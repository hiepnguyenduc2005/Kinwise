import SwiftUI
import UIKit

struct KinwiseCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.card)
            .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .stroke(Theme.line, lineWidth: 1)
            )
            .shadow(color: Theme.ink.opacity(0.05), radius: 10, y: 4)
    }
}

struct PrimaryButton: View {
    let title: String
    var isLoading = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack {
                if isLoading {
                    ProgressView().tint(.white)
                }
                Text(title)
                    .font(.headline)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
        }
        .buttonStyle(.borderedProminent)
        .tint(Theme.blue)
        .disabled(isLoading)
        .accessibilityLabel(title)
    }
}

struct FieldLabel: View {
    let title: String
    @Binding var text: String
    var secure = false
    var keyboard: UIKeyboardType = .default

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Theme.ink)
            Group {
                if secure {
                    SecureField(title, text: $text)
                } else {
                    DoneAccessoryField(title: title, text: $text, keyboard: keyboard)
                }
            }
            .foregroundStyle(Theme.ink)
            .padding(12)
            .background(Theme.field)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
    }
}

struct StatusPill: View {
    let paused: Bool

    var body: some View {
        Text(paused ? "Paused" : "Active")
            .font(.caption.weight(.semibold))
            .foregroundStyle(Theme.ink)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(paused ? Theme.pausedFill : Theme.activeFill)
            .clipShape(Capsule())
            .accessibilityLabel(paused ? "Access paused" : "Access active")
    }
}

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.senderRole == "child" { Spacer(minLength: 48) }
            VStack(alignment: .leading, spacing: 4) {
                Text(message.senderRole == "child" ? "You" : "Kinwise")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Theme.ink.opacity(0.7))
                Text(message.content ?? "This message is hidden.")
                    .font(.body)
                    .foregroundStyle(Theme.ink)
            }
            .padding(14)
            .background(message.senderRole == "child" ? Theme.childBubble : Theme.assistantBubble)
            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            .accessibilityElement(children: .combine)
            if message.senderRole != "child" { Spacer(minLength: 48) }
        }
    }
}

struct ErrorBanner: View {
    let message: String

    var body: some View {
        Text(message)
            .font(.subheadline)
            .foregroundStyle(Theme.ink)
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.banner)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            .accessibilityLabel(message)
    }
}

struct DoneAccessoryField: UIViewRepresentable {
    let title: String
    @Binding var text: String
    var keyboard: UIKeyboardType = .default

    func makeUIView(context: Context) -> UITextField {
        let field = UITextField()
        field.placeholder = title
        field.keyboardType = keyboard
        field.autocorrectionType = .no
        field.autocapitalizationType = .none
        field.font = .preferredFont(forTextStyle: .body)
        field.textColor = .label
        field.tintColor = UIColor(red: 0.42, green: 0.58, blue: 0.78, alpha: 1)
        field.backgroundColor = .clear
        field.textContentType = keyboard == .phonePad ? .telephoneNumber : nil
        field.addTarget(context.coordinator, action: #selector(Coordinator.changed(_:)), for: .editingChanged)
        let bar = UIToolbar(frame: CGRect(x: 0, y: 0, width: 320, height: 44))
        let done = UIBarButtonItem(title: "Done", style: .done, target: field, action: #selector(UIResponder.resignFirstResponder))
        bar.items = [UIBarButtonItem(barButtonSystemItem: .flexibleSpace, target: nil, action: nil), done]
        bar.sizeToFit()
        field.inputAccessoryView = bar
        return field
    }

    func updateUIView(_ field: UITextField, context: Context) {
        if field.text != text {
            field.text = text
        }
        field.keyboardType = keyboard
    }

    func sizeThatFits(_ proposal: ProposedViewSize, uiView: UITextField, context: Context) -> CGSize? {
        CGSize(width: proposal.width ?? uiView.intrinsicContentSize.width, height: 22)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(text: $text)
    }

    @MainActor
    final class Coordinator: NSObject {
        private let apply: @MainActor (String) -> Void

        init(text: Binding<String>) {
            apply = { text.wrappedValue = $0 }
            super.init()
        }

        @objc nonisolated func changed(_ field: UITextField) {
            MainActor.assumeIsolated {
                apply(field.text ?? "")
            }
        }
    }
}

extension View {
    /// Phone and number keypads have no Return key. Done sits above the keyboard, and dragging a form scrolls it away.
    func kinwiseForm() -> some View {
        scrollDismissesKeyboard(.interactively)
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("Done") {
                        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                    }
                }
            }
    }
}
