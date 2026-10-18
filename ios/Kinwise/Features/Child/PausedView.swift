import SwiftUI

struct PausedView: View {
    var body: some View {
        KinwiseCard {
            VStack(alignment: .leading, spacing: 8) {
                Label("Taking a break", systemImage: "moon.stars")
                    .font(.headline)
                    .foregroundStyle(Theme.ink)
                Text("A guardian paused Kinwise. Chat will come back when they turn it on. You have not done anything wrong.")
                    .font(.body)
                    .foregroundStyle(Theme.ink)
            }
        }
        .padding(.horizontal, 16)
        .accessibilityElement(children: .combine)
    }
}
