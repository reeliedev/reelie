import SwiftUI

/// Screen 11 — Page detail (live page stats + products).
struct PageDetailView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    let pageID: UUID
    @State private var showDelete = false

    private var page: Page? { app.pages.first { $0.id == pageID } }

    private func archive() {
        if let i = app.pages.firstIndex(where: { $0.id == pageID }) {
            app.pages[i].status = .archived
        }
        dismiss()
    }
    private func delete() {
        app.pages.removeAll { $0.id == pageID }
        dismiss()
    }

    var body: some View {
        VStack(spacing: 0) {
            // Nav bar with LIVE indicator + manage menu.
            ZStack {
                HStack {
                    BackButton { dismiss() }
                    Spacer()
                    Menu {
                        Button { archive() } label: { Label("Archive page", systemImage: "archivebox") }
                        Button(role: .destructive) { showDelete = true } label: {
                            Label("Delete page", systemImage: "trash")
                        }
                    } label: {
                        Image(systemName: "ellipsis")
                            .font(.system(size: 18, weight: .bold)).foregroundStyle(Palette.ink)
                    }
                }
                HStack(spacing: 6) {
                    Circle().fill(Palette.sun).frame(width: 7, height: 7)
                    Text("LIVE").font(ReelieFont.ui(12, weight: .bold)).tracking(1.5).foregroundStyle(Palette.ink)
                }
            }
            .frame(height: 44)
            .padding(.horizontal, 28)

            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {
                    header

                    // Stat trio.
                    HStack(spacing: 10) {
                        stat(page?.views ?? "0", "VIEWS")
                        stat(page?.shopClicks ?? "0", "SHOP CLICKS")
                        stat(page?.earned ?? "$0", "EARNED")
                    }
                    .padding(.top, 18)

                    SectionLabel(text: "PRODUCTS · \(page?.products.count ?? 0)")
                        .padding(.top, 20).padding(.bottom, 10)

                    ForEach(page?.products ?? []) { product in
                        ProductStatRow(product: product).padding(.bottom, 9)
                    }

                    Text("Earnings update as retailers confirm orders. Sales on your own links (LTK) are tracked in your LTK account.")
                        .font(ReelieFont.ui(11.5)).foregroundStyle(Palette.faint)
                        .multilineTextAlignment(.center).lineSpacing(1)
                        .padding(.horizontal, 6).padding(.top, 4)
                }
                .padding(.horizontal, 28)
                .padding(.bottom, 16)
            }

            // Bottom actions.
            VStack(spacing: 12) {
                Rectangle().fill(Palette.line).frame(height: 1.5)
                BigButton(title: "Share page", style: .sun) {}
                    .padding(.horizontal, 28)
                Button("Take page offline") { archive() }
                    .font(ReelieFont.ui(13.5, weight: .medium)).foregroundStyle(Palette.fainter)
                    .buttonStyle(.plain)
            }
            .padding(.bottom, 8)
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .confirmationDialog("Delete this page?", isPresented: $showDelete, titleVisibility: .visible) {
            Button("Delete page", role: .destructive) { delete() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This removes the page from Reelie. This can't be undone.")
        }
    }

    private var header: some View {
        VStack(spacing: 0) {
            GradientPoster(corner: 20).frame(width: 84, height: 84)
                .overlay(
                    Circle().fill(.white.opacity(0.92)).frame(width: 30, height: 30)
                        .overlay(Image(systemName: "play.fill").font(.system(size: 11)).foregroundStyle(Palette.ink))
                )
                .padding(.top, 4).padding(.bottom, 12)

            Text(page?.title ?? "").displayStyle(25).multilineTextAlignment(.center)

            HStack(spacing: 8) {
                (
                    Text(app.baseURL).foregroundStyle(Palette.grey).fontWeight(.medium)
                    + Text("\(app.handle)/\(page?.slug ?? "")").foregroundStyle(Palette.ink).fontWeight(.bold)
                )
                .font(ReelieFont.ui(12.5)).lineLimit(1)
                Button("Copy") {
                    UIPasteboard.general.string = app.fullURL(for: page?.slug ?? "")
                }
                .font(ReelieFont.ui(12, weight: .bold)).foregroundStyle(Palette.ink).buttonStyle(.plain)
            }
            .padding(.horizontal, 12).padding(.vertical, 8)
            .background(Palette.soft, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .padding(.top, 12)
        }
    }

    private func stat(_ num: String, _ label: String) -> some View {
        VStack(spacing: 3) {
            Text(num).font(ReelieFont.ui(19, weight: .bold)).foregroundStyle(Palette.ink)
            Text(label).font(ReelieFont.ui(11, weight: .bold)).tracking(0.8).foregroundStyle(Palette.faint)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 13).padding(.horizontal, 8)
        .hairlineCard(cornerRadius: 16)
    }
}

private struct ProductStatRow: View {
    let product: Product
    var body: some View {
        HStack(spacing: 11) {
            EmojiThumb(emoji: product.emoji, size: 40, corner: 11)
            VStack(alignment: .leading, spacing: 2) {
                Text(product.name).font(ReelieFont.ui(13.5, weight: .medium)).foregroundStyle(Palette.ink).lineLimit(1)
                HStack(spacing: 5) {
                    switch product.link {
                    case .reelie: Text("Reelie link").font(ReelieFont.ui(11.5)).foregroundStyle(Palette.grey)
                    case .own:    Text("Your link").font(ReelieFont.ui(11.5)).foregroundStyle(Palette.grey)
                    }
                    RateChip(link: product.link)
                }
            }
            Spacer(minLength: 4)
            VStack(alignment: .trailing, spacing: 1) {
                Text(product.earned ?? "—").font(ReelieFont.ui(13, weight: .bold)).foregroundStyle(Palette.ink)
                Text("\(product.clicks ?? 0) clicks").font(ReelieFont.ui(10.5)).foregroundStyle(Palette.faint)
            }
            Image(systemName: "chevron.right").font(.system(size: 13, weight: .bold)).foregroundStyle(Color(hex: 0xD5D5D5))
        }
        .padding(.horizontal, 13).padding(.vertical, 11)
        .hairlineCard(cornerRadius: 16)
    }
}

#Preview {
    let a = AppState(); a.onboardingComplete = true
    return NavigationStack { PageDetailView(pageID: a.pages[3].id) }.environment(a)
}
