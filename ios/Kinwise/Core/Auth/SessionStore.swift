import Foundation
import Observation

@MainActor
@Observable
final class SessionStore {
    var user: UserAccount?
    var accessToken: String?
    var isRestoring = true
    var access = AccessState(isPaused: false, stateVersion: 0, updatedAt: .distantPast)
    var lastError: String?

    let api = APIClient.live()
    private let keychain = KeychainStore()
    private let refreshKey = "refresh_token"

    func restore() async {
        guard isRestoring else { return }
        defer { isRestoring = false }
        guard let refreshToken = keychain.read(key: refreshKey) else { return }
        do {
            let tokens = try await api.refresh(refreshToken: refreshToken)
            apply(tokens)
            if user?.role == "child" {
                await refreshAccess()
            }
        } catch {
            clear()
        }
    }

    func signInGuardian(email: String, password: String) async {
        await perform {
            let tokens = try await api.login(email: email, password: password)
            apply(tokens)
        }
    }

    func registerGuardian(email: String, password: String, displayName: String) async {
        await perform {
            let tokens = try await api.registerGuardian(email: email, password: password, displayName: displayName)
            apply(tokens)
        }
    }

    func signInChild(username: String, password: String) async {
        await perform {
            let tokens = try await api.login(username: username, password: password)
            apply(tokens)
            await refreshAccess()
        }
    }

    func refreshAccess() async {
        guard let token = accessToken, user?.role == "child" else { return }
        do {
            let latest = try await api.childAccess(token: token)
            if latest.stateVersion >= access.stateVersion {
                access = latest
            }
        } catch {
            lastError = (error as? LocalizedError)?.errorDescription
        }
    }

    func applySocket(_ event: AccessSocketEvent) {
        guard event.stateVersion >= access.stateVersion else { return }
        access = AccessState(isPaused: event.isPaused, stateVersion: event.stateVersion, updatedAt: event.updatedAt)
    }

    func logout() async {
        if user?.role == "child", access.isPaused {
            lastError = "Sign out is off while Kinwise is paused."
            return
        }
        if let refreshToken = keychain.read(key: refreshKey) {
            try? await api.logout(refreshToken: refreshToken)
        }
        clear()
    }

    func token() throws -> String {
        guard let accessToken else {
            throw APIFailure(status: 401, code: "unauthorized", message: "Sign in to continue.")
        }
        return accessToken
    }

    private func perform(_ work: () async throws -> Void) async {
        lastError = nil
        do {
            try await work()
        } catch {
            lastError = (error as? LocalizedError)?.errorDescription ?? "Kinwise could not complete that."
        }
    }

    private func apply(_ tokens: TokenResponse) {
        accessToken = tokens.accessToken
        user = tokens.user
        keychain.save(key: refreshKey, value: tokens.refreshToken)
        lastError = nil
    }

    private func clear() {
        accessToken = nil
        user = nil
        access = AccessState(isPaused: false, stateVersion: 0, updatedAt: .distantPast)
        keychain.delete(key: refreshKey)
    }
}
