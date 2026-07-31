import SwiftUI

/// Preview of an auto-generated page inside the app. Shows the routine exactly
/// as it will appear on the web (numbered steps, prices, shop links) and lets the
/// creator name their own public link before publishing.
struct GeneratedPageView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    let pageID: UUID

    @State private var editingLink = false
    @State private var showDelete = false
    @State private var stats: PageStats?
    @State private var publishing = false
    @FocusState private var linkFocused: Bool

    private var pageIndex: Int? { app.generatedPages.firstIndex { $0.id == pageID } }

    var body: some View {
        @Bindable var app = app
        if let page = app.generatedPages.first(where: { $0.id == pageID }) {
            // Bind by looking the page up by its STABLE id every access — never a
            // captured index, which would go out of bounds the instant the page is
            // deleted (loadMyPages shrinks the array) and crash the app.
            let linkBinding = Binding<String>(
                get: {
                    guard let i = app.generatedPages.firstIndex(where: { $0.id == pageID }) else { return "" }
                    return app.generatedPages[i].customSlug ?? app.generatedPages[i].slug
                },
                set: {
                    guard let i = app.generatedPages.firstIndex(where: { $0.id == pageID }) else { return }
                    app.generatedPages[i].customSlug = $0
                }
            )
            content(page: page, link: linkBinding)
        } else {
            // The page was deleted out from under this screen — pop back safely.
            Color.white.onAppear { dismiss() }
        }
    }

    private func content(page: GeneratedPage, link: Binding<String>) -> some View {
        VStack(spacing: 0) {
            // Nav bar
            ZStack {
                HStack(spacing: 16) {
                    BackButton { dismiss() }
                    Spacer()
                    NavigationLink(value: AppRoute.pageEditor(pageID: pageID)) {
                        HStack(spacing: 5) {
                            Image(systemName: "pencil").font(.system(size: 13, weight: .bold))
                            Text("Edit").font(ReelieFont.ui(13.5, weight: .bold))
                        }
                        .foregroundStyle(Palette.ink)
                    }
                    .buttonStyle(.plain)
                    if let idx = pageIndex {
                        Menu {
                            let page = app.generatedPages[idx]
                            Button {
                                Task { await app.setArchived(page, archived: !page.archived); dismiss() }
                            } label: {
                                Label(page.archived ? "Unarchive" : "Archive",
                                      systemImage: page.archived ? "tray.and.arrow.up" : "archivebox")
                            }
                            Button(role: .destructive) { showDelete = true } label: {
                                Label("Delete page", systemImage: "trash")
                            }
                        } label: {
                            Image(systemName: "ellipsis").font(.system(size: 17, weight: .bold)).foregroundStyle(Palette.ink)
                        }
                    }
                }
                StepLabel(text: pageIndex.flatMap {
                    let p = app.generatedPages[$0]
                    return p.archived ? "ARCHIVED" : (p.published ? "LIVE" : "DRAFT")
                } ?? "YOUR PAGE")
            }
            .frame(height: 44)
            .padding(.horizontal, 28)

            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {
                    header(page)
                    linkEditor(page: page, link: link)

                    // Insights + earnings — shown for live pages so creators can see
                    // how each page is performing and what it's earning.
                    if page.published, let st = stats {
                        SectionLabel(text: "INSIGHTS").padding(.top, 22).padding(.bottom, 10)
                        HStack(spacing: 10) {
                            pageStat("\(st.humanViews)", "VIEWS")
                            pageStat("\(st.aiCrawls)", "AI ANSWERS")
                            pageStat("\(st.clicks)", "CLICKS")
                        }
                        // Per-page earnings banner.
                        HStack(alignment: .center) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("EARNINGS")
                                    .font(ReelieFont.ui(10, weight: .bold)).tracking(0.5).foregroundStyle(Palette.grey)
                                Text(Money.string(st.earnings)).displayStyle(26)
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: 2) {
                                Text("\(st.sales)")
                                    .font(ReelieFont.ui(16, weight: .bold)).foregroundStyle(Palette.ink)
                                Text(st.sales == 1 ? "SALE" : "SALES")
                                    .font(ReelieFont.ui(10, weight: .bold)).tracking(0.5).foregroundStyle(Palette.faint)
                            }
                        }
                        .padding(.horizontal, 16).padding(.vertical, 14)
                        .frame(maxWidth: .infinity)
                        .background(Palette.sun.opacity(0.16), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                        .padding(.top, 10)
                        if !st.aiByEngine.isEmpty {
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 7) {
                                    ForEach(st.aiByEngine) { e in
                                        HStack(spacing: 5) {
                                            Text(e.engine).font(ReelieFont.ui(11.5, weight: .semibold))
                                            Text("\(e.count)").font(ReelieFont.ui(11.5, weight: .bold)).foregroundStyle(Palette.grey)
                                        }
                                        .padding(.horizontal, 11).padding(.vertical, 6)
                                        .background(Palette.soft, in: Capsule()).foregroundStyle(Palette.ink)
                                    }
                                }
                            }
                            .padding(.top, 9)
                        }
                    }

                    if !page.intro.isEmpty {
                        Text(page.intro)
                            .font(ReelieFont.ui(15)).foregroundStyle(Palette.ink).lineSpacing(3)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.top, 20)
                    }

                    SectionLabel(text: "THE ROUTINE")
                        .padding(.top, 22).padding(.bottom, 12)

                    // Rich preview — plays the per-step clip, exactly like the public page.
                    ForEach(Array(page.products.enumerated()), id: \.element.id) { i, product in
                        PreviewStepRow(number: i + 1, product: product,
                                       pageHandle: page.handle, pageSlug: page.pathSlug).padding(.bottom, 11)
                    }

                    Text(page.disclosure)
                        .font(ReelieFont.ui(11.5)).foregroundStyle(Palette.faint)
                        .multilineTextAlignment(.center)
                        .padding(.top, 6).padding(.horizontal, 16)
                }
                .padding(.horizontal, 28)
                .padding(.bottom, 16)
            }

            // Bottom publish / unpublish
            VStack(spacing: 12) {
                Rectangle().fill(Palette.line).frame(height: 1.5)
                if page.published {
                    BigButton(title: publishing ? "…" : "Unpublish", style: .outline) {
                        guard !publishing else { return }
                        publishing = true
                        Task { await app.setPublished(page, published: false); publishing = false; dismiss() }
                    }
                    .padding(.horizontal, 28)
                    Text("Live at \(page.publicURL)")
                        .font(ReelieFont.ui(12, weight: .medium)).foregroundStyle(Palette.grey)
                } else {
                    BigButton(title: publishing ? "…" : "Publish page", style: .sun) {
                        guard !publishing else { return }
                        publishing = true
                        Task {
                            await app.setPublished(page, published: true)
                            publishing = false
                            dismiss()
                        }
                    }
                    .padding(.horizontal, 28)
                    HStack(spacing: 24) {
                        NavigationLink(value: AppRoute.pageEditor(pageID: pageID)) {
                            HStack(spacing: 5) {
                                Image(systemName: "pencil").font(.system(size: 13, weight: .bold))
                                Text("Edit page").font(ReelieFont.ui(14, weight: .bold))
                            }
                            .foregroundStyle(Palette.ink)
                        }
                        .buttonStyle(.plain)
                        Button("Not now") { dismiss() }
                            .font(ReelieFont.ui(14, weight: .medium)).foregroundStyle(Palette.grey)
                            .buttonStyle(.plain)
                    }
                }
            }
            .padding(.bottom, 8)
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .task(id: page.slug) { stats = await app.pageStats(slug: page.slug) }
        .confirmationDialog("Delete this page?", isPresented: $showDelete, titleVisibility: .visible) {
            Button("Delete page", role: .destructive) {
                if let page = app.generatedPages.first(where: { $0.id == pageID }) {
                    dismiss()                                  // pop first…
                    Task { await app.deletePageAPI(page) }     // …then remove it
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This removes the page from Reelie. This can't be undone.")
        }
    }

    // A single performance tile (views / AI answers / clicks).
    private func pageStat(_ num: String, _ label: String) -> some View {
        VStack(spacing: 3) {
            Text(num).font(ReelieFont.ui(16, weight: .bold)).foregroundStyle(Palette.ink)
            Text(label).font(ReelieFont.ui(10, weight: .bold)).tracking(0.5).foregroundStyle(Palette.faint)
        }
        .frame(maxWidth: .infinity).padding(.vertical, 12)
        .hairlineCard(cornerRadius: 14)
    }

    // MARK: header

    private func header(_ page: GeneratedPage) -> some View {
        VStack(spacing: 0) {
            GradientPoster(corner: 22)
                .frame(width: 96, height: 96)
                .overlay(Text(page.emoji).font(.system(size: 40)))
                .padding(.top, 6).padding(.bottom, 14)

            Text(page.title).displayStyle(27).multilineTextAlignment(.center)

            Text(page.meta)
                .font(ReelieFont.ui(13.5)).foregroundStyle(Palette.grey)
                .multilineTextAlignment(.center)
                .padding(.top, 8)
        }
    }

    // MARK: "name your link" editor

    private func linkEditor(page: GeneratedPage, link: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            SectionLabel(text: "YOUR LINK")
            HStack(spacing: 2) {
                Text("reelie.io/\(page.handle)/")
                    .font(ReelieFont.ui(13.5, weight: .medium)).foregroundStyle(Palette.grey)
                TextField("your-link", text: link)
                    .font(ReelieFont.ui(13.5, weight: .bold))
                    .foregroundStyle(Palette.ink)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .focused($linkFocused)
                Spacer(minLength: 6)
                Image(systemName: "pencil")
                    .font(.system(size: 13, weight: .bold)).foregroundStyle(Palette.faint)
            }
            .padding(.horizontal, 13).padding(.vertical, 12)
            .hairlineCard(cornerRadius: 14, color: linkFocused ? Palette.ink : Palette.line)
        }
        .padding(.top, 20)
    }
}

