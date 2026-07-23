import SwiftUI

/// Consumer-facing read-only routine (the app twin of the public web page).
/// Save the whole routine, shop each product, and see who else uses each product.
struct RoutineView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    let pageKey: String

    private var page: GeneratedPage? { app.page(withKey: pageKey) }

    var body: some View {
        VStack(spacing: 0) {
            navBar
            if let page {
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 0) {
                        header(page)
                        SectionLabel(text: "THE ROUTINE").padding(.top, 24).padding(.bottom, 12)
                        ForEach(Array(page.products.enumerated()), id: \.element.id) { i, product in
                            ProductRow(number: i + 1, product: product,
                                       pageHandle: page.handle, pageSlug: page.pathSlug)
                                .padding(.bottom, 11)
                        }
                        Text(page.disclosure)
                            .font(ReelieFont.ui(11.5)).foregroundStyle(Palette.faint)
                            .multilineTextAlignment(.center)
                            .padding(.top, 6).padding(.horizontal, 16)

                        RecoRail(title: "SIMILAR CREATORS",
                                 items: app.similarCreators(to: page.handle))
                            .padding(.top, 22)
                    }
                    .padding(.horizontal, 28).padding(.bottom, 24)
                }
            } else {
                Spacer(); Text("Routine not found").font(ReelieFont.ui(15)).foregroundStyle(Palette.grey); Spacer()
            }
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
    }

    private var navBar: some View {
        ZStack {
            HStack {
                BackButton { dismiss() }
                Spacer()
                if let page {
                    Button { app.toggleFavorite(page) } label: {
                        Image(systemName: app.isFavorite(page) ? "heart.fill" : "heart")
                            .font(.system(size: 20, weight: .medium))
                            .foregroundStyle(app.isFavorite(page) ? Palette.sun : Palette.ink)
                    }
                    .buttonStyle(.plain)
                }
            }
            StepLabel(text: "ROUTINE")
        }
        .frame(height: 44).padding(.horizontal, 28)
    }

    private func header(_ page: GeneratedPage) -> some View {
        VStack(spacing: 0) {
            GradientPoster(corner: 22).frame(width: 96, height: 96)
                .overlay(Text(page.emoji).font(.system(size: 40)))
                .padding(.top, 6).padding(.bottom, 14)
            Text(page.title).displayStyle(27).multilineTextAlignment(.center)
            NavigationLink(value: ConsumerRoute.creatorProfile(handle: page.handle)) {
                Text("by \(page.creatorName)")
                    .font(ReelieFont.ui(13.5, weight: .bold)).foregroundStyle(Palette.ink)
                    .padding(.bottom, 1)
                    .overlay(Rectangle().fill(Palette.sun).frame(height: 1.5), alignment: .bottom)
            }
            .buttonStyle(.plain)
            .padding(.top, 8)
        }
    }
}

/// One product row: brand/name/price/shop, plus a "also used by" avatar strip.
private struct ProductRow: View {
    @Environment(AppState.self) private var app
    let number: Int
    let product: Product
    let pageHandle: String
    let pageSlug: String

    private var alsoUsedBy: [Creator] {
        app.creatorsUsing(brand: product.brand, name: product.name, excluding: pageHandle)
    }

    /// The affiliate redirect that logs a click and 302s to the retailer,
    /// exactly like the web page's Shop buttons (`/r/{handle}/{slug}/{position}`).
    private var shopURL: URL? {
        let base = app.apiBaseURL ?? URL(string: "https://reelie.io")
        return base?.appendingPathComponent("r/\(pageHandle)/\(pageSlug)/\(number)")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 13) {
                Text("\(number)").font(ReelieFont.display(16)).foregroundStyle(Palette.faint).frame(width: 18)
                EmojiThumb(emoji: product.emoji, size: 50)
                VStack(alignment: .leading, spacing: 2) {
                    if !product.brand.isEmpty {
                        Text(product.brand.uppercased())
                            .font(ReelieFont.ui(11, weight: .bold)).tracking(0.6).foregroundStyle(Palette.grey)
                    }
                    Text(product.name)
                        .font(ReelieFont.ui(14.5, weight: .medium)).foregroundStyle(Palette.ink)
                        .fixedSize(horizontal: false, vertical: true)
                    if let price = product.priceDisplay {
                        Text(price).font(ReelieFont.ui(12.5, weight: .bold)).foregroundStyle(Palette.ink).padding(.top, 3)
                    }
                }
                Spacer(minLength: 4)
                shopButton
            }

            if !alsoUsedBy.isEmpty {
                HStack(spacing: 7) {
                    Text("Also used by").font(ReelieFont.ui(11)).foregroundStyle(Palette.grey)
                    ForEach(alsoUsedBy.prefix(4)) { c in
                        NavigationLink(value: ConsumerRoute.creatorProfile(handle: c.handle)) {
                            CreatorAvatar(gradient: c.avatarGradient, size: 24, ring: false)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.leading, 31)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 13)
        .hairlineCard()
    }

    @ViewBuilder private var shopButton: some View {
        if let url = shopURL {
            Link(destination: url) { shopButtonLabel }.buttonStyle(.plain)
        } else {
            shopButtonLabel
        }
    }

    private var shopButtonLabel: some View {
        VStack(spacing: 3) {
            Text("Shop").font(ReelieFont.ui(13, weight: .bold)).foregroundStyle(Palette.ink)
            if let retailer = product.retailer, !retailer.isEmpty {
                Text(retailer.uppercased())
                    .font(ReelieFont.ui(9, weight: .bold)).tracking(0.4)
                    .foregroundStyle(Palette.ink.opacity(0.55))
            }
        }
        .padding(.horizontal, 15).padding(.vertical, 10)
        .background(Palette.sun, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

#Preview {
    let a = AppState(); a.onboardingComplete = true
    return NavigationStack { RoutineView(pageKey: "mariskincare/night-routine") }.environment(a)
}
