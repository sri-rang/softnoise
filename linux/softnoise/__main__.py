"""
__main__.py — Adw.Application entry point for SoftNoise
"""

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio  # noqa: E402

from .audio_engine import AudioEngine  # noqa: E402
from .window import SoftNoiseWindow  # noqa: E402

APP_ID = "com.softnoise.app"


class SoftNoiseApp(Adw.Application):

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._engine = AudioEngine()
        self.connect("activate", self._on_activate)

    def _on_activate(self, app: "SoftNoiseApp") -> None:
        win = self.get_active_window()
        if win is None:
            win = SoftNoiseWindow(app=self, engine=self._engine)
        win.present()

    def do_shutdown(self) -> None:
        if self._engine.is_running:
            self._engine.stop()
        Adw.Application.do_shutdown(self)


def main() -> int:
    app = SoftNoiseApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