// MARK: - One numbered step — the same rich, clip-playing row as the public page.

private struct PreviewStepRow: View {
    @Environment(AppState.self) private var app
    let number: Int
    let product: Product
    var pageHandle: String = ""
    var pageSlug: String = ""

    /// The affiliate redirect for this product — lets the creator verify where the
    /// Shop button actually goes before publishing (same as the web "Test link ↗").
    private var testLinkURL: URL? {
        guard !pageHandle.isEmpty, !pageSlug.isEmpty else { return nil }
        return (app.apiBaseURL ?? URL(string: "https://reelie.io"))?
            .appendingPathComponent("r/\(pageHandle)/\(pageSlug)/\(number)")
    }

    /// Per-step clip + poster, absolute-ized (same as the consumer RoutineView).
    private var clipURL: URL? { absolutize(product.clipUrl) }
    private var clipPosterURL: URL? { absolutize(product.clipPoster) }
    private func absolutize(_ s: String?) -> URL? {
        guard let s, !s.isEmpty else { return nil }
        if s.hasPrefix("http") { return URL(string: s) }
        return (app.apiBaseURL ?? URL(string: "https://reelie.io"))?.appendingPathComponent(s)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // The actual clip playing (muted, looping) — exactly like the web page.
            if let clip = clipURL {
                ClipPlayerView(url: clip, posterURL: clipPosterURL)
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

            // Narration — how they use it.
            if let n = product.narration {
                Text(n).font(ReelieFont.ui(13.5)).foregroundStyle(Palette.grey).lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true).padding(.top, 8)
            }

            HStack(alignment: .center, spacing: 8) {
                if let price = product.priceDisplay {
                    HStack(spacing: 4) {
                        Text(price).font(ReelieFont.ui(14, weight: .bold)).foregroundStyle(Palette.ink)
                        if product.priceEstimated {
                            Text("approx.").font(ReelieFont.ui(11)).foregroundStyle(Palette.faint)
                        }
                    }
                }
                Spacer()
                if let t = testLinkURL {
                    Link(destination: t) {
                        HStack(spacing: 3) {
                            Text("Test link").font(ReelieFont.ui(12, weight: .semibold))
                            Image(systemName: "arrow.up.right").font(.system(size: 10, weight: .bold))
                        }
                        .foregroundStyle(Palette.ink)
                        .padding(.horizontal, 12).padding(.vertical, 10)
                        .hairlineCard(cornerRadius: 12)
                    }
                    .buttonStyle(.plain)
                }
                shopButton
            }
            .padding(.top, 12)
        }
        .padding(14)
        .hairlineCard()
    }

    private var shopButton: some View {
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
    return NavigationStack {
        if let p = a.generatedPages.first {
            GeneratedPageView(pageID: p.id)
        } else {
            Text("No generated pages bundled")
        }
    }
    .environment(a)
}
