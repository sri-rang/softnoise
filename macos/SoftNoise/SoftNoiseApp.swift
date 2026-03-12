import SwiftUI

@main
struct SoftNoiseApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowResizability(.contentSize)
        .defaultSize(width: 380, height: 480)
    }
}
