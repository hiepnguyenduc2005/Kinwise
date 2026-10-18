import SwiftUI

struct ChildDetailView: View {
    @Environment(SessionStore.self) private var session
    let childID: UUID
    let name: String
    var focusConversationID: UUID? = nil
    var focusMessageID: UUID? = nil
    @State private var overview: ChildOverview?
    @State private var guardians: [GuardianLink] = []
    @State private var invites: [InvitationPending] = []
    @State private var inviteCode: String?
    @State private var conversations: [ConversationSummary] = []
    @State private var visibleCount = 5
    @State private var expandedID: UUID?
    @State private var transcripts: [UUID: [ChatMessage]] = [:]
    @State private var error: String?
    @State private var password = ""
    @State private var newChildPassword = ""
    @State private var displayName = ""
    @State private var ageBand = "9-11"
    @State private var pageTitle = ""
    @State private var editingChild = false
    @State private var busy = false
    @State private var didOpenFocus = false

    private let ageBands = ["6-8", "9-11", "12-14", "15-17"]

    private var trimmedName: String {
        displayName.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var nameChanged: Bool {
        guard let original = overview?.child.displayName else { return false }
        return !trimmedName.isEmpty && trimmedName != original
    }

    private var ageChanged: Bool {
        guard let original = overview?.child.ageBand else { return false }
        return ageBand != original
    }

    private var visibleConversations: [ConversationSummary] {
        Array(conversations.prefix(visibleCount))
    }

    var body: some View {
        ScrollViewReader { proxy in
        List {
            Section {
            VStack(alignment: .leading, spacing: 14) {
                if let error { ErrorBanner(message: error) }
                if let child = overview?.child {
                    KinwiseCard {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text(child.displayName).font(.kinwiseHeadline)
                                Spacer()
                                StatusPill(paused: child.access.isPaused)
                            }
                            Text("@\(child.username) · ages \(child.ageBand)")
                                .font(.subheadline)
                            Button(child.access.isPaused ? "Resume Kinwise" : "Pause Kinwise") {
                                Task { await toggle(paused: child.access.isPaused) }
                            }
                            .buttonStyle(.borderedProminent)
                            .controlSize(.large)
                            .tint(child.access.isPaused ? Theme.mint : Theme.blue)
                            .padding(.top, 8)
                            .accessibilityLabel(child.access.isPaused ? "Resume access" : "Pause access")
                        }
                    }
                    KinwiseCard {
                        VStack(alignment: .leading, spacing: 16) {
                            Button {
                                editingChild.toggle()
                            } label: {
                                HStack {
                                    Text("Edit child").font(.headline)
                                    Spacer()
                                    Image(systemName: editingChild ? "chevron.up" : "chevron.down")
                                        .accessibilityHidden(true)
                                }
                                .frame(maxWidth: .infinity, minHeight: 52, alignment: .leading)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel(editingChild ? "Hide child edits" : "Edit child")
                            if editingChild {
                                FieldLabel(title: "Display name", text: $displayName)
                                Button("Save name") { Task { await saveName() } }
                                    .buttonStyle(.borderedProminent)
                                    .controlSize(.large)
                                    .disabled(!nameChanged || busy)
                                Picker("Age band", selection: $ageBand) {
                                    ForEach(ageBands, id: \.self) { Text($0).tag($0) }
                                }
                                .pickerStyle(.segmented)
                                Button("Save age") { Task { await saveAge() } }
                                    .buttonStyle(.borderedProminent)
                                    .controlSize(.large)
                                    .disabled(!ageChanged || busy)
                                Text("Password").font(.subheadline.weight(.semibold))
                                FieldLabel(title: "Your password", text: $password, secure: true)
                                FieldLabel(title: "New child password", text: $newChildPassword, secure: true)
                                Button("Save password") { Task { await resetPassword() } }
                                    .buttonStyle(.borderedProminent)
                                    .controlSize(.large)
                                    .disabled(password.isEmpty || newChildPassword.count < 8 || busy)
                            }
                        }
                    }
                }
                if let usage = overview?.usage {
                    KinwiseCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Usage").font(.headline)
                            Text("\(usage.messagesToday) messages today · \(usage.conversationsToday) conversations today")
                            ForEach(usage.messagesLast7Days) { day in
                                HStack {
                                    Text(day.date).font(.caption)
                                    Spacer()
                                    Text("\(day.count)").font(.caption.monospacedDigit())
                                }
                            }
                            ForEach(usage.safetyCounts) { item in
                                Text("\(item.category.replacingOccurrences(of: "_", with: " ")): \(item.count)")
                                    .font(.caption)
                            }
                        }
                    }
                }
                KinwiseCard {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Guardians").font(.headline)
                        ForEach(guardians) { guardian in
                            HStack {
                                Text(guardian.displayName)
                                if guardian.createdByAudit {
                                    Text("created account")
                                        .font(.caption2)
                                        .foregroundStyle(Theme.ink)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(Theme.childBubble)
                                        .clipShape(Capsule())
                                }
                                Spacer()
                            }
                        }
                        Button("Invite another guardian") { Task { await invite() } }
                            .disabled(busy)
                        if let inviteCode {
                            Text("Share this code once: \(inviteCode)")
                                .font(.headline)
                                .textSelection(.enabled)
                                .accessibilityLabel("Invitation code \(inviteCode)")
                        }
                        if invites.contains(where: { $0.status == "pending_confirmation" }) {
                            FieldLabel(title: "Your password to confirm", text: $password, secure: true)
                            ForEach(invites.filter { $0.status == "pending_confirmation" }) { invite in
                                Button("Confirm \(invite.acceptedByDisplayName ?? "guardian")") {
                                    Task { await confirm(invite) }
                                }
                            }
                        }
                    }
                }
            }
            .padding(.vertical, 8)
            }
            .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))
            .listRowBackground(Theme.cream)
            .listRowSeparator(.hidden)

            Section {
                if conversations.isEmpty {
                    Text("No conversations yet.")
                        .foregroundStyle(Theme.ink.opacity(0.7))
                        .listRowBackground(Theme.cream)
                }
                ForEach(visibleConversations) { conversation in
                    conversationRow(conversation)
                        .id(conversation.id)
                        .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))
                        .listRowBackground(Theme.cream)
                        .listRowSeparator(.hidden)
                        .swipeActions(edge: .leading, allowsFullSwipe: false) {
                            Button("Delete", role: .destructive) {
                                Task { await delete(conversation) }
                            }
                        }
                }
                if visibleCount < conversations.count {
                    Button("Show more") { visibleCount += 5 }
                        .foregroundStyle(Theme.ink)
                        .listRowBackground(Theme.cream)
                }
            } header: {
                Text("Conversations")
                    .foregroundStyle(Theme.ink)
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .background(Theme.cream)
        .kinwiseForm()
        .navigationTitle(pageTitle.isEmpty ? name : pageTitle)
        .task { await load() }
        .onChange(of: expandedID) { _, id in
            guard let id, id == focusConversationID else { return }
            DispatchQueue.main.async {
                withAnimation { proxy.scrollTo(id, anchor: .top) }
            }
        }
        }
    }

    private func conversationRow(_ conversation: ConversationSummary) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Button {
                Task { await toggle(conversation) }
            } label: {
                HStack(alignment: .top, spacing: 10) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(conversation.title).font(.headline).foregroundStyle(Theme.ink)
                        if conversation.ended {
                            Text("Closed")
                                .font(.caption.weight(.semibold))
                                .italic()
                                .foregroundStyle(Theme.ink.opacity(0.7))
                        }
                        Text(conversation.summary ?? "No summary")
                            .font(.subheadline)
                            .foregroundStyle(Theme.ink.opacity(0.7))
                            .lineLimit(2)
                    }
                    Spacer(minLength: 8)
                    Image(systemName: expandedID == conversation.id ? "chevron.up" : "chevron.down")
                        .foregroundStyle(Theme.ink.opacity(0.7))
                        .accessibilityHidden(true)
                }
            }
            .buttonStyle(.plain)
            .accessibilityLabel(expandedID == conversation.id ? "Hide messages" : "Show messages")
            if expandedID == conversation.id {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 8) {
                            if conversation.ended {
                                Text("This conversation is closed. The child cannot send more messages here.")
                                    .font(.footnote)
                                    .italic()
                                    .foregroundStyle(Theme.ink.opacity(0.75))
                            }
                            if let messages = transcripts[conversation.id] {
                                if messages.isEmpty {
                                    Text("No messages.").font(.footnote).foregroundStyle(Theme.ink.opacity(0.7))
                                }
                                ForEach(messages) { message in
                                    VStack(alignment: .leading, spacing: 4) {
                                        MessageBubble(message: ChatMessage(
                                            id: message.id,
                                            senderRole: message.senderRole,
                                            content: message.content,
                                            restricted: false,
                                            childFacingText: nil,
                                            createdAt: message.createdAt
                                        ))
                                        if let hidden = message.childFacingText {
                                            Text("Child sees: \(hidden)")
                                                .font(.footnote)
                                                .italic()
                                                .foregroundStyle(Theme.ink.opacity(0.75))
                                        }
                                    }
                                    .id(message.id)
                                    .padding(message.id == focusMessageID ? 6 : 0)
                                    .background(
                                        message.id == focusMessageID ? Theme.caution.opacity(0.35) : Color.clear,
                                        in: RoundedRectangle(cornerRadius: 12, style: .continuous)
                                    )
                                }
                            } else {
                                ProgressView()
                            }
                        }
                    }
                    .frame(maxHeight: 220)
                    .onAppear { scrollToFocusedMessage(proxy, conversation: conversation) }
                    .onChange(of: transcripts[conversation.id]?.count ?? 0) { _, _ in
                        scrollToFocusedMessage(proxy, conversation: conversation)
                    }
                }
            }
        }
        .padding(12)
        .background(Theme.card)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private func load() async {
        do {
            let token = try session.token()
            overview = try await session.api.overview(token: token, childID: childID)
            conversations = try await session.api.guardianConversations(token: token, childID: childID)
            guardians = try await session.api.guardians(token: token, childID: childID)
            invites = try await session.api.pendingInvites(token: token, childID: childID)
            if let child = overview?.child {
                displayName = child.displayName
                ageBand = child.ageBand
                pageTitle = child.displayName
            }
            error = nil
            await revealFocusedConversation()
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func revealFocusedConversation() async {
        guard !didOpenFocus, let target = focusConversationID else { return }
        didOpenFocus = true
        guard let index = conversations.firstIndex(where: { $0.id == target }) else { return }
        visibleCount = max(visibleCount, index + 1)
        expandedID = target
        guard transcripts[target] == nil else { return }
        do {
            transcripts[target] = try await session.api.guardianMessages(
                token: try session.token(),
                childID: childID,
                conversationID: target
            )
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
            expandedID = nil
        }
    }

    private func scrollToFocusedMessage(_ proxy: ScrollViewProxy, conversation: ConversationSummary) {
        guard conversation.id == focusConversationID, let focusMessageID else { return }
        DispatchQueue.main.async {
            withAnimation { proxy.scrollTo(focusMessageID, anchor: .center) }
        }
    }

    private func toggle(paused: Bool) async {
        do {
            let token = try session.token()
            if paused {
                _ = try await session.api.resume(token: token, childID: childID)
            } else {
                _ = try await session.api.pause(token: token, childID: childID)
            }
            await load()
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func saveName() async {
        guard nameChanged else { return }
        let keptAge = ageBand
        busy = true
        defer { busy = false }
        do {
            _ = try await session.api.updateChildSettings(
                token: try session.token(),
                childID: childID,
                displayName: trimmedName
            )
            await load()
            ageBand = keptAge
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func saveAge() async {
        guard ageChanged else { return }
        let keptName = displayName
        busy = true
        defer { busy = false }
        do {
            _ = try await session.api.updateChildSettings(
                token: try session.token(),
                childID: childID,
                ageBand: ageBand
            )
            await load()
            displayName = keptName
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func invite() async {
        busy = true
        defer { busy = false }
        do {
            let created = try await session.api.invite(token: try session.token(), childID: childID)
            inviteCode = created.code
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func resetPassword() async {
        do {
            try await session.api.resetChildPassword(
                token: try session.token(),
                childID: childID,
                currentPassword: password,
                newPassword: newChildPassword
            )
            password = ""
            newChildPassword = ""
            error = nil
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func confirm(_ invite: InvitationPending) async {
        do {
            try await session.api.confirmInvite(token: try session.token(), invitationID: invite.invitationId, password: password)
            password = ""
            await load()
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func toggle(_ conversation: ConversationSummary) async {
        if expandedID == conversation.id {
            expandedID = nil
            return
        }
        expandedID = conversation.id
        guard transcripts[conversation.id] == nil else { return }
        do {
            transcripts[conversation.id] = try await session.api.guardianMessages(
                token: try session.token(),
                childID: childID,
                conversationID: conversation.id
            )
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
            expandedID = nil
        }
    }

    private func delete(_ conversation: ConversationSummary) async {
        do {
            try await session.api.deleteConversation(token: try session.token(), childID: childID, conversationID: conversation.id)
            conversations.removeAll { $0.id == conversation.id }
            transcripts[conversation.id] = nil
            if expandedID == conversation.id { expandedID = nil }
            error = nil
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }
}
