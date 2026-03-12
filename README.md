# SoftNoise

Real-time microphone noise cancellation and monitor mode (sidetone).

- **macOS** — native SwiftUI app using Apple's Voice Processing I/O unit
- **Linux** — GTK4/libadwaita app using RNNoise + sounddevice (PipeWire/PulseAudio)

---

## macOS

**Requirements**

- macOS 13+
- Xcode 15+

**Run**

```sh
make run
```

Grant microphone access when prompted.

**Architecture overview**

```mermaid
flowchart TD
    subgraph UI["UI layer — ContentView (SwiftUI · @MainActor)"]
        Toggle["NC Toggle"] & Slider["Volume Slider"] & Meter["Level Meter"] & Btn["Start / Stop"]
    end

    subgraph Engine["AudioEngine (AVAudioEngine)"]
        IN["inputNode\n+ Voice Processing I/O"]
        MX["mainMixerNode\n(outputVolume)"]
        TAP["buffer tap → RMS"]
    end

    Mic(["Mic"]) --> IN
    IN --> MX --> HP(["Headphones"])
    IN --> TAP -->|"@Published inputLevel"| Meter
    Toggle -->|"restart on change"| Engine
    Slider -->|"outputVolume"| MX
    Btn -->|"start / stop"| Engine
```

> See [`docs/architecture-macos.md`](docs/architecture-macos.md) for the full diagram.

---

## Linux

**Requirements**

- Python 3.10+
- GTK4 + libadwaita Python bindings
- sounddevice, numpy
- librnnoise (optional — NC is disabled if not found)

Install on Ubuntu 22.04+:

```sh
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
                 python3-numpy python3-sounddevice librnnoise0
```

**Run**

```sh
make linux-run
```

**Architecture overview**

```mermaid
flowchart TD
    subgraph UI["UI layer — SoftNoiseWindow (GTK4 / libadwaita)"]
        NCRow["NC Switch"] & VolRow["Volume Scale"] & LBar["Level Bar"] & Btn2["Start / Stop"]
    end

    subgraph Engine["AudioEngine (sounddevice · audio thread)"]
        SD["Stream\n48 kHz · 480 frames · float32"]
        RNN["rnnoise ctypes\n(optional — skipped if lib missing)"]
        RMS2["RMS → 0–1 level"]
        Out["× monitor_volume → out"]
    end

    PW(["PipeWire / PulseAudio"])
    Mic2(["Mic"]) --> PW --> SD
    SD --> RNN --> RMS2 & Out
    Out --> PW --> HP2(["Headphones"])
    RMS2 -->|"GLib.idle_add"| LBar
    NCRow -->|"toggle_nc() — no restart"| RNN
    VolRow -->|"set_monitor_volume()"| Out
    Btn2 -->|"start / stop"| SD
```

> See [`docs/architecture-linux.md`](docs/architecture-linux.md) for the full diagram.

### Build installable packages

```sh
make linux-build      # meson build (verifies install layout)
make linux-deb        # .deb for Ubuntu/Debian (requires dpkg-dev, debhelper)
make linux-appimage   # AppImage (requires appimage-builder)
make linux-flatpak    # Flatpak (requires flatpak-builder + GNOME SDK 47)
```
