import SwiftUI

/// Screen 07 — Approve your page (+ screen 08 add-product sheet).
struct ApprovePageView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    let pageID: UUID

    @State private var expandedID: UUID?
    @State private var showAddSheet = false

    private var page: Page? { app.pages.first { $0.id == pageID } }

    var body: some View {
        VStack(spacing: 0) {
            // Nav bar.
            ZStack {
                HStack { BackButton { dismiss() }; Spacer() }
                StepLabel(text: "NEW PAGE READY")
            }
            .frame(height: 44)
            .padding(.horizontal, 28)

            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {
                    header

                    SectionLabel(text: "READY — TAP ANY PRODUCT TO EDIT")
                        .padding(.top, 20).padding(.bottom, 10)

                    ForEach(readyProducts) { product in
                        ProductApprovalCard(
                            product: product,
                            expanded: expandedID == product.id,
                            onTap: { toggle(product.id) }
                        )
                        .padding(.bottom, 10)
                    }

                    if !reviewProducts.isEmpty {
                        SectionLabel(text: "NEEDS A LOOK").padding(.top, 10).padding(.bottom, 10)
                        ForEach(reviewProducts) { product in
                            ReviewProductCard(product: product,
                                               onYes: {}, onNo: { remove(product.id) })
                            .padding(.bottom, 10)
                        }
                    }

                    Button { showAddSheet = true } label: {
                        Text("+ Add a product we missed")
                            .font(ReelieFont.ui(14.5, weight: .medium)).foregroundStyle(Palette.grey)
                            .frame(maxWidth: .infinity).frame(height: 50)
                            .overlay(
                                RoundedRectangle(cornerRadius: 16, style: .continuous)
                                    .strokeBorder(style: StrokeStyle(lineWidth: 1.5, dash: [5]))
                                    .foregroundStyle(Color(hex: 0xDCDCDC))
                            )
                    }
                    .buttonStyle(.plain)
                    .padding(.top, 2)
                }
                .padding(.horizontal, 28)
                .padding(.bottom, 16)
            }

            // Bottom approve.
            VStack(spacing: 12) {
                Rectangle().fill(Palette.line).frame(height: 1.5)
                NavigationLink(value: AppRoute.pageLive(slug: page?.slug ?? "",
                                                        title: page?.title ?? "")) {
                    Text("Approve page")
                        .font(ReelieFont.ui(16, weight: .bold)).foregroundStyle(Palette.ink)
                        .frame(maxWidth: .infinity).frame(height: 54)
                        .background(Palette.sun, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                }
                .buttonStyle(PressableStyle())
                .simultaneousGesture(TapGesture().onEnded { approve() })
                .padding(.horizontal, 28)
                Button("Not now") { dismiss() }
                    .font(ReelieFont.ui(14, weight: .medium)).foregroundStyle(Palette.grey)
                    .buttonStyle(.plain)
            }
            .padding(.bottom, 8)
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .sheet(isPresented: $showAddSheet) { AddProductSheet() }
    }

    private var header: some View {
        VStack(spacing: 0) {
            GradientPoster(corner: 22)
                .frame(width: 96, height: 96)
                .overlay(
                    Circle().fill(.white.opacity(0.92)).frame(width: 34, height: 34)
                        .overlay(Image(systemName: "play.fill").font(.system(size: 13)).foregroundStyle(Palette.ink))
                )
                .padding(.top, 6).padding(.bottom, 14)

            Text(page?.title ?? "Your new page").displayStyle(27)
                .multilineTextAlignment(.center)

            (
                Text("From your Reel, yesterday · ")
                + Text("\(readyProducts.count + reviewProducts.count) products found")
                    .foregroundStyle(Palette.ink).fontWeight(.bold)
            )
            .font(ReelieFont.ui(13.5)).foregroundStyle(Palette.grey)
            .padding(.top, 8)
        }
    }

    private var readyProducts: [Product] { page?.products.filter { $0.status == .ready } ?? [] }
    private var reviewProducts: [Product] { page?.products.filter { $0.status == .needsReview } ?? [] }

    private func toggle(_ id: UUID) {
        withAnimation(.easeInOut(duration: 0.2)) { expandedID = (expandedID == id) ? nil : id }
    }

    private func remove(_ id: UUID) {
        guard let idx = app.pages.firstIndex(where: { $0.id == pageID }) else { return }
        withAnimation { app.pages[idx].products.removeAll { $0.id == id } }
    }

    private func approve() {
        guard let idx = app.pages.firstIndex(where: { $0.id == pageID }) else { return }
        app.pages[idx].status = .live
        app.pages[idx].meta = "Just now · live"
        // Reset the tab to Pages so returning lands on the list.
        app.selectedTab = .pages
    }
}

// MARK: - Ready product card (expands to link editor)

private struct ProductApprovalCard: View {
    let product: Product
    let expanded: Bool
    let onTap: () -> Void

    @State private var useReelieLink = true

