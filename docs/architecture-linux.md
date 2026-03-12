# Linux Architecture

## Component diagram

```mermaid
flowchart TD
    subgraph App["SoftNoiseApp (Adw.Application)"]
        ACT["activate signal"]
    end

    subgraph Win["SoftNoiseWindow (Adw.ApplicationWindow · UI thread)"]
        direction TB
        NCRow["AdwSwitchRow\nNoise Cancellation"]
        VolRow["AdwActionRow + GtkScale\nMonitor Volume 0–1"]
        LevelBar["GtkLevelBar\n(offsets 0.6 / 0.85 / 1.0)"]
        StartStop["GtkButton\nStart / Stop"]
        InfoText["GtkLabel ×4\ninfo + pactl cmd"]
    end

    subgraph Engine["AudioEngine (owns stream)"]
        direction TB
        SD["sounddevice.Stream\nsamplerate=48000\nblocksize=480\nchannels=1, float32\nlatency=low"]

        subgraph CB["_audio_callback (audio thread)"]
            direction TB
            Copy["indata[:,0].copy()"]
            RNN["_RNNoiseState.process()\n(if nc_enabled and available)"]
            RMS["_rms_to_level()\n−60 dB…0 dB → 0…1"]
            Out["outdata[:,0] = samples × monitor_volume"]
        end

        Lock["threading.Lock\n(guards nc_enabled, monitor_volume)"]
        Idle["GLib.idle_add()\n→ UI thread callbacks"]
    end

    subgraph RNNLib["rnnoise ctypes shim"]
        direction TB
        CDLL["ctypes.CDLL('librnnoise.so.0')"]
        Create["rnnoise_create(NULL)\n→ DenoiseState*"]
        Process["rnnoise_process_frame()\n480 × float32 (int16-range scaled)"]
    end

    Mic(["Microphone\n(default input)"])
    HP(["Headphones / Speakers\n(default output)"])
    PW(["PipeWire / PulseAudio\n(PortAudio compat layer)"])

    ACT --> Win
    Win --> Engine

    PW -->|PCM| Mic
    Mic -->|float32 frames| SD
    SD --> CB
    CB --> Copy --> RNN --> RMS --> Out
    Out -->|float32| HP
    HP --> PW

    RNN <-->|"480 samples\n(int16-scaled)"| Process
    Process <--> Create
    Create <--> CDLL

    RMS -->|level float| Idle
    Idle -->|on_level_changed| LevelBar

    NCRow -->|toggle_nc()| Lock
    VolRow -->|set_monitor_volume()| Lock
    Lock --> CB

    StartStop -->|start() / stop()| SD
```

## Key design decisions

| Decision | Detail |
|---|---|
| NC implementation | `librnnoise.so` via ctypes; falls back gracefully if not installed (NC row disabled in UI) |
| NC toggle | Flips `nc_enabled` flag protected by `threading.Lock` — takes effect on the next callback frame, **no stream restart** needed |
| int16-range scaling | rnnoise expects samples in `−32768…32767` range; we scale `×32768` in, `/32768` out |
| Thread model | `sounddevice` callback runs on a PortAudio real-time thread; all UI mutations go through `GLib.idle_add()` (equivalent of Swift's `Task { @MainActor in … }`) |
| Monitor mode | `outdata[:,0] = samples * monitor_volume`; volume 0.0 → silence, no extra latency |
| Audio backend | `sounddevice` → PortAudio → PipeWire (via PulseAudio compat socket) or PulseAudio directly; no PipeWire-specific code needed |
| RMS formula | Same as macOS: `rms = √mean(x²)`, `dB = 20·log₁₀(rms)`, `level = (dB − (−60)) / 60`, clamped 0–1 |
| System-wide NC | Documented as `pactl load-module module-null-sink` virtual sink; apps route their mic through it |

## Data flow — audio path

```
Microphone
  └─► PipeWire / PulseAudio (PortAudio compat)
        └─► sounddevice.Stream callback (audio thread, 480 float32 frames)
              ├─► [nc_enabled] _RNNoiseState.process()
              │     └─► librnnoise.rnnoise_process_frame()
              ├─► _rms_to_level() → GLib.idle_add → GtkLevelBar
              └─► outdata[:,0] × monitor_volume
                    └─► PipeWire / PulseAudio → Headphones / Speakers
```

## Data flow — state changes

```
User action           AudioEngine mutation              UI reaction
──────────────────────────────────────────────────────────────────────
press Start      →    start() → stream.start()        → on_running_changed(True) → button → "Stop" (red)
press Stop       →    stop()  → stream.stop/close()   → on_running_changed(False) → button → "Start" (blue)
toggle NC on     →    toggle_nc(True) → new _RNNoiseState (no restart)  → immediate next frame
toggle NC off    →    toggle_nc(False) → _rnnoise = None (no restart)   → immediate next frame
drag volume      →    set_monitor_volume() → self.monitor_volume        → next callback picks up lock value
audio arrives    →    _rms_to_level() → GLib.idle_add                   → GtkLevelBar.set_value()
```

## Packaging overview

```mermaid
flowchart LR
    Src["linux/\nsource tree"]

    Src -->|"meson setup + compile"| Meson["meson build\n(verifies layout)"]
    Src -->|"dpkg-buildpackage"| Deb[".deb\n(Ubuntu 22.04+)"]
    Src -->|"appimage-builder"| AImg["SoftNoise-x86_64\n.AppImage\n(~45 MB, self-contained)"]
    Src -->|"flatpak-builder"| FP["com.softnoise.app\nFlatpak\n(GNOME Platform 47)"]

    FP -->|"modules: rnnoise\nnumpy, sounddevice\nsoftnoise"| FPM["Flatpak bundle"]
```
