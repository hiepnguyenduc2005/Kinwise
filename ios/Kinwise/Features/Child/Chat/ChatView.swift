import SwiftUI

struct ChatView: View {
    @Environment(SessionStore.self) private var session
    let conversation: ConversationSummary
    @State private var messages: [ChatMessage] = []
    @State private var draft = ""
    @State private var composerID = UUID()
    @FocusState private var composerFocused: Bool
    @State private var isSending = false
    @State private var closed = false
    @State private var error: String?

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(spacing: 12) {
                        if session.access.isPaused { PausedView() }
                        if closed {
                            KinwiseCard {
                                Text("Kinwise closed this chat to keep you safe.")
                                    .foregroundStyle(Theme.ink)
                            }
                            .padding(.horizontal, 16)
                        }
                        if let error { ErrorBanner(message: error).padding(.horizontal, 16) }
                        ForEach(messages) { message in
                            MessageBubble(message: message).padding(.horizontal, 16).id(message.id)
                        }
                        if isSending {
                            ProgressView("Kinwise is thinking")
                                .padding()
                                .accessibilityLabel("Kinwise is thinking")
                        }
                    }
                    .padding(.vertical, 16)
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: messages.count) { _, _ in
                    if let last = messages.last {
                        withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                    }
                }
            }
            if !session.access.isPaused && !closed {
                composer
            }
        }
        .background(Theme.cream)
        .kinwiseForm()
        .navigationTitle(closed ? "Closed conversation" : conversation.title)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            closed = conversation.ended
            await load()
        }
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Ask Kinwise", text: $draft, axis: .vertical)
                .id(composerID)
                .focused($composerFocused)
                .lineLimit(1...4)
                .foregroundStyle(Theme.ink)
                .padding(12)
                .background(Theme.field)
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                .accessibilityLabel("Message")
            Button {
                Task { await send() }
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 32))
            }
            .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSending)
            .accessibilityLabel("Send message")
        }
        .padding(12)
        .background(Theme.card)
    }

    private func load() async {
        do {
            messages = try await session.api.messages(token: try session.token(), conversationID: conversation.id)
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func send() async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        draft = ""
        composerID = UUID()
        composerFocused = true
        isSending = true
        defer { isSending = false }
        do {
            let response = try await session.api.sendMessage(token: try session.token(), conversationID: conversation.id, content: text)
            messages.append(response.userMessage)
            if let assistant = response.assistantMessage {
                messages.append(assistant)
            }
            closed = response.conversationEnded
            session.access = response.access
            error = nil
        } catch let failure as APIFailure {
            error = failure.message
            if failure.code == "conversation_ended" { closed = true }
            if failure.code == "access_paused" || failure.code == "response_withheld" {
                await session.refreshAccess()
            }
            await load()
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }
}
