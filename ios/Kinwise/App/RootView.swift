import SwiftUI

struct RootView: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        Group {
            if session.isRestoring {
                ProgressView("Opening Kinwise")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Theme.cream)
            } else if session.user == nil {
                WelcomeView()
            } else if session.user?.role == "guardian" {
                GuardianTabView()
            } else {
                ChildTabView()
            }
        }
        .task {
            await session.restore()
        }
        .onChange(of: scenePhase) { _, phase in
            guard phase == .active, session.user?.role == "child" else { return }
            Task { await session.refreshAccess() }
        }
    }
}
