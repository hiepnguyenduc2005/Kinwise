import SwiftUI

struct SettingsView: View {
    @Environment(SessionStore.self) private var session
    @State private var displayName = ""
    @State private var phone = ""
    @State private var spaceID = ""
    @State private var messaging = false
    @State private var status: PhoneStatus?
    @State private var error: String?
    @State private var notice: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text(session.user?.email ?? "")
                        .font(.subheadline)
                        .foregroundStyle(Theme.ink.opacity(0.7))
                    if let error { ErrorBanner(message: error) }
                    if let notice { Text(notice).font(.subheadline) }
                    KinwiseCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Profile").font(.headline)
                            FieldLabel(title: "Display name", text: $displayName)
                            Button("Save name") { Task { await saveName() } }
                                .buttonStyle(.bordered)
                        }
                    }
                    KinwiseCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Phone notifications").font(.headline)
                            Text("Save the phone you text the Kinwise iMessage line from. Add that same number under Spectrum users. Saving the number turns messaging on. Kinwise also shows an alert on this phone.")
                                .font(.footnote)
                                .foregroundStyle(Theme.ink.opacity(0.75))
                            FieldLabel(title: "Phone number", text: $phone, keyboard: .phonePad)
                            Button("Save phone") { Task { await savePhone() } }
                                .buttonStyle(.bordered)
                            Toggle("Photon messaging", isOn: $messaging)
                                .disabled((status?.phone ?? "").isEmpty)
                            FieldLabel(title: "Conversation id (optional, filled after you text)", text: $spaceID)
                            Button("Save messaging") { Task { await saveMessaging() } }
                                .buttonStyle(.bordered)
                        }
                    }
                    Text("Email verification and email password recovery are not connected. There is no email delivery provider in this build. Guardians can reset a child's password from the child screen after signing in again with their own password.")
                        .font(.footnote)
                        .foregroundStyle(Theme.ink.opacity(0.7))
                    Button("Sign out", role: .destructive) { Task { await session.logout() } }
                }
                .padding(20)
            }
            .background(Theme.cream)
            .kinwiseForm()
            .navigationTitle("Settings")
            .task { await load() }
        }
    }

    private func load() async {
        displayName = session.user?.displayName ?? ""
        do {
            status = try await session.api.phone(token: try session.token())
            messaging = status?.messagingEnabled ?? false
            spaceID = status?.photonSpaceId ?? ""
            if phone.isEmpty { phone = status?.phone ?? "" }
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func saveName() async {
        do {
            let user = try await session.api.updateProfile(token: try session.token(), displayName: displayName)
            session.user = user
            notice = "Name saved."
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func savePhone() async {
        do {
            status = try await session.api.savePhone(token: try session.token(), phone: phone)
            phone = status?.phone ?? ""
            messaging = status?.messagingEnabled ?? false
            notice = phone.isEmpty ? "Phone cleared." : "Phone saved."
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }

    private func saveMessaging() async {
        do {
            status = try await session.api.phonePreferences(
                token: try session.token(),
                messagingEnabled: messaging,
                photonSpaceID: spaceID
            )
            notice = "Messaging preferences saved."
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription
        }
    }
}
