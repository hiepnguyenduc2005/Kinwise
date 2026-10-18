import SwiftUI

struct ChildTabView: View {
    @Environment(SessionStore.self) private var session
    @State private var socket = AccessSocket()

    var body: some View {
        TabView {
            ConversationsView()
                .tabItem { Label("Chats", systemImage: "bubble.left.and.bubble.right") }
            ChildProfileView()
                .tabItem { Label("Me", systemImage: "person.crop.circle") }
        }
        .task {
            await session.refreshAccess()
            guard let token = session.accessToken else { return }
            socket.connect(baseURL: session.api.baseURL, token: token) { event in
                session.applySocket(event)
            }
        }
        .onDisappear { socket.disconnect() }
    }
}