    var body: some View {
        VStack(spacing: 0) {
            Button(action: onTap) {
                HStack(spacing: 12) {
                    EmojiThumb(emoji: product.emoji)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(product.brand.uppercased())
                            .font(ReelieFont.ui(11.5, weight: .bold)).tracking(0.6)
                            .foregroundStyle(Palette.grey)
                        Text(product.name)
                            .font(ReelieFont.ui(15, weight: .medium)).foregroundStyle(Palette.ink)
                            .multilineTextAlignment(.leading)
                        evidenceLine.padding(.top, 3)
                        if !expanded { linkLine.padding(.top, 5) }
                    }
                    Spacer(minLength: 4)
                    VStack(spacing: 8) {
                        SunTick(size: 24)
                        Image(systemName: expanded ? "chevron.down" : "chevron.right")
                            .font(.system(size: 15, weight: .bold)).foregroundStyle(Color(hex: 0xD5D5D5))
                    }
                }
            }
            .buttonStyle(.plain)

            if expanded { editor.padding(.top, 13) }
        }
        .padding(.horizontal, 14).padding(.vertical, 13)
        .hairlineCard(color: expanded ? Palette.ink : Palette.line)
    }

    private var evidenceLine: some View {
        HStack(spacing: 6) {
            Text(product.evidence.rawValue)
                .font(ReelieFont.ui(11.5, weight: .bold)).foregroundStyle(Palette.grey)
                .padding(.horizontal, 6).padding(.vertical, 1)
                .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(Palette.line, lineWidth: 1))
            Text(product.note.map { "\(product.timestamp) · \($0)" } ?? product.timestamp)
                .font(ReelieFont.ui(11.5)).foregroundStyle(Palette.faint)
        }
    }

    private var linkLine: some View {
        HStack(spacing: 6) {
            switch product.link {
            case .reelie: Text("Reelie link").font(ReelieFont.ui(12, weight: .medium)).foregroundStyle(Palette.grey)
            case .own:    Text("Your link").font(ReelieFont.ui(12, weight: .medium)).foregroundStyle(Palette.grey)
            }
            RateChip(link: product.link)
        }
    }

    private var editor: some View {
        VStack(alignment: .leading, spacing: 0) {
            Rectangle().fill(Palette.line).frame(height: 1.5).padding(.bottom, 13)
            Text("PRODUCT LINK")
                .font(ReelieFont.ui(11, weight: .bold)).tracking(1.2).foregroundStyle(Palette.faint)
                .padding(.bottom, 9)

            linkOption(
                selected: useReelieLink,
                title: "Use Reelie's link",
                subtitle: "We route it to the best rate for you",
                trailing: { RateChip(link: .reelie(rate: 8)) }
            ) { useReelieLink = true }

            linkOption(selected: !useReelieLink, title: "Use my own affiliate link", subtitle: nil,
                       trailing: { EmptyView() }) { useReelieLink = false }

            if !useReelieLink {
                HStack(spacing: 8) {
                    Image(systemName: "link").foregroundStyle(Palette.fainter)
                    Text("Paste your link…").font(ReelieFont.ui(12.5)).foregroundStyle(Palette.fainter)
                }
                .padding(.horizontal, 12).padding(.vertical, 10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Palette.soft, in: RoundedRectangle(cornerRadius: 12))
                .padding(.leading, 28).padding(.top, 2)
            }
        }
    }

    private func linkOption<Trailing: View>(
        selected: Bool, title: String, subtitle: String?,
        @ViewBuilder trailing: () -> Trailing, action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 10) {
                ZStack {
                    Circle().strokeBorder(selected ? Palette.ink : Color(hex: 0xD5D5D5), lineWidth: 2)
                        .frame(width: 18, height: 18)
                    if selected { Circle().fill(Palette.sun).frame(width: 8, height: 8) }
                }
                VStack(alignment: .leading, spacing: 1) {
                    Text(title).font(ReelieFont.ui(13.5, weight: .medium)).foregroundStyle(Palette.ink)
                    if let subtitle {
                        Text(subtitle).font(ReelieFont.ui(11.5)).foregroundStyle(Palette.grey)
                    }
                }
                Spacer()
                trailing()
            }
            .padding(.horizontal, 12).padding(.vertical, 11)
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous)
                .strokeBorder(selected ? Palette.ink : Palette.line, lineWidth: 1.5))
        }
        .buttonStyle(.plain)
        .padding(.bottom, 8)
    }
}

// MARK: - Needs-a-look card (thumbs up/down)

private struct ReviewProductCard: View {
    let product: Product
    let onYes: () -> Void
    let onNo: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            EmojiThumb(emoji: product.emoji)
            VStack(alignment: .leading, spacing: 2) {
                Text(product.brand.uppercased())
                    .font(ReelieFont.ui(11.5, weight: .bold)).tracking(0.6).foregroundStyle(Palette.grey)
                Text(product.name).font(ReelieFont.ui(15, weight: .medium)).foregroundStyle(Palette.ink)
                HStack(spacing: 6) {
                    Text(product.evidence.rawValue)
                        .font(ReelieFont.ui(11.5, weight: .bold)).foregroundStyle(Palette.grey)
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(Palette.line, lineWidth: 1))
                    Text("\(product.timestamp) · are we right?")
                        .font(ReelieFont.ui(11.5)).foregroundStyle(Palette.faint)
                }
                .padding(.top, 3)
            }
            Spacer(minLength: 4)
            HStack(spacing: 8) {
                yn(system: "checkmark", filled: true, action: onYes)
                yn(system: "xmark", filled: false, action: onNo)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 13)
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous)
            .strokeBorder(style: StrokeStyle(lineWidth: 1.5, dash: [4]))
            .foregroundStyle(Color(hex: 0xDCDCDC)))
    }

    private func yn(system: String, filled: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: system)
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(filled ? .white : Palette.grey)
                .frame(width: 38, height: 38)
                .background(filled ? Palette.ink : .white, in: RoundedRectangle(cornerRadius: 12))
                .overlay(filled ? nil : RoundedRectangle(cornerRadius: 12).strokeBorder(Palette.line, lineWidth: 1.5))
        }
        .buttonStyle(PressableStyle())
    }
}

#Preview {
    let a = AppState(); a.onboardingComplete = true
    return NavigationStack { ApprovePageView(pageID: a.pages[0].id) }.environment(a)
}
