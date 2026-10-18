import SwiftUI

struct DashboardView: View {
    @Environment(SessionStore.self) private var session
    @State private var children: [ChildListItem] = []
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("Hello, \(session.user?.displayName ?? "guardian").")
                        .font(.kinwiseHeadline)
                        .foregroundStyle(Theme.ink)
                    Text("Every linked guardian has the same supervision tools. Counts come from saved activity.")
                        .font(.subheadline)
                        .foregroundStyle(Theme.ink.opacity(0.75))
                    if let error { ErrorBanner(message: error) }
                    if children.isEmpty {
                        KinwiseCard {
                            Text("No children yet. Create an account from the Children tab.")
                                .foregroundStyle(Theme.ink)
                        }
                    }
                    ForEach(children) { child in
                        NavigationLink {
                            ChildDetailView(childID: child.id, name: child.displayName)
                        } label: {
                            KinwiseCard {
                                HStack {
                                    VStack(alignment: .leading, spacing: 6) {
                                        Text(child.displayName).font(.headline).foregroundStyle(Theme.ink)
                                        Text("@\(child.username) · \(child.messagesToday) messages today")
                                            .font(.subheadline)
                                            .foregroundStyle(Theme.ink.opacity(0.7))
                                    }
                                    Spacer()
                                    StatusPill(paused: child.isPaused)
                                }
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(20)
            }
            .background(Theme.cream)
            .navigationTitle("Kinwise")
            .task { await load() }
            .refreshable { await load() }
        }
    }

    private func load() async {
        do {
            children = try await session.api.children(token: try session.token())
            error = nil
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }
}
