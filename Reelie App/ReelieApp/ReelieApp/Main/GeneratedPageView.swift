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
        if let idx = pageIndex {
            let linkBinding = Binding<String>(
                get: { app.generatedPages[idx].customSlug ?? app.generatedPages[idx].slug },
                set: { app.generatedPages[idx].customSlug = $0 }
            )
            content(page: app.generatedPages[idx], link: linkBinding)
        } else {
            Text("Page not found").font(ReelieFont.ui(15)).foregroundStyle(Palette.grey)
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
                    if app.showingAPIPages, let idx = pageIndex {
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

                    // Per-page analytics: views + AI answer-engine crawls + clicks.
                    if let st = stats, (st.humanViews + st.aiCrawls + st.clicks) > 0 {
                        SectionLabel(text: "PERFORMANCE").padding(.top, 22).padding(.bottom, 10)
                        HStack(spacing: 10) {
                            pageStat("\(st.humanViews)", "VIEWS")
                            pageStat("\(st.aiCrawls)", "AI ANSWERS")
                            pageStat("\(st.clicks)", "CLICKS")
                        }
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

                    SectionLabel(text: "THE ROUTINE")
                        .padding(.top, 22).padding(.bottom, 12)

                    ForEach(Array(page.products.enumerated()), id: \.element.id) { i, product in
                        StepRow(number: i + 1, product: product).padding(.bottom, 11)
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
                            // Real API pages go live via the backend; mock/offline just closes.
                            if app.showingAPIPages { await app.setPublished(page, published: true) }
                            publishing = false
                            dismiss()
                        }
                    }
                    .padding(.horizontal, 28)
                    Button("Not now") { dismiss() }
                        .font(ReelieFont.ui(14, weight: .medium)).foregroundStyle(Palette.grey)
                        .buttonStyle(.plain)
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
                if let idx = pageIndex {
                    let page = app.generatedPages[idx]
                    Task { await app.deletePageAPI(page); dismiss() }
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

// MARK: - One numbered product row (mirrors the public web page's .step)

private struct StepRow: View {
    let number: Int
    let product: Product

    var body: some View {
        HStack(spacing: 13) {
            Text("\(number)")
                .font(ReelieFont.display(16)).foregroundStyle(Palette.faint)
                .frame(width: 18)
            EmojiThumb(emoji: product.emoji, size: 50)
            VStack(alignment: .leading, spacing: 2) {
                if !product.brand.isEmpty {
                    Text(product.brand.uppercased())
                        .font(ReelieFont.ui(11, weight: .bold)).tracking(0.6)
                        .foregroundStyle(Palette.grey)
                }
                Text(product.name)
                    .font(ReelieFont.ui(14.5, weight: .medium)).foregroundStyle(Palette.ink)
                    .fixedSize(horizontal: false, vertical: true)
                if let note = product.note {
                    Text("\"\(note)\"")
                        .font(ReelieFont.ui(11.5)).foregroundStyle(Palette.grey).italic()
                        .padding(.top, 1)
                }
                priceLine.padding(.top, 4)
            }
            Spacer(minLength: 4)
            shopButton
        }
        .padding(.horizontal, 14).padding(.vertical, 13)
        .hairlineCard()
    }

    @ViewBuilder private var priceLine: some View {
        if let price = product.priceDisplay {
            HStack(spacing: 4) {
                Text(price).font(ReelieFont.ui(12.5, weight: .bold)).foregroundStyle(Palette.ink)
                if product.priceEstimated {
                    Text("approx.").font(ReelieFont.ui(11.5)).foregroundStyle(Palette.faint)
                }
            }
        }
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
