import SwiftUI

struct ChildrenView: View {
    @Environment(SessionStore.self) private var session
    @State private var children: [ChildListItem] = []
    @State private var showingCreate = false
    @State private var inviteCode = ""
    @State private var error: String?
    @State private var notice: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if let error { ErrorBanner(message: error) }
                    if let notice { Text(notice).font(.subheadline).foregroundStyle(Theme.ink) }
                    KinwiseCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Accept an invitation").font(.headline)
                            FieldLabel(title: "Invitation code", text: $inviteCode)
                            Button("Accept code") { Task { await accept() } }
                                .buttonStyle(.bordered)
                        }
                    }
                    ForEach(children) { child in
                        NavigationLink {
                            ChildDetailView(childID: child.id, name: child.displayName)
                        } label: {
                            KinwiseCard {
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text(child.displayName).font(.headline).foregroundStyle(Theme.ink)
                                        Text("@\(child.username) · ages \(child.ageBand)")
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
            .kinwiseForm()
            .navigationTitle("Children")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Add") { showingCreate = true }
                        .accessibilityLabel("Create child account")
                }
            }
            .sheet(isPresented: $showingCreate) {
                CreateChildView { showingCreate = false; Task { await load() } }
            }
            .task { await load() }
            .refreshable { await load() }
        }
    }

    private func load() async {
        do {
            children = try await session.api.children(token: try session.token())
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func accept() async {
        do {
            let accepted = try await session.api.acceptInvite(token: try session.token(), code: inviteCode)
            notice = "Invitation \(accepted.status.replacingOccurrences(of: "_", with: " ")). The inviting guardian still needs to confirm."
            inviteCode = ""
            error = nil
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }
}

struct CreateChildView: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss
    var onCreated: () -> Void
    @State private var name = ""
    @State private var username = ""
    @State private var password = ""
    @State private var ageBand = "9-11"
    @State private var error: String?
    @State private var createdPassword: String?
    @State private var busy = false
    private let bands = ["6-8", "9-11", "12-14", "15-17"]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("The password is shown once on this device. Kinwise stores only a hash.")
                        .font(.subheadline)
                        .foregroundStyle(Theme.ink.opacity(0.75))
                    if let error { ErrorBanner(message: error) }
                    if let createdPassword {
                        KinwiseCard {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("Share these credentials now.")
                                    .font(.headline)
                                Text("Username \(username)")
                                Text("Password \(createdPassword)")
                                    .textSelection(.enabled)
                            }
                        }
                    } else {
                        FieldLabel(title: "Display name", text: $name)
                        FieldLabel(title: "Username", text: $username)
                        FieldLabel(title: "Password", text: $password, secure: true)
                        Picker("Age band", selection: $ageBand) {
                            ForEach(bands, id: \.self) { Text($0).tag($0) }
                        }
                        .pickerStyle(.segmented)
                        PrimaryButton(title: "Create child", isLoading: busy) { Task { await create() } }
                    }
                }
                .padding(20)
            }
            .background(Theme.cream)
            .kinwiseForm()
            .navigationTitle("New child")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { onCreated(); dismiss() }
                }
            }
        }
    }

    private func create() async {
        busy = true
        defer { busy = false }
        do {
            _ = try await session.api.createChild(
                token: try session.token(),
                username: username,
                password: password,
                displayName: name,
                ageBand: ageBand
            )
            createdPassword = password
            password = ""
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }
}
