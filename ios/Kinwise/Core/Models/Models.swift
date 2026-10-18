import Foundation

struct UserAccount: Codable, Identifiable, Hashable {
    let id: UUID
    let role: String
    var displayName: String
    var email: String?
    var username: String?
}

struct TokenResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int
    let user: UserAccount
}

struct AccessState: Codable, Equatable {
    var isPaused: Bool
    var stateVersion: Int
    var updatedAt: Date
}

struct ChildListItem: Codable, Identifiable, Hashable {
    let id: UUID
    let username: String
    let displayName: String
    let ageBand: String
    var isPaused: Bool
    var stateVersion: Int
    var messagesToday: Int
}

struct ChildProfileResponse: Codable, Identifiable {
    let id: UUID
    let username: String
    let displayName: String
    let ageBand: String
    let createdAt: Date
    var access: AccessState
}

struct ChildMe: Codable {
    let id: UUID
    let username: String
    let displayName: String
    let ageBand: String
    let supervisionNotice: String
}

struct UsageDay: Codable, Identifiable {
    var id: String { date }
    let date: String
    let count: Int
}

struct SafetyCount: Codable, Identifiable {
    var id: String { category }
    let category: String
    let count: Int
}

struct UsageSummary: Codable {
    let messagesToday: Int
    let conversationsToday: Int
    let messagesLast7Days: [UsageDay]
    let safetyCounts: [SafetyCount]
}

struct ConversationSummary: Codable, Identifiable, Hashable {
    let id: UUID
    let title: String
    let summary: String?
    let ended: Bool
    let createdAt: Date
    let updatedAt: Date
}

struct ChatMessage: Codable, Identifiable {
    let id: UUID
    let senderRole: String
    let content: String?
    let restricted: Bool
    let childFacingText: String?
    let createdAt: Date
}

struct SendMessageResponse: Codable {
    let userMessage: ChatMessage
    let assistantMessage: ChatMessage?
    let access: AccessState
    let conversationEnded: Bool
}

struct SafetyEventItem: Codable, Identifiable {
    let id: UUID
    let category: String
    let severity: String
    let createdAt: Date
    let resolutionStatus: String
    let notificationEligible: Bool
    let summary: String
    let recommendedAction: String
    let conversationId: UUID?
    let messageId: UUID?
}

struct ChildOverview: Codable {
    let child: ChildProfileResponse
    let usage: UsageSummary
    let recentSafety: [SafetyEventItem]
    let recentConversations: [ConversationSummary]
}

struct InvitationCreated: Codable {
    let invitationId: UUID
    let code: String
    let expiresAt: Date
}

struct InvitationAccepted: Codable {
    let invitationId: UUID
    let childId: UUID
    let status: String
}

struct InvitationPending: Codable, Identifiable {
    var id: UUID { invitationId }
    let invitationId: UUID
    let status: String
    let expiresAt: Date
    let acceptedByDisplayName: String?
}

struct GuardianLink: Codable, Identifiable {
    var id: UUID { guardianId }
    let guardianId: UUID
    let displayName: String
    let status: String
    let activatedAt: Date?
    let createdByAudit: Bool
}

struct PhoneStatus: Codable {
    let phone: String?
    let messagingEnabled: Bool
    let photonSpaceId: String?
}

struct PhotonCommandItem: Codable, Identifiable {
    let id: UUID
    let command: String
    let status: String
    let childId: UUID?
    let createdAt: Date
    let result: String
}

struct AccessSocketEvent: Codable, Sendable {
    let type: String
    let childId: UUID
    let isPaused: Bool
    let stateVersion: Int
    let updatedAt: Date
}

struct StatusResponse: Codable {
    let status: String
}
