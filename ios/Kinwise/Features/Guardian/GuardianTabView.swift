import SwiftUI
import UserNotifications

struct SafetyBannerTarget: Hashable {
    let eventID: UUID
    let childID: UUID
}

@MainActor
@Observable
final class SafetyNavigation {
    static let shared = SafetyNavigation()
    var target: SafetyBannerTarget?
    private init() {}
}

struct GuardianTabView: View {
    @Environment(SessionStore.self) private var session
    @State private var tab = 0

    var body: some View {
        let pendingEventID = SafetyNavigation.shared.target?.eventID
        TabView(selection: $tab) {
            DashboardView()
                .tabItem { Label("Home", systemImage: "house") }
                .tag(0)
            ChildrenView()
                .tabItem { Label("Children", systemImage: "person.2") }
                .tag(1)
            SafetyCenterView()
                .tabItem { Label("Safety", systemImage: "shield") }
                .tag(2)
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
                .tag(3)
        }
        .task(id: pendingEventID) {
            if pendingEventID != nil { tab = 2 }
        }
        .task { await SafetyAlertCenter.shared.watch(session) }
    }
}

@MainActor
final class SafetyAlertCenter: NSObject, UNUserNotificationCenterDelegate {
    static let shared = SafetyAlertCenter()

    private let seenKey = "kinwise.seenSafetyEventIDs"
    private let primedKey = "kinwise.safetyAlertsPrimed"
    private var seen: Set<UUID> = []
    private var primed = false

    private override init() {
        super.init()
        let stored = UserDefaults.standard.stringArray(forKey: seenKey) ?? []
        seen = Set(stored.compactMap(UUID.init(uuidString:)))
        primed = UserDefaults.standard.bool(forKey: primedKey)
    }

    func watch(_ session: SessionStore) async {
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        _ = try? await center.requestAuthorization(options: [.alert, .sound, .badge])
        while !Task.isCancelled {
            await poll(session)
            try? await Task.sleep(for: .seconds(3))
        }
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .sound, .list]
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        let info = response.notification.request.content.userInfo
        guard
            let eventRaw = info["eventID"] as? String, let eventID = UUID(uuidString: eventRaw),
            let childRaw = info["childID"] as? String, let childID = UUID(uuidString: childRaw)
        else { return }
        let target = SafetyBannerTarget(eventID: eventID, childID: childID)
        await MainActor.run { SafetyNavigation.shared.target = target }
    }

    private func poll(_ session: SessionStore) async {
        guard session.user?.role == "guardian" else { return }
        guard let token = try? session.token() else { return }
        guard let children = try? await session.api.children(token: token) else { return }
        var found: [(ChildListItem, SafetyEventItem)] = []
        for child in children {
            guard let events = try? await session.api.safetyEvents(token: token, childID: child.id) else { continue }
            found.append(contentsOf: events.map { (child, $0) })
        }
        if !primed {
            seen.formUnion(found.map(\.1.id))
            primed = true
            store()
            return
        }
        for (child, event) in found where seen.insert(event.id).inserted {
            guard event.notificationEligible, event.severity == "high" || event.severity == "critical" else { continue }
            let content = UNMutableNotificationContent()
            content.title = "Kinwise safety alert"
            content.body = "\(child.displayName): \(event.summary)"
            content.sound = .default
            content.userInfo = [
                "eventID": event.id.uuidString,
                "childID": child.id.uuidString,
            ]
            let request = UNNotificationRequest(identifier: event.id.uuidString, content: content, trigger: nil)
            try? await UNUserNotificationCenter.current().add(request)
        }
        store()
    }

    private func store() {
        UserDefaults.standard.set(seen.map(\.uuidString), forKey: seenKey)
        UserDefaults.standard.set(primed, forKey: primedKey)
    }
}
