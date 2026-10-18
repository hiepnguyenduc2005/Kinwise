import SwiftUI

struct WelcomeView: View {
    @State private var mode: AuthMode?

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.cream.ignoresSafeArea()
                VStack(spacing: 28) {
                    Spacer()
                    VStack(spacing: 10) {
                        Image(systemName: "sparkles")
                            .font(.system(size: 42))
                            .foregroundStyle(Theme.lavender)
                            .accessibilityHidden(true)
                        Text("Kinwise")
                            .font(.kinwiseTitle)
                            .foregroundStyle(Theme.ink)
                        Text("Curiosity, with care.")
                            .font(.title3)
                            .foregroundStyle(Theme.ink.opacity(0.75))
                    }
                    KinwiseCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("A learning companion for children, with guardians close by.")
                                .font(.body)
                                .foregroundStyle(Theme.ink)
                            Text("Ordinary conversations are visible to linked guardians. Kinwise does not claim to be a complete safety system.")
                                .font(.footnote)
                                .foregroundStyle(Theme.ink.opacity(0.7))
                        }
                    }
                    .padding(.horizontal, 24)
                    VStack(spacing: 12) {
                        PrimaryButton(title: "I'm a guardian") { mode = .guardian }
                        Button("I'm a child") { mode = .child }
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(Theme.secondaryFill)
                            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                            .foregroundStyle(Theme.ink)
                    }
                    .padding(.horizontal, 24)
                    Spacer()
                }
            }
            .navigationDestination(item: $mode) { selected in
                switch selected {
                case .guardian:
                    GuardianAuthView()
                case .child:
                    ChildLoginView()
                }
            }
        }
    }
}

enum AuthMode: String, Identifiable, Hashable {
    case guardian, child
    var id: String { rawValue }
}

struct GuardianAuthView: View {
    @Environment(SessionStore.self) private var session
    @State private var email = ""
    @State private var password = ""
    @State private var name = ""
    @State private var registering = false
    @State private var busy = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(registering ? "Create a guardian account" : "Guardian sign in")
                    .font(.kinwiseHeadline)
                if let error = session.lastError { ErrorBanner(message: error) }
                if registering {
                    FieldLabel(title: "Name", text: $name)
                }
                FieldLabel(title: "Email", text: $email, keyboard: .emailAddress)
                FieldLabel(title: "Password", text: $password, secure: true)
                PrimaryButton(title: registering ? "Create account" : "Sign in", isLoading: busy) {
                    Task {
                        busy = true
                        if registering {
                            await session.registerGuardian(email: email, password: password, displayName: name)
                        } else {
                            await session.signInGuardian(email: email, password: password)
                        }
                        busy = false
                    }
                }
                Button(registering ? "I already have an account" : "Create a guardian account") {
                    registering.toggle()
                }
                .font(.subheadline.weight(.semibold))
            }
            .padding(24)
        }
        .background(Theme.cream)
        .kinwiseForm()
        .navigationTitle("Guardian")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct ChildLoginView: View {
    @Environment(SessionStore.self) private var session
    @State private var username = ""
    @State private var password = ""
    @State private var busy = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("A guardian creates your username. You sign in with that username and password.")
                    .font(.body)
                    .foregroundStyle(Theme.ink)
                if let error = session.lastError { ErrorBanner(message: error) }
                FieldLabel(title: "Username", text: $username)
                FieldLabel(title: "Password", text: $password, secure: true)
                PrimaryButton(title: "Sign in", isLoading: busy) {
                    Task {
                        busy = true
                        await session.signInChild(username: username, password: password)
                        busy = false
                    }
                }
            }
            .padding(24)
        }
        .background(Theme.cream)
        .kinwiseForm()
        .navigationTitle("Child")
        .navigationBarTitleDisplayMode(.inline)
    }
}
