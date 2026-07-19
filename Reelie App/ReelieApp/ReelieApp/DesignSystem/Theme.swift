import SwiftUI

// MARK: - Palette
//
// Design register: minimal, fully centered, white canvas.
// Sun is used as an accent / punctuation only.
enum Palette {
    static let sun     = Color(hex: 0xFFD60A)   // accent
    static let sunDeep = Color(hex: 0xEFC400)
    static let ink     = Color(hex: 0x141414)   // primary text
    static let grey    = Color(hex: 0x9A9A9A)   // secondary text
    static let line    = Color(hex: 0xEDEDED)   // hairline borders
    static let soft     = Color(hex: 0xF7F7F7)  // soft fills
    static let faint    = Color(hex: 0xC9C9C9)  // labels / disabled
    static let fainter  = Color(hex: 0xBDBDBD)
    static let ok       = Color(hex: 0x1DB954)
}

extension Color {
    init(hex: UInt, alpha: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: alpha
        )
    }
}

// MARK: - Typography
//
// Display: Fraunces italic (falls back to system serif italic if the font
//          isn't installed — drop Fraunces .ttf into the target and add it to
//          Info.plist "Fonts provided by application" to get the real face).
// UI:      DM Sans (falls back to the system sans font).
enum ReelieFont {
    private static let displayName = "Fraunces-Italic"
    private static let uiName = "DMSans-Regular"

    private static let hasDisplay = UIFont(name: displayName, size: 12) != nil
    private static let hasUI = UIFont(name: uiName, size: 12) != nil

    /// Fraunces-style italic display face used for wordmarks and headlines.
    static func display(_ size: CGFloat) -> Font {
        hasDisplay
            ? .custom(displayName, size: size)
            : .system(size: size, weight: .bold, design: .serif).italic()
    }

    /// DM Sans-style UI face.
    static func ui(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        if hasUI {
            // DM Sans ships weight-named files; Font.custom + weight is close enough.
            return .custom(uiName, size: size).weight(weight)
        }
        return .system(size: size, weight: weight, design: .default)
    }
}

// MARK: - Reusable view modifiers

/// Applies the display face and, when falling back to the system serif,
/// keeps the italic slant.
struct DisplayText: ViewModifier {
    let size: CGFloat
    func body(content: Content) -> some View {
        content
            .font(ReelieFont.display(size))
            .foregroundStyle(Palette.ink)
    }
}

extension View {
    func displayStyle(_ size: CGFloat) -> some View { modifier(DisplayText(size: size)) }
}

// A hairline stroke used across cards / rows.
extension View {
    func hairlineCard(cornerRadius: CGFloat = 18,
                      color: Color = Palette.line,
                      width: CGFloat = 1.5) -> some View {
        overlay(
            RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                .strokeBorder(color, lineWidth: width)
        )
    }
}
