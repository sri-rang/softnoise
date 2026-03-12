import AVFoundation

@MainActor
final class AudioEngine: ObservableObject {
    @Published var isRunning = false
    @Published var inputLevel: Float = 0.0
    @Published var noiseCancellationEnabled = true
    @Published var monitorVolume: Float = 0.0

    private var engine = AVAudioEngine()

    func start() async {
        guard !isRunning else { return }
        let granted = await AVCaptureDevice.requestAccess(for: .audio)
        guard granted else {
            print("SoftNoise: microphone access denied")
            return
        }
        do {
            try setupEngine()
            try engine.start()
            isRunning = true
        } catch {
            print("SoftNoise: engine start error: \(error)")
        }
    }

    func stop() {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        isRunning = false
        inputLevel = 0.0
    }

    func restart() async {
        stop()
        await start()
    }

    func setMonitorVolume(_ value: Float) {
        monitorVolume = value
        if engine.isRunning {
            engine.mainMixerNode.outputVolume = value
        }
    }

    private func setupEngine() throws {
        engine = AVAudioEngine()
        try engine.inputNode.setVoiceProcessingEnabled(noiseCancellationEnabled)
        let fmt = engine.inputNode.outputFormat(forBus: 0)
        engine.connect(engine.inputNode, to: engine.mainMixerNode, format: fmt)
        engine.mainMixerNode.outputVolume = monitorVolume
        engine.inputNode.installTap(onBus: 0, bufferSize: 1024, format: fmt) { [weak self] buffer, _ in
            let level = AudioEngine.rmsLevel(buffer: buffer)
            Task { @MainActor [weak self] in
                guard let self, self.isRunning else { return }
                self.inputLevel = level
            }
        }
        engine.prepare()
    }

    private static func rmsLevel(buffer: AVAudioPCMBuffer) -> Float {
        guard let data = buffer.floatChannelData, buffer.frameLength > 0 else { return 0 }
        let frames = Int(buffer.frameLength)
        let ptr = data[0]
        var sum: Float = 0
        for i in 0..<frames { sum += ptr[i] * ptr[i] }
        let rms = sqrt(sum / Float(frames))
        let db = 20 * log10(max(rms, 1e-7))
        return max(0, min(1, (db + 60) / 60))
    }
}
