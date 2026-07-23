import SwiftUI

// MARK: - Palette
//
// Design register: minimal, fully centered, white canvas, yellow accent.
// Warm ink/muted/neutrals match the web app (studio): warm near-black text on
// warm off-whites. Sun (yellow) stays the accent / punctuation.
enum Palette {
    static let sun     = Color(hex: 0xFFD60A)   // accent (yellow)
    static let sunDeep = Color(hex: 0xEFC400)
    static let ink     = Color(hex: 0x201B0A)   // primary text (warm near-black — web --ink)
    static let grey    = Color(hex: 0x7A6F4A)   // secondary text (warm tan — web --grey)
    static let line    = Color(hex: 0xE9E4D8)   // hairline borders (warm)
    static let soft     = Color(hex: 0xF7F4EC)  // soft fills (warm off-white)
    static let faint    = Color(hex: 0xB4A98A)  // labels / disabled (warm — web --faint)
    static let fainter  = Color(hex: 0xC7BEA8)
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
// Matches the web app exactly:
//   Display / headings / wordmark / big numbers = Space Grotesk
//   UI / body                                    = Instrument Sans
// Static weight files are bundled in Resources/Fonts and registered via
// Info.plist UIAppFonts. Each weight is its own file (referenced by PostScript
// name) so weights render crisply instead of being synthesized. Falls back to
// the system font if the faces somehow fail to load.
enum ReelieFont {
    static let hasBrandFonts = UIFont(name: "InstrumentSans-Regular", size: 12) != nil
                            && UIFont(name: "SpaceGrotesk-Bold", size: 12) != nil

    /// Instrument Sans file for a given weight.
    private static func instrument(_ weight: Font.Weight) -> String {
        switch weight {
        case .medium:                 return "InstrumentSans-Medium"
        case .semibold:               return "InstrumentSans-SemiBold"
        case .bold, .heavy, .black:   return "InstrumentSans-Bold"
        default:                      return "InstrumentSans-Regular"
        }
    }

    /// Space Grotesk file for a given weight (ships Medium/SemiBold/Bold).
    private static func grotesk(_ weight: Font.Weight) -> String {
        switch weight {
        case .thin, .ultraLight, .light, .regular, .medium: return "SpaceGrotesk-Medium"
        case .semibold:                                     return "SpaceGrotesk-SemiBold"
        default:                                            return "SpaceGrotesk-Bold"
        }
    }

    /// Space Grotesk display face — wordmarks, headlines, big numbers.
    static func display(_ size: CGFloat, weight: Font.Weight = .bold) -> Font {
        hasBrandFonts
            ? .custom(grotesk(weight), size: size)
            : .system(size: size, weight: .bold, design: .default)
    }

    /// Instrument Sans UI / body face.
    static func ui(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        hasBrandFonts
            ? .custom(instrument(weight), size: size)
            : .system(size: size, weight: weight, design: .default)
    }
}

// MARK: - Reusable view modifiers

/// Applies the Space Grotesk display face + ink color.
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
