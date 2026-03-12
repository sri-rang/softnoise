"""
window.py — GTK4 / libadwaita UI for SoftNoise
All UI mutations go through GLib.idle_add() for thread safety.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, GLib  # noqa: E402

from .audio_engine import AudioEngine  # noqa: E402


SYSTEM_WIDE_NC_CMD = (
    "pactl load-module module-null-sink sink_name=softnoise_nc "
    "sink_properties=device.description=SoftNoise-NC"
)

INFO_LINES = [
    "<b>Monitor Mode</b>: sets outgoing audio to your headphones.",
    "Set Monitor Volume &gt; 0 to hear yourself.",
    "",
    "<b>System-wide NC</b>: route apps through the virtual sink:",
    f"<tt>{SYSTEM_WIDE_NC_CMD}</tt>",
]


class SoftNoiseWindow(Adw.ApplicationWindow):

    def __init__(self, app: Adw.Application, engine: AudioEngine) -> None:
        super().__init__(application=app, title="SoftNoise",
                         default_width=380, resizable=False)
        self._engine = engine

        engine.on_level_changed = self._on_level_changed
        engine.on_running_changed = self._on_running_changed

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        # Header bar
        self._header = Adw.HeaderBar()
        self._subtitle_label = Gtk.Label(label="Stopped")
        self._subtitle_label.add_css_class("caption")
        self._subtitle_label.add_css_class("dim-label")
        self._header.set_title_widget(
            self._make_title_widget()
        )
        toolbar_view.add_top_bar(self._header)

        # Main content box
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(20)
        content.set_margin_end(20)
        toolbar_view.set_content(content)

        # Preferences group: NC toggle + monitor volume
        prefs = Adw.PreferencesGroup()
        content.append(prefs)

        # NC switch row
        self._nc_row = Adw.SwitchRow(
            title="Voice Processing (Noise Cancellation)",
        )
        if not self._engine.nc_available:
            self._nc_row.set_subtitle("librnnoise not found")
            self._nc_row.set_sensitive(False)
        self._nc_row.set_active(self._engine.nc_enabled)
        self._nc_row.connect("notify::active", self._on_nc_toggled)
        prefs.add(self._nc_row)

        # Monitor volume row
        vol_row = Adw.ActionRow(title="Monitor Volume")
        self._vol_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.05
        )
        self._vol_scale.set_value(self._engine.monitor_volume)
        self._vol_scale.set_hexpand(True)
        self._vol_scale.set_size_request(160, -1)
        self._vol_scale.connect("value-changed", self._on_volume_changed)
        vol_row.add_suffix(self._vol_scale)
        vol_row.set_activatable_widget(self._vol_scale)
        prefs.add(vol_row)

        # Level meter section
        level_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content.append(level_box)

        level_label = Gtk.Label(label="Input Level", xalign=0)
        level_label.add_css_class("caption")
        level_box.append(level_label)

        self._level_bar = Gtk.LevelBar()
        self._level_bar.set_min_value(0.0)
        self._level_bar.set_max_value(1.0)
        self._level_bar.set_value(0.0)
        self._level_bar.add_offset_value(Gtk.LEVEL_BAR_OFFSET_LOW, 0.6)
        self._level_bar.add_offset_value(Gtk.LEVEL_BAR_OFFSET_HIGH, 0.85)
        self._level_bar.add_offset_value(Gtk.LEVEL_BAR_OFFSET_FULL, 1.0)
        level_box.append(self._level_bar)

        # Start / Stop button
        self._toggle_btn = Gtk.Button(label="Start")
        self._toggle_btn.add_css_class("suggested-action")
        self._toggle_btn.set_halign(Gtk.Align.CENTER)
        self._toggle_btn.connect("clicked", self._on_toggle_clicked)
        content.append(self._toggle_btn)

        # Info text
        for line in INFO_LINES:
            lbl = Gtk.Label()
            lbl.set_markup(line)
            lbl.set_wrap(True)
            lbl.set_xalign(0)
            lbl.add_css_class("caption")
            content.append(lbl)

    def _make_title_widget(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_valign(Gtk.Align.CENTER)

        title = Gtk.Label(label="SoftNoise")
        title.add_css_class("heading")
        box.append(title)

        box.append(self._subtitle_label)
        return box

    # ------------------------------------------------------------------
    # Signal handlers (UI thread)
    # ------------------------------------------------------------------

    def _on_toggle_clicked(self, _btn: Gtk.Button) -> None:
        if self._engine.is_running:
            self._engine.stop()
        else:
            self._engine.start()

    def _on_nc_toggled(self, row: Adw.SwitchRow, _param) -> None:
        self._engine.toggle_nc(row.get_active())

    def _on_volume_changed(self, scale: Gtk.Scale) -> None:
        self._engine.set_monitor_volume(scale.get_value())

    # ------------------------------------------------------------------
    # Engine callbacks → scheduled on GLib main loop
    # ------------------------------------------------------------------

    def _on_level_changed(self, level: float) -> None:
        self._level_bar.set_value(level)

    def _on_running_changed(self, running: bool) -> None:
        if running:
            self._subtitle_label.set_label("Running")
            self._subtitle_label.remove_css_class("dim-label")
            self._subtitle_label.add_css_class("success")
            self._toggle_btn.set_label("Stop")
            self._toggle_btn.remove_css_class("suggested-action")
            self._toggle_btn.add_css_class("destructive-action")
        else:
            self._subtitle_label.set_label("Stopped")
            self._subtitle_label.remove_css_class("success")
            self._subtitle_label.add_css_class("dim-label")
            self._toggle_btn.set_label("Start")
            self._toggle_btn.remove_css_class("destructive-action")
            self._toggle_btn.add_css_class("suggested-action")
            self._level_bar.set_value(0.0)
