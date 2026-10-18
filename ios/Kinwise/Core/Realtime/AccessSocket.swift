import Foundation

@MainActor
final class AccessSocket {
    private let session = URLSession(configuration: .default)
    private var task: URLSessionWebSocketTask?
    private var onEvent: ((AccessSocketEvent) -> Void)?

    func connect(baseURL: URL, token: String, onEvent: @escaping (AccessSocketEvent) -> Void) {
        disconnect()
        self.onEvent = onEvent
        let root = baseURL.absoluteString
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            .replacingOccurrences(of: "https://", with: "wss://")
            .replacingOccurrences(of: "http://", with: "ws://")
        guard let url = URL(string: root + "/api/v1/realtime/child-access") else { return }
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let socket = session.webSocketTask(with: request)
        task = socket
        socket.resume()
        listen(socket)
    }

    func disconnect() {
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        onEvent = nil
    }

    nonisolated private func listen(_ socket: URLSessionWebSocketTask) {
        socket.receive { [weak self] result in
            guard let self else { return }
            if case .success(let message) = result {
                if case .string(let text) = message, let event = Self.decode(text) {
                    Task { @MainActor in
                        self.onEvent?(event)
                    }
                }
                self.listen(socket)
            }
        }
    }

    nonisolated private static func decode(_ text: String) -> AccessSocketEvent? {
        guard let data = text.data(using: .utf8) else { return nil }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let value = try container.decode(String.self)
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: value) { return date }
            formatter.formatOptions = [.withInternetDateTime]
            if let date = formatter.date(from: value) { return date }
            throw DecodingError.dataCorruptedError(in: container, debugDescription: value)
        }
        return try? decoder.decode(AccessSocketEvent.self, from: data)
    }
}
