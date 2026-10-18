import SwiftUI

struct SafetyCenterView: View {
    @Environment(SessionStore.self) private var session
    @State private var children: [ChildListItem] = []
    @State private var rows: [(ChildListItem, SafetyEventItem)] = []
    @State private var selectedChildID: UUID?
    @State private var visibleCount = 5
    @State private var error: String?
    @State private var busy = false

    private var selectedChild: ChildListItem? {
        if let selectedChildID, let match = children.first(where: { $0.id == selectedChildID }) {
            return match
        }
        return children.first
    }

    private var selectedEvents: [(ChildListItem, SafetyEventItem)] {
        guard let selectedChild else { return [] }
        return rows.filter { $0.0.id == selectedChild.id }
    }

    private var visibleEvents: [(ChildListItem, SafetyEventItem)] {
        Array(selectedEvents.prefix(visibleCount))
    }

    var body: some View {
        let pending = SafetyNavigation.shared.target
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("Safety events are saved by the server. High and critical events send a text and a phone alert. The text does not include the child's words. Tap an event to open that conversation.")
                        .font(.subheadline)
                        .foregroundStyle(Theme.ink.opacity(0.75))
                    if let error { ErrorBanner(message: error) }
                    if children.isEmpty {
                        KinwiseCard { Text("No children yet.").foregroundStyle(Theme.ink) }
                    } else {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(children) { child in
                                    let selected = child.id == selectedChild?.id
                                    Button(child.displayName) {
                                        selectedChildID = child.id
                                        visibleCount = 5
                                    }
                                        .font(.headline)
                                        .padding(.horizontal, 14)
                                        .padding(.vertical, 10)
                                        .foregroundStyle(Theme.ink)
                                        .background(selected ? Theme.blue : Theme.card)
                                        .clipShape(Capsule())
                                        .overlay(Capsule().stroke(Theme.line, lineWidth: 1))
                                        .accessibilityAddTraits(selected ? .isSelected : [])
                                }
                            }
                        }
                        if let child = selectedChild {
                            KinwiseCard {
                                VStack(alignment: .leading, spacing: 10) {
                                    HStack {
                                        Text(child.displayName).font(.kinwiseHeadline)
                                        Spacer()
                                        StatusPill(paused: child.isPaused)
                                    }
                                    Button(child.isPaused ? "Resume Kinwise" : "Pause Kinwise") {
                                        Task { await togglePause(child) }
                                    }
                                    .buttonStyle(.borderedProminent)
                                    .controlSize(.large)
                                    .tint(child.isPaused ? Theme.mint : Theme.blue)
                                    .disabled(busy)
                                    .accessibilityLabel(child.isPaused ? "Resume \(child.displayName)" : "Pause \(child.displayName)")
                                }
                            }
                        }
                        if selectedEvents.isEmpty {
                            KinwiseCard { Text("No safety events yet.").foregroundStyle(Theme.ink) }
                        }
                        ForEach(visibleEvents, id: \.1.id) { child, event in
                            KinwiseCard {
                                VStack(alignment: .leading, spacing: 6) {
                                    if let conversationID = event.conversationId {
                                        NavigationLink {
                                            ChildDetailView(
                                                childID: child.id,
                                                name: child.displayName,
                                                focusConversationID: conversationID,
                                                focusMessageID: event.messageId
                                            )
                                        } label: {
                                            eventSummary(event)
                                        }
                                        .buttonStyle(.plain)
                                    } else {
                                        eventSummary(event)
                                    }
                                    if event.resolutionStatus != "acknowledged" {
                                        Button("Acknowledge") { Task { await acknowledge(event) } }
                                            .buttonStyle(.bordered)
                                    } else {
                                        Text("Acknowledged").font(.caption).foregroundStyle(Theme.ink.opacity(0.6))
                                    }
                                }
                            }
                        }
                        if visibleCount < selectedEvents.count {
                            Button("Show more") { visibleCount += 5 }
                                .font(.headline)
                                .foregroundStyle(Theme.ink)
                        }
                    }
                }
                .padding(20)
            }
            .background(Theme.cream)
            .navigationTitle("Safety")
            .task { await load() }
            .refreshable { await load() }
            .onAppear { openBanner(pending) }
            .onChange(of: pending?.eventID) { _, _ in openBanner(SafetyNavigation.shared.target) }
        }
    }

    private func openBanner(_ target: SafetyBannerTarget?) {
        guard let target else { return }
        selectedChildID = target.childID
        visibleCount = 5
        SafetyNavigation.shared.target = nil
    }

    private func eventSummary(_ event: SafetyEventItem) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("\(event.severity) · \(event.category.replacingOccurrences(of: "_", with: " "))")
                    .font(.headline)
                    .foregroundStyle(Theme.ink)
                Spacer()
                if event.conversationId != nil {
                    Image(systemName: "chevron.right")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Theme.ink.opacity(0.55))
                        .accessibilityHidden(true)
                }
            }
            Text(event.summary)
                .foregroundStyle(Theme.ink)
            Text(event.recommendedAction)
                .font(.footnote)
                .foregroundStyle(Theme.ink.opacity(0.75))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
    }

    private func load() async {
        do {
            let token = try session.token()
            let loaded = try await session.api.children(token: token)
            var combined: [(ChildListItem, SafetyEventItem)] = []
            for child in loaded {
                let events = try await session.api.safetyEvents(token: token, childID: child.id)
                combined.append(contentsOf: events.map { (child, $0) })
            }
            children = loaded
            rows = combined.sorted { $0.1.createdAt > $1.1.createdAt }
            if selectedChildID == nil || !loaded.contains(where: { $0.id == selectedChildID }) {
                selectedChildID = loaded.first?.id
            }
            error = nil
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func togglePause(_ child: ChildListItem) async {
        busy = true
        defer { busy = false }
        do {
            let token = try session.token()
            if child.isPaused {
                _ = try await session.api.resume(token: token, childID: child.id)
            } else {
                _ = try await session.api.pause(token: token, childID: child.id)
            }
            await load()
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func acknowledge(_ event: SafetyEventItem) async {
        do {
            _ = try await session.api.acknowledge(token: try session.token(), eventID: event.id)
            await load()
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }
}
