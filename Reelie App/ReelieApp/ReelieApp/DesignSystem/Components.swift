import SwiftUI

// MARK: - Wordmark

/// "Reelie." with a sun-yellow dot.
struct Wordmark: View {
    var size: CGFloat = 24
    var body: some View {
        HStack(spacing: 0) {
            Text("Reelie").foregroundStyle(Palette.ink)
            Text(".").foregroundStyle(Palette.sun)
        }
        .font(ReelieFont.display(size))
    }
}

// MARK: - Buttons

/// Full-width primary action. Sun fill by default; `.ink` and `.outline` variants.
struct BigButton: View {
    enum Style { case sun, ink, outline }

    let title: String
    var style: Style = .sun
    var icon: Image? = nil
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                icon
                Text(title)
            }
            .font(ReelieFont.ui(16, weight: style == .sun ? .bold : .medium))
            .foregroundStyle(foreground)
            .frame(maxWidth: .infinity)
            .frame(height: 54)
            .background(background)
            .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .strokeBorder(Palette.line, lineWidth: style == .outline ? 1.5 : 0)
            )
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
        .buttonStyle(PressableStyle())
    }

    private var foreground: Color { style == .ink ? .white : Palette.ink }
    private var background: Color {
        switch style {
        case .sun: return Palette.sun
        case .ink: return Palette.ink
        case .outline: return .white
        }
    }
}

/// Small pill button (e.g. "Connect", "Review", "Copy").
struct PillButton: View {
    enum Style { case ink, sun, outline }
    let title: String
    var style: Style = .ink
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(ReelieFont.ui(13.5, weight: .bold))
                .foregroundStyle(style == .ink ? .white : Palette.ink)
                .padding(.horizontal, 16)
                .padding(.vertical, 9)
                .background(fill)
                .overlay(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .strokeBorder(Palette.ink, lineWidth: style == .outline ? 1.5 : 0)
                )
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .buttonStyle(PressableStyle())
    }

    private var fill: Color {
        switch style {
        case .ink: return Palette.ink
        case .sun: return Palette.sun
        case .outline: return .white
        }
    }
}

/// Scale-on-press affordance matching the web mockups' `:active` transform.
struct PressableStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.easeOut(duration: 0.08), value: configuration.isPressed)
    }
}

// MARK: - Small pieces

/// All-caps tracked section label, e.g. "NEEDS YOUR OK".
struct SectionLabel: View {
    let text: String
    var body: some View {
        Text(text)
            .font(ReelieFont.ui(11.5, weight: .bold))
            .tracking(1.5)
            .foregroundStyle(Palette.faint)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// The sun-yellow circular check badge used everywhere.
struct SunTick: View {
    var size: CGFloat = 24
    var body: some View {
        Circle()
            .fill(Palette.sun)
            .frame(width: size, height: size)
            .overlay(
                Image(systemName: "checkmark")
                    .font(.system(size: size * 0.5, weight: .bold))
                    .foregroundStyle(Palette.ink)
            )
    }
}

/// Yellow "earns X%" / soft "LTK" rate chip.
struct RateChip: View {
    let link: LinkKind
    var body: some View {
        switch link {
        case .reelie(let rate):
            chip("earns \(rate)%", bg: Palette.sun, fg: Palette.ink)
        case .own(let label):
            chip(label, bg: Palette.soft, fg: Palette.ink)
        }
    }

    private func chip(_ text: String, bg: Color, fg: Color) -> some View {
        Text(text)
            .font(ReelieFont.ui(11.5, weight: .bold))
            .foregroundStyle(fg)
            .padding(.horizontal, 7)
            .padding(.vertical, 1.5)
            .background(bg, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
    }
}

/// Emoji tile used as a product/page thumbnail.
struct EmojiThumb: View {
    let emoji: String
    var size: CGFloat = 46
    var corner: CGFloat = 12
    var fill: Color = Palette.soft
    var body: some View {
        RoundedRectangle(cornerRadius: corner, style: .continuous)
            .fill(fill)
            .frame(width: size, height: size)
            .overlay(Text(emoji).font(.system(size: size * 0.42)))
    }
}

/// Gradient poster tile (video thumbnails / page headers).
struct GradientPoster: View {
    var colors: [Color] = [Color(hex: 0xE8E4DA), Color(hex: 0xD8D2C4)]
    var corner: CGFloat = 20
    var body: some View {
        RoundedRectangle(cornerRadius: corner, style: .continuous)
            .fill(LinearGradient(colors: colors, startPoint: .topLeading, endPoint: .bottomTrailing))
    }
}

// MARK: - Custom tab bar

struct ReelieTabBar: View {
    @Binding var selection: MainTab
    /// When true, the creator studio tabs (Pages / Earnings) are shown.
    var showsCreator: Bool = false

    var body: some View {
        VStack(spacing: 0) {
            Rectangle().fill(Palette.line).frame(height: 1.5)
            HStack {
                item(.discover, "magnifyingglass", "Discover")
                item(.saved, "heart", "Saved")
                if showsCreator {
                    item(.pages, "square.grid.2x2", "Pages")
                    item(.earnings, "target", "Earnings")
                }
                item(.profile, "person.circle", "Profile")
            }
            .padding(.top, 10)
            .padding(.horizontal, 10)
            .padding(.bottom, 6)
        }
        .background(.white)
    }

    private func item(_ tab: MainTab, _ symbol: String, _ label: String) -> some View {
        let active = selection == tab
        return Button {
            selection = tab
        } label: {
            VStack(spacing: 3) {
                Image(systemName: symbol)
                    .font(.system(size: 20))
                Text(label)
                    .font(ReelieFont.ui(11.5, weight: .bold))
                Circle()
                    .fill(active ? Palette.sun : .clear)
                    .frame(width: 5, height: 5)
                    .padding(.top, 1)
            }
            .foregroundStyle(active ? Palette.ink : Palette.faint)
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Nav bar back button

struct BackButton: View {
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Image(systemName: "chevron.left")
                .font(.system(size: 20, weight: .medium))
                .foregroundStyle(Palette.ink)
        }
        .buttonStyle(.plain)
    }
}

/// A small centered step label like "STEP 1 OF 2".
struct StepLabel: View {
    let text: String
    var body: some View {
        Text(text)
            .font(ReelieFont.ui(12, weight: .bold))
            .tracking(1.5)
            .foregroundStyle(Palette.faint)
    }
}
