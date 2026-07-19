import SwiftUI

// Shared pieces for the consumer surface (Discover / creator profiles / Saved).

/// Round creator avatar (gradient with an optional sun ring).
struct CreatorAvatar: View {
    let gradient: [Color]
    var size: CGFloat = 46
    var ring: Bool = true

    var body: some View {
        Circle()
            .fill(LinearGradient(colors: gradient, startPoint: .topLeading, endPoint: .bottomTrailing))
            .frame(width: size, height: size)
            .overlay(ring ? Circle().strokeBorder(Palette.sun, lineWidth: max(2, size * 0.05)) : nil)
    }
}

/// A card for one routine (GeneratedPage) in a list. Taps through to RoutineView.
struct RoutineCard: View {
    @Environment(AppState.self) private var app
    let page: GeneratedPage
    var showCreator: Bool = true

    var body: some View {
        NavigationLink(value: ConsumerRoute.routine(key: page.key)) {
            HStack(spacing: 13) {
                GradientPoster(colors: [Color(hex: 0xE8E4DA), Color(hex: 0xD8D2C4)], corner: 14)
                    .frame(width: 54, height: 54)
                    .overlay(Text(page.emoji).font(.system(size: 22)))

                VStack(alignment: .leading, spacing: 3) {
                    Text(page.title)
                        .font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.ink)
                        .lineLimit(1)
                    Text(showCreator ? "\(page.creatorName) · \(page.products.count) products"
                                     : "\(page.products.count) products")
                        .font(ReelieFont.ui(12.5)).foregroundStyle(Palette.grey)
                        .lineLimit(1)
                }
                Spacer(minLength: 8)
                Image(systemName: app.isFavorite(page) ? "heart.fill" : "chevron.right")
                    .font(.system(size: app.isFavorite(page) ? 14 : 15, weight: .bold))
                    .foregroundStyle(app.isFavorite(page) ? Palette.sun : Color(hex: 0xD5D5D5))
            }
            .padding(14)
            .hairlineCard()
            .padding(.bottom, 10)
        }
        .buttonStyle(.plain)
    }
}

/// Horizontal rail of creator recommendation chips with a reason line.
struct RecoRail: View {
    let title: String
    let items: [(creator: Creator, reason: String)]

    var body: some View {
        if !items.isEmpty {
            VStack(alignment: .leading, spacing: 0) {
                SectionLabel(text: title).padding(.bottom, 12)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        ForEach(items, id: \.creator.handle) { item in
                            NavigationLink(value: ConsumerRoute.creatorProfile(handle: item.creator.handle)) {
                                VStack(spacing: 8) {
                                    CreatorAvatar(gradient: item.creator.avatarGradient, size: 60)
                                    Text(item.creator.displayName)
                                        .font(ReelieFont.ui(13, weight: .bold)).foregroundStyle(Palette.ink)
                                        .lineLimit(1)
                                    Text(item.reason)
                                        .font(ReelieFont.ui(11)).foregroundStyle(Palette.grey)
                                        .multilineTextAlignment(.center).lineLimit(2)
                                }
                                .frame(width: 108)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
        }
    }
}

extension View {
    /// Registers the consumer navigation destinations on a stack root.
    func consumerDestinations() -> some View {
        self.navigationDestination(for: ConsumerRoute.self) { route in
            switch route {
            case .creatorProfile(let handle):
                CreatorProfileView(handle: handle)
            case .routine(let key):
                RoutineView(pageKey: key)
            }
        }
    }
}
