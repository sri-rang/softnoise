import SwiftUI

struct ContentView: View {
    @StateObject private var audio = AudioEngine()

    var body: some View {
        VStack(spacing: 20) {
            // Header
            HStack {
                Text("SoftNoise")
                    .font(.title2.bold())
                Spacer()
                Circle()
                    .fill(audio.isRunning ? Color.green : Color.gray)
                    .frame(width: 10, height: 10)
            }

            Divider()

            // Voice Processing toggle
            Toggle("Voice Processing (Noise Cancellation)", isOn: Binding(
                get: { audio.noiseCancellationEnabled },
                set: { newValue in
                    audio.noiseCancellationEnabled = newValue
                    if audio.isRunning {
                        Task { await audio.restart() }
                    }
                }
            ))

            // Monitor volume
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("Monitor Volume")
                        .font(.subheadline)
                    Spacer()
                    Text(String(format: "%.0f%%", audio.monitorVolume * 100))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
                Slider(
                    value: Binding(
                        get: { Double(audio.monitorVolume) },
                        set: { audio.setMonitorVolume(Float($0)) }
                    ),
                    in: 0...1
                )
            }

            // Level meter
            VStack(alignment: .leading, spacing: 6) {
                Text("Input Level")
                    .font(.subheadline)
                LevelMeterView(level: audio.inputLevel)
                    .frame(height: 16)
            }

            // Start / Stop
            Button {
                Task {
                    if audio.isRunning {
                        audio.stop()
                    } else {
                        await audio.start()
                    }
                }
            } label: {
                Text(audio.isRunning ? "Stop" : "Start")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(audio.isRunning ? .red : .accentColor)

            Divider()

            // Info
            VStack(alignment: .leading, spacing: 8) {
                Text("Monitor Mode")
                    .font(.caption.bold())
                Text("Set Monitor Volume > 0 to hear your voice with noise cancellation applied through your headphones (sidetone).")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)

                Text("System-wide NC")
                    .font(.caption.bold())
                    .padding(.top, 4)
                Text("For calls and other apps: route your mic through BlackHole virtual device and select BlackHole as the input in your target app.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(20)
        .frame(width: 380)
    }
}

struct LevelMeterView: View {
    let level: Float

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.secondary.opacity(0.2))
                RoundedRectangle(cornerRadius: 4)
                    .fill(meterColor)
                    .frame(width: geo.size.width * CGFloat(level))
                    .animation(.linear(duration: 0.05), value: level)
            }
        }
    }

    private var meterColor: Color {
        switch level {
        case ..<0.6:  return .green
        case ..<0.85: return .yellow
        default:      return .red
        }
    }
}
