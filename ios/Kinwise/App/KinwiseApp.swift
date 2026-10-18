import SwiftUI
import UserNotifications

@main
struct KinwiseApp: App {
    @State private var session = SessionStore()

    init() {
        let center = UNUserNotificationCenter.current()
        MainActor.assumeIsolated {
            center.delegate = SafetyAlertCenter.shared
        }
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(session)
                .tint(Theme.blue)
        }
    }
}
