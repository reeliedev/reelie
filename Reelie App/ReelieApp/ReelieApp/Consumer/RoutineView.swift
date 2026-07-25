import SwiftUI

/// Consumer-facing read-only routine (the app twin of the public web page).
/// Save the whole routine, shop each product, and see who else uses each product.
struct RoutineView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    let pageKey: String

    @State private var fetched: GeneratedPage?
    @State private var didLoad = false
    private var page: GeneratedPage? { app.page(withKey: pageKey) ?? fetched }

    var body: some View {
        VStack(spacing: 0) {
            navBar
            if let page {
                ScrollView(showsIndicators: false) {
                    LazyVStack(spacing: 0) {
                        header(page)
                        if !page.intro.isEmpty {
                            Text(page.intro)
                                .font(ReelieFont.ui(15)).foregroundStyle(Palette.ink).lineSpacing(3)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.top, 18)
                        }
                        if let t = page.totals, !t.totalDisplay.isEmpty { totalsCard(t) }
                        SectionLabel(text: "THE ROUTINE").padding(.top, 24).padding(.bottom, 12)
                        ForEach(Array(page.products.enumerated()), id: \.element.id) { i, product in
                            ProductRow(number: i + 1, product: product,
                                       pageHandle: page.handle, pageSlug: page.pathSlug)
                                .padding(.bottom, 11)
                        }

                        if !page.faqs.isEmpty { faqSection(page.faqs).padding(.top, 26) }

                        Text(page.disclosure)
                            .font(ReelieFont.ui(11.5)).foregroundStyle(Palette.faint)
                            .multilineTextAlignment(.center)
                            .padding(.top, 20).padding(.horizontal, 16)

                        RecoRail(title: "SIMILAR CREATORS",
                                 items: app.similarCreators(to: page.handle))
                            .padding(.top, 22)
                    }
                    .padding(.horizontal, 28).padding(.bottom, 24)
                }
            } else if !didLoad {
                Spacer(); ProgressView().tint(Palette.ink); Spacer()
            } else {
                Spacer(); Text("Routine not found").font(ReelieFont.ui(15)).foregroundStyle(Palette.grey); Spacer()
            }
        }
        .task(id: pageKey) {
            if app.page(withKey: pageKey) == nil { fetched = await app.fetchRoutine(key: pageKey) }
            didLoad = true
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
                    UGCMenu(kind: "page", ref: page.key, handle: page.handle) { dismiss() }
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

    // "Shop the whole routine" kit — matches the web's summary card.
    private func totalsCard(_ t: RoutineTotals) -> some View {
        VStack(spacing: 8) {
            Text("SHOP THE WHOLE ROUTINE")
                .font(ReelieFont.ui(10.5, weight: .bold)).tracking(1).foregroundStyle(Palette.grey)
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(t.totalDisplay).displayStyle(32)
                if t.anyEstimated { Text("approx.").font(ReelieFont.ui(12)).foregroundStyle(Palette.faint) }
            }
            Text("\(t.count) products" + (t.rangeDisplay != "—" ? " · \(t.rangeDisplay)" : ""))
                .font(ReelieFont.ui(12.5)).foregroundStyle(Palette.grey)
            if !t.retailers.isEmpty {
                HStack(spacing: 6) {
                    ForEach(t.retailers.prefix(4), id: \.self) { r in
                        Text(r).font(ReelieFont.ui(11, weight: .semibold)).foregroundStyle(Palette.ink)
                            .padding(.horizontal, 10).padding(.vertical, 5)
                            .background(.white, in: Capsule())
                            .overlay(Capsule().strokeBorder(Palette.line, lineWidth: 1))
                    }
                }
                .padding(.top, 4)
            }
        }
        .frame(maxWidth: .infinity).padding(.vertical, 18).padding(.horizontal, 16)
        .background(Palette.soft, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .padding(.top, 18)
    }

    // Auto-generated + custom Q&A — the same block the web routine page shows.
    private func faqSection(_ faqs: [RoutineFAQ]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionLabel(text: "QUESTIONS & ANSWERS")
            ForEach(faqs) { f in
                VStack(alignment: .leading, spacing: 4) {
                    Text(f.q).font(ReelieFont.ui(14, weight: .semibold)).foregroundStyle(Palette.ink)
                    Text(f.a).font(ReelieFont.ui(13)).foregroundStyle(Palette.grey).lineSpacing(2)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(14).hairlineCard(cornerRadius: 14)
            }
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

    /// The per-step video clip, absolute-ized.
    private var clipURL: URL? {
        guard let c = product.clipUrl, !c.isEmpty else { return nil }
        if c.hasPrefix("http") { return URL(string: c) }
        return (app.apiBaseURL ?? URL(string: "https://reelie.io"))?.appendingPathComponent(c)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // The actual clip playing (muted, looping) — same as the web guide.
            if let clip = clipURL {
                ClipPlayerView(url: clip)
                    .frame(maxWidth: .infinity).frame(height: 300)
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .padding(.bottom, 12)
            }

            // Step + timestamp, and the evidence tag.
            HStack(spacing: 6) {
                Text("STEP \(number)")
                    .font(ReelieFont.ui(10.5, weight: .bold)).tracking(0.8).foregroundStyle(Palette.grey)
                if !product.timestamp.isEmpty, product.timestamp != "0:00" {
                    Text("· \(product.timestamp)").font(ReelieFont.ui(10.5, weight: .bold)).foregroundStyle(Palette.faint)
                }
                Spacer()
                Text(product.evidence.label)
                    .font(ReelieFont.ui(10, weight: .semibold)).foregroundStyle(Palette.grey)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(Palette.soft, in: Capsule())
            }
            .padding(.bottom, 8)

            HStack(alignment: .top, spacing: 12) {
                if clipURL == nil { EmojiThumb(emoji: product.emoji, size: 46) }
                VStack(alignment: .leading, spacing: 3) {
                    if !product.brand.isEmpty {
                        Text(product.brand.uppercased())
                            .font(ReelieFont.ui(11, weight: .bold)).tracking(0.6).foregroundStyle(Palette.grey)
                    }
                    (Text(product.name).font(ReelieFont.ui(16, weight: .semibold)).foregroundStyle(Palette.ink)
                     + (product.variant.map {
                            Text("  \($0)").font(ReelieFont.ui(13)).foregroundStyle(Palette.grey)
                        } ?? Text("")))
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
            }

            // Narration — how they use it (the meat of the guide).
            if let n = product.narration {
                Text(n).font(ReelieFont.ui(13.5)).foregroundStyle(Palette.grey).lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true).padding(.top, 8)
            }

            // Price + shop.
            HStack(alignment: .center) {
                if let price = product.priceDisplay {
                    HStack(spacing: 4) {
                        Text(price).font(ReelieFont.ui(14, weight: .bold)).foregroundStyle(Palette.ink)
                        if product.priceEstimated {
                            Text("approx.").font(ReelieFont.ui(11)).foregroundStyle(Palette.faint)
                        }
                    }
                }
                Spacer()
                shopButton
            }
            .padding(.top, 12)

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
                .padding(.top, 12)
            }
        }
        .padding(14)
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
