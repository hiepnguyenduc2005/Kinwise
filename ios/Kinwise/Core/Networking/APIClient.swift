import Foundation

struct APIFailure: Error, LocalizedError {
    let status: Int
    let code: String
    let message: String
    var errorDescription: String? { message }
}

struct APIClient: Sendable {
    let baseURL: URL
    private let session: URLSession

    init(baseURL: URL) {
        self.baseURL = baseURL
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        self.session = URLSession(configuration: configuration)
    }

    static func live() -> APIClient {
        let raw = Bundle.main.object(forInfoDictionaryKey: "KINWISE_API_BASE_URL") as? String ?? "http://127.0.0.1:8000"
        return APIClient(baseURL: URL(string: raw) ?? URL(string: "http://127.0.0.1:8000")!)
    }

    func registerGuardian(email: String, password: String, displayName: String) async throws -> TokenResponse {
        try await send("POST", "/api/v1/auth/guardian/register", token: nil, body: [
            "email": email, "password": password, "display_name": displayName,
        ])
    }

    func login(email: String? = nil, username: String? = nil, password: String) async throws -> TokenResponse {
        var body: [String: String] = ["password": password]
        if let email { body["email"] = email }
        if let username { body["username"] = username }
        return try await send("POST", "/api/v1/auth/login", token: nil, body: body)
    }

    func refresh(refreshToken: String) async throws -> TokenResponse {
        try await send("POST", "/api/v1/auth/refresh", token: nil, body: ["refresh_token": refreshToken])
    }

    func logout(refreshToken: String) async throws {
        let _: StatusResponse = try await send("POST", "/api/v1/auth/logout", token: nil, body: ["refresh_token": refreshToken])
    }

    func me(token: String) async throws -> UserAccount {
        try await send("GET", "/api/v1/auth/me", token: token, body: Optional<[String: String]>.none)
    }

    func updateProfile(token: String, displayName: String) async throws -> UserAccount {
        try await send("PATCH", "/api/v1/auth/me", token: token, body: ["display_name": displayName])
    }

    func childMe(token: String) async throws -> ChildMe {
        try await send("GET", "/api/v1/children/me", token: token, body: Optional<[String: String]>.none)
    }

    func childAccess(token: String) async throws -> AccessState {
        try await send("GET", "/api/v1/children/me/access", token: token, body: Optional<[String: String]>.none)
    }

    func conversations(token: String) async throws -> [ConversationSummary] {
        try await send("GET", "/api/v1/conversations/", token: token, body: Optional<[String: String]>.none)
    }

    func createConversation(token: String) async throws -> ConversationSummary {
        try await send("POST", "/api/v1/conversations/", token: token, body: [String: String]())
    }

    func messages(token: String, conversationID: UUID) async throws -> [ChatMessage] {
        try await send("GET", "/api/v1/conversations/\(conversationID.uuidString)/messages", token: token, body: Optional<[String: String]>.none)
    }

    func sendMessage(token: String, conversationID: UUID, content: String) async throws -> SendMessageResponse {
        try await send(
            "POST",
            "/api/v1/conversations/\(conversationID.uuidString)/messages",
            token: token,
            body: ["content": content]
        )
    }

    func children(token: String) async throws -> [ChildListItem] {
        try await send("GET", "/api/v1/guardian/children", token: token, body: Optional<[String: String]>.none)
    }

    func updateChildSettings(token: String, childID: UUID, displayName: String? = nil, ageBand: String? = nil) async throws -> ChildProfileResponse {
        var body: [String: String] = [:]
        if let displayName { body["display_name"] = displayName }
        if let ageBand { body["age_band"] = ageBand }
        return try await send(
            "PATCH",
            "/api/v1/guardian/children/\(childID.uuidString)/settings",
            token: token,
            body: body
        )
    }

    func createChild(token: String, username: String, password: String, displayName: String, ageBand: String) async throws -> ChildProfileResponse {
        try await send("POST", "/api/v1/guardian/children", token: token, body: [
            "username": username, "password": password, "display_name": displayName, "age_band": ageBand,
        ])
    }

    func overview(token: String, childID: UUID) async throws -> ChildOverview {
        try await send("GET", "/api/v1/guardian/children/\(childID.uuidString)/overview", token: token, body: Optional<[String: String]>.none)
    }

    func guardianConversations(token: String, childID: UUID) async throws -> [ConversationSummary] {
        try await send(
            "GET",
            "/api/v1/guardian/children/\(childID.uuidString)/conversations",
            token: token,
            body: Optional<[String: String]>.none
        )
    }

    func deleteConversation(token: String, childID: UUID, conversationID: UUID) async throws {
        let _: StatusResponse = try await send(
            "DELETE",
            "/api/v1/guardian/children/\(childID.uuidString)/conversations/\(conversationID.uuidString)",
            token: token,
            body: Optional<[String: String]>.none
        )
    }

    func guardianMessages(token: String, childID: UUID, conversationID: UUID) async throws -> [ChatMessage] {
        try await send(
            "GET",
            "/api/v1/guardian/children/\(childID.uuidString)/conversations/\(conversationID.uuidString)/messages",
            token: token,
            body: Optional<[String: String]>.none
        )
    }

