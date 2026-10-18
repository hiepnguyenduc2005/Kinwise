import SwiftUI

struct ChildProfileView: View {
    @Environment(SessionStore.self) private var session
    @State private var profile: ChildMe?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let error { ErrorBanner(message: error) }
                    KinwiseCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(profile?.displayName ?? session.user?.displayName ?? "Kinwise")
                                .font(.kinwiseHeadline)
                            Text("@\(profile?.username ?? session.user?.username ?? "")")
                                .foregroundStyle(Theme.ink.opacity(0.7))
                            if let band = profile?.ageBand {
                                Text("Age band \(band)")
                                    .font(.subheadline)
                            }
                            StatusPill(paused: session.access.isPaused)
                        }
                    }
                    KinwiseCard {
                        Text(profile?.supervisionNotice ?? "A linked guardian can see ordinary conversations.")
                            .font(.body)
                            .foregroundStyle(Theme.ink)
                    }
                    if session.access.isPaused {
                        Text("Sign out is off while Kinwise is paused.")
                            .font(.subheadline)
                            .foregroundStyle(Theme.ink.opacity(0.72))
                    } else {
                    if session.access.isPaused {
                        Text("Sign out is off while Kinwise is paused.")
                            .font(.subheadline)
                            .foregroundStyle(Theme.ink.opacity(0.7))
                    } else {
                        Button("Sign out", role: .destructive) {
                            Task { await session.logout() }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    }
                }
                .padding(20)
            }
            .background(Theme.cream)
            .navigationTitle("Me")
            .task { await load() }
        }
    }

    private func load() async {
        do {
            profile = try await session.api.childMe(token: try session.token())
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }
}
