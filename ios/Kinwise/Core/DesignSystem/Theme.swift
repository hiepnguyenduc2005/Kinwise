import SwiftUI

enum Theme {
    static let cream = adaptive(
        light: UIColor(red: 0.984, green: 0.969, blue: 0.949, alpha: 1),
        dark: UIColor(red: 0.09, green: 0.09, blue: 0.10, alpha: 1)
    )
    static let ink = adaptive(
        light: UIColor(red: 0.17, green: 0.22, blue: 0.28, alpha: 1),
        dark: UIColor(red: 0.95, green: 0.93, blue: 0.89, alpha: 1)
    )
    static let blue = adaptive(
        light: UIColor(red: 0.42, green: 0.58, blue: 0.78, alpha: 1),
        dark: UIColor(red: 0.49, green: 0.66, blue: 0.88, alpha: 1)
    )
    static let lavender = adaptive(
        light: UIColor(red: 0.72, green: 0.66, blue: 0.86, alpha: 1),
        dark: UIColor(red: 0.78, green: 0.72, blue: 0.94, alpha: 1)
    )
    static let mint = adaptive(
        light: UIColor(red: 0.62, green: 0.82, blue: 0.74, alpha: 1),
        dark: UIColor(red: 0.55, green: 0.82, blue: 0.72, alpha: 1)
    )
    static let card = adaptive(light: .white, dark: UIColor(red: 0.16, green: 0.16, blue: 0.18, alpha: 1))
    static let field = adaptive(
        light: UIColor(red: 0.984, green: 0.969, blue: 0.949, alpha: 1),
        dark: UIColor(red: 0.22, green: 0.22, blue: 0.25, alpha: 1)
    )
    static let caution = adaptive(
        light: UIColor(red: 0.86, green: 0.55, blue: 0.42, alpha: 1),
        dark: UIColor(red: 0.93, green: 0.62, blue: 0.48, alpha: 1)
    )
    static let line = adaptive(
        light: UIColor(red: 0.17, green: 0.22, blue: 0.28, alpha: 0.08),
        dark: UIColor(white: 1, alpha: 0.12)
    )
    static let childBubble = adaptive(
        light: UIColor(red: 0.86, green: 0.83, blue: 0.94, alpha: 1),
        dark: UIColor(red: 0.33, green: 0.28, blue: 0.48, alpha: 1)
    )
    static let assistantBubble = adaptive(
        light: UIColor(red: 0.82, green: 0.91, blue: 0.87, alpha: 1),
        dark: UIColor(red: 0.20, green: 0.36, blue: 0.32, alpha: 1)
    )
    static let secondaryFill = adaptive(
        light: UIColor(red: 0.73, green: 0.87, blue: 0.82, alpha: 1),
        dark: UIColor(red: 0.18, green: 0.34, blue: 0.30, alpha: 1)
    )
    static let activeFill = adaptive(
        light: UIColor(red: 0.79, green: 0.90, blue: 0.86, alpha: 1),
        dark: UIColor(red: 0.18, green: 0.34, blue: 0.30, alpha: 1)
    )
    static let pausedFill = adaptive(
        light: UIColor(red: 0.95, green: 0.86, blue: 0.82, alpha: 1),
        dark: UIColor(red: 0.42, green: 0.26, blue: 0.22, alpha: 1)
    )
    static let banner = adaptive(
        light: UIColor(red: 0.96, green: 0.89, blue: 0.86, alpha: 1),
        dark: UIColor(red: 0.38, green: 0.22, blue: 0.18, alpha: 1)
    )

    private static func adaptive(light: UIColor, dark: UIColor) -> Color {
        Color(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark ? dark : light
        })
    }
}

extension Font {
    static let kinwiseTitle = Font.system(.largeTitle, design: .rounded).weight(.semibold)
    static let kinwiseHeadline = Font.system(.title3, design: .rounded).weight(.semibold)
}