    func safetyEvents(token: String, childID: UUID) async throws -> [SafetyEventItem] {
        try await send("GET", "/api/v1/guardian/children/\(childID.uuidString)/safety-events", token: token, body: Optional<[String: String]>.none)
    }

    func acknowledge(token: String, eventID: UUID) async throws -> SafetyEventItem {
        try await send("POST", "/api/v1/guardian/safety-events/\(eventID.uuidString)/acknowledge", token: token, body: [String: String]())
    }

    func pause(token: String, childID: UUID) async throws -> AccessState {
        try await send("POST", "/api/v1/guardian/children/\(childID.uuidString)/pause", token: token, body: [String: String]())
    }

    func resume(token: String, childID: UUID) async throws -> AccessState {
        try await send("POST", "/api/v1/guardian/children/\(childID.uuidString)/resume", token: token, body: [String: String]())
    }

    func invite(token: String, childID: UUID) async throws -> InvitationCreated {
        try await send("POST", "/api/v1/guardian/children/\(childID.uuidString)/invitations", token: token, body: [String: String]())
    }

    func acceptInvite(token: String, code: String) async throws -> InvitationAccepted {
        try await send("POST", "/api/v1/guardian/invitations/accept", token: token, body: ["code": code])
    }

    func confirmInvite(token: String, invitationID: UUID, password: String) async throws {
        let _: StatusResponse = try await send(
            "POST",
            "/api/v1/guardian/invitations/\(invitationID.uuidString)/confirm",
            token: token,
            body: ["current_password": password]
        )
    }

    func pendingInvites(token: String, childID: UUID) async throws -> [InvitationPending] {
        try await send("GET", "/api/v1/guardian/children/\(childID.uuidString)/invitations", token: token, body: Optional<[String: String]>.none)
    }

    func guardians(token: String, childID: UUID) async throws -> [GuardianLink] {
        try await send("GET", "/api/v1/guardian/children/\(childID.uuidString)/guardians", token: token, body: Optional<[String: String]>.none)
    }

    func removeGuardian(token: String, childID: UUID, guardianID: UUID, password: String) async throws {
        let _: StatusResponse = try await send(
            "DELETE",
            "/api/v1/guardian/children/\(childID.uuidString)/guardians/\(guardianID.uuidString)",
            token: token,
            body: ["current_password": password]
        )
    }

    func savePhone(token: String, phone: String) async throws -> PhoneStatus {
        try await send("PATCH", "/api/v1/guardian/phone", token: token, body: PhoneBody(phone: phone.isEmpty ? nil : phone))
    }

    func phone(token: String) async throws -> PhoneStatus {
        try await send("GET", "/api/v1/guardian/phone", token: token, body: Optional<[String: String]>.none)
    }

    func phonePreferences(token: String, messagingEnabled: Bool, photonSpaceID: String?) async throws -> PhoneStatus {
        try await send(
            "PATCH",
            "/api/v1/guardian/phone/preferences",
            token: token,
            body: PhonePrefsBody(messagingEnabled: messagingEnabled, photonSpaceId: photonSpaceID)
        )
    }

    func resetChildPassword(token: String, childID: UUID, currentPassword: String, newPassword: String) async throws {
        let _: StatusResponse = try await send(
            "POST",
            "/api/v1/guardian/children/\(childID.uuidString)/credentials",
            token: token,
            body: ["current_password": currentPassword, "new_password": newPassword]
        )
    }

    private func send<T: Decodable, Body: Encodable>(
        _ method: String,
        _ path: String,
        token: String?,
        body: Body?
    ) async throws -> T {
        guard let url = URL(string: baseURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + path) else {
            throw APIFailure(status: 0, code: "network", message: "The API address is invalid.")
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            let encoder = JSONEncoder()
            encoder.keyEncodingStrategy = .convertToSnakeCase
            request.httpBody = try encoder.encode(body)
        }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw APIFailure(status: 0, code: "network", message: "The server did not respond.")
        }
        if !(200..<300).contains(http.statusCode) {
            throw decodeFailure(data: data, status: http.statusCode)
        }
        if T.self == StatusResponse.self, data.isEmpty {
            return StatusResponse(status: "ok") as! T
        }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom(decodeAPIDate)
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIFailure(status: http.statusCode, code: "decode", message: "Kinwise received an unexpected response.")
        }
    }

    private func decodeFailure(data: Data, status: Int) -> APIFailure {
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let detail = object["detail"] as? [String: Any],
           let message = detail["message"] as? String {
            return APIFailure(status: status, code: detail["code"] as? String ?? "error", message: message)
        }
        return APIFailure(status: status, code: "error", message: "Something went wrong (\(status)).")
    }
}

private struct PhoneBody: Encodable {
    var phone: String?
}

private struct PhonePrefsBody: Encodable {
    var messagingEnabled: Bool
    var photonSpaceId: String?
}

private func decodeAPIDate(_ decoder: Decoder) throws -> Date {
    let container = try decoder.singleValueContainer()
    let value = try container.decode(String.self)
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    if let date = formatter.date(from: value) { return date }
    formatter.formatOptions = [.withInternetDateTime]
    if let date = formatter.date(from: value) { return date }
    throw DecodingError.dataCorruptedError(in: container, debugDescription: value)
}
