import SwiftUI

struct ConversationsView: View {
    @Environment(SessionStore.self) private var session
    @State private var conversations: [ConversationSummary] = []
    @State private var path = NavigationPath()
    @State private var visibleCount = 10
    @State private var error: String?
    @State private var isLoading = false

    private var visibleConversations: [ConversationSummary] {
        Array(conversations.prefix(visibleCount))
    }

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if session.access.isPaused {
                        PausedBanner()
                    }
                    if let error { ErrorBanner(message: error) }
                    if conversations.isEmpty && !isLoading {
                        KinwiseCard {
                            Text("No conversations yet. Start one when you're curious about something.")
                                .foregroundStyle(Theme.ink)
                        }
                    }
                    ForEach(visibleConversations) { conversation in
                        NavigationLink(value: conversation) {
                            KinwiseCard {
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(conversation.title).font(.headline).foregroundStyle(Theme.ink)
                                    if let summary = conversation.summary {
                                        Text(summary).font(.subheadline).foregroundStyle(Theme.ink.opacity(0.7)).lineLimit(2)
                                    }
                                }
                            }
                        }
                        .buttonStyle(.plain)
                    }
                    if visibleCount < conversations.count {
                        Button("Load older conversations") { visibleCount += 10 }
                            .buttonStyle(.bordered)
                    }
                }
                .padding(20)
            }
            .background(Theme.cream)
            .navigationTitle("Kinwise")
            .navigationDestination(for: ConversationSummary.self) { conversation in
                ChatView(conversation: conversation)
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await createConversation() }
                    } label: {
                        Image(systemName: "plus.circle.fill")
                    }
                    .accessibilityLabel("New conversation")
                    .disabled(session.access.isPaused)
                }
            }
            .task { await load() }
            .refreshable { await load() }
        }
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            conversations = try await session.api.conversations(token: try session.token())
            error = nil
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func createConversation() async {
        do {
            let created = try await session.api.createConversation(token: try session.token())
            conversations.insert(created, at: 0)
            path.append(created)
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }
}

struct PausedBanner: View {
    var body: some View {
        KinwiseCard {
            Label("Chat is paused by a guardian.", systemImage: "pause.circle.fill")
                .font(.headline)
                .foregroundStyle(Theme.ink)
        }
    }
}
