"""
audio_engine.py — sounddevice stream + rnnoise ctypes + RMS metering
Mirrors AudioEngine.swift: same state properties, same RMS formula.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import math
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
from gi.repository import GLib

logger = logging.getLogger(__name__)

FRAME_SIZE = 480    # rnnoise fixed frame size
SAMPLE_RATE = 48000  # rnnoise requirement


# ---------------------------------------------------------------------------
# rnnoise ctypes shim
# ---------------------------------------------------------------------------

def _load_rnnoise() -> Optional[ctypes.CDLL]:
    """Load librnnoise, returning None if unavailable."""
    for name in ("librnnoise.so.0", "librnnoise.so", "rnnoise"):
        try:
            found = ctypes.util.find_library(name) or name
            lib = ctypes.CDLL(found)
            # Validate that the expected symbols exist
            _ = lib.rnnoise_create
            _ = lib.rnnoise_process_frame
            _ = lib.rnnoise_destroy
            lib.rnnoise_create.restype = ctypes.c_void_p
            lib.rnnoise_create.argtypes = [ctypes.c_void_p]
            lib.rnnoise_process_frame.restype = ctypes.c_float
            lib.rnnoise_process_frame.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
            ]
            lib.rnnoise_destroy.restype = None
            lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
            logger.info("Loaded rnnoise from %s", found)
            return lib
        except (OSError, AttributeError):
            continue
    logger.warning("librnnoise not found — noise cancellation unavailable")
    return None


_rnnoise_lib: Optional[ctypes.CDLL] = _load_rnnoise()


class _RNNoiseState:
    """Wraps a single rnnoise DenoiseState for one channel."""

    def __init__(self) -> None:
        if _rnnoise_lib is None:
            raise RuntimeError("librnnoise not available")
        self._state = _rnnoise_lib.rnnoise_create(None)
        if not self._state:
            raise RuntimeError("rnnoise_create returned NULL")

    def process(self, samples: np.ndarray) -> np.ndarray:
        """Process exactly FRAME_SIZE float32 samples in-place and return result."""
        assert samples.shape == (FRAME_SIZE,), f"Expected {FRAME_SIZE} samples"
        # rnnoise operates on int16-range floats (−32768 … 32767)
        scaled = (samples * 32768.0).astype(np.float32)
        out = np.zeros(FRAME_SIZE, dtype=np.float32)
        in_ptr = scaled.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        out_ptr = out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        _rnnoise_lib.rnnoise_process_frame(self._state, out_ptr, in_ptr)
        return (out / 32768.0).astype(np.float32)

    def __del__(self) -> None:
        if _rnnoise_lib is not None and self._state:
            _rnnoise_lib.rnnoise_destroy(self._state)


# ---------------------------------------------------------------------------
# RMS → normalised level  (mirrors Swift AudioEngine formula)
# ---------------------------------------------------------------------------

_DB_FLOOR = -60.0  # dB floor mapped to 0.0
_DB_CEIL = 0.0     # dB ceiling mapped to 1.0


def _rms_to_level(samples: np.ndarray) -> float:
    """Return a 0.0–1.0 normalised level from raw float32 samples."""
    rms = float(np.sqrt(np.mean(samples ** 2)))
    if rms < 1e-10:
        return 0.0
    db = 20.0 * math.log10(rms)
    db = max(_DB_FLOOR, min(_DB_CEIL, db))
    return (db - _DB_FLOOR) / (_DB_CEIL - _DB_FLOOR)


# ---------------------------------------------------------------------------
# AudioEngine
# ---------------------------------------------------------------------------

class AudioEngine:
    """
    Manages a sounddevice full-duplex stream with optional rnnoise NC.

    Callbacks (set before calling start):
        on_level_changed(level: float)    — called on GLib main loop
        on_running_changed(running: bool) — called on GLib main loop
    """

    def __init__(self) -> None:
        self.is_running: bool = False
        self.nc_enabled: bool = True
        self.monitor_volume: float = 0.0  # 0.0–1.0
        self.input_level: float = 0.0     # last computed RMS level

        self.on_level_changed: Callable[[float], None] = lambda _: None
        self.on_running_changed: Callable[[bool], None] = lambda _: None

        self._stream: Optional[sd.Stream] = None
        self._rnnoise: Optional[_RNNoiseState] = None
        self._lock = threading.Lock()

        # Accumulate samples to fill exactly FRAME_SIZE for rnnoise
        self._nc_buffer = np.zeros(0, dtype=np.float32)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def nc_available(self) -> bool:
        return _rnnoise_lib is not None

    def start(self) -> None:
        if self.is_running:
            return
        if self.nc_enabled and self.nc_available:
            self._rnnoise = _RNNoiseState()
        self._nc_buffer = np.zeros(0, dtype=np.float32)
        self._stream = sd.Stream(
            samplerate=SAMPLE_RATE,
            blocksize=FRAME_SIZE,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
            latency="low",
        )
        self._stream.start()
        self.is_running = True
        GLib.idle_add(self._notify_running, True)

    def stop(self) -> None:
        if not self.is_running:
            return
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._rnnoise is not None:
            self._rnnoise = None
        self.is_running = False
        GLib.idle_add(self._notify_running, False)

    def toggle_nc(self, enabled: bool) -> None:
        """Toggle noise cancellation mid-stream — no restart needed."""
        with self._lock:
            self.nc_enabled = enabled
            if enabled and self.nc_available and self._rnnoise is None:
                self._rnnoise = _RNNoiseState()
            elif not enabled:
                self._rnnoise = None

    def set_monitor_volume(self, volume: float) -> None:
        self.monitor_volume = max(0.0, min(1.0, volume))

    # ------------------------------------------------------------------
    # Audio callback (audio thread — NO Python objects allocation)
    # ------------------------------------------------------------------

    def _audio_callback(
        self,
        indata: np.ndarray,
        outdata: np.ndarray,
        frames: int,
        time,  # noqa: ANN001
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            logger.warning("sounddevice status: %s", status)

        samples = indata[:, 0].copy()

        with self._lock:
            rnnoise = self._rnnoise
            volume = self.monitor_volume

        if rnnoise is not None:
            try:
                samples = rnnoise.process(samples)
            except Exception as exc:  # noqa: BLE001
                logger.error("rnnoise error: %s", exc)

        level = _rms_to_level(samples)
        self.input_level = level
        GLib.idle_add(self._notify_level, level)

        outdata[:, 0] = samples * volume

    # ------------------------------------------------------------------
    # GLib main-loop callbacks
    # ------------------------------------------------------------------

    def _notify_level(self, level: float) -> bool:
        self.on_level_changed(level)
        return GLib.SOURCE_REMOVE

    def _notify_running(self, running: bool) -> bool:
        self.on_running_changed(running)
        return GLib.SOURCE_REMOVE
