import SwiftUI

/// Screens 05 (empty) & 10 (list) — the Pages tab.
struct HomeView: View {
    @Environment(AppState.self) private var app

    var body: some View {
        @Bindable var app = app
        VStack(spacing: 0) {
            // Header wordmark + new-page entry.
            ZStack {
                Wordmark(size: 24)
                HStack {
                    Spacer()
                    NavigationLink(value: AppRoute.pickVideo) {
                        HStack(spacing: 4) {
                            Image(systemName: "plus").font(.system(size: 13, weight: .bold))
                            Text("New").font(ReelieFont.ui(13.5, weight: .bold))
                        }
                        .foregroundStyle(Palette.ink)
                        .padding(.horizontal, 13).padding(.vertical, 7)
                        .background(Palette.sun, in: Capsule())
                    }
                    .buttonStyle(.plain)
                }
                .padding(.horizontal, 28)
            }
            .padding(.top, 14)
            .padding(.bottom, 4)

            if (app.showingAPIPages ? app.generatedPages.isEmpty : app.pages.isEmpty) {
                HomeEmptyState()
            } else {
                HomeList()
            }

            ReelieTabBar(selection: $app.selectedTab, showsCreator: app.isCreator)
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .navigationDestination(for: AppRoute.self) { route in
            switch route {
            case .pickVideo:
                PickVideoView()
            case .approve(let id):
                ApprovePageView(pageID: id)
            case .pageLive(let slug, let title):
                PageLiveView(slug: slug, title: title)
            case .pageDetail(let id):
                PageDetailView(pageID: id)
            case .generatedPage(let id):
                GeneratedPageView(pageID: id)
            case .pageEditor(let id):
                PageEditorView(pageID: id)
            }
        }
        .task { await app.loadMyPages() }
    }
}

// MARK: - Empty state (screen 05)

private struct HomeEmptyState: View {
    @Environment(AppState.self) private var app

    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            HStack(spacing: 8) {
                Circle().fill(Palette.sun).frame(width: 8, height: 8)
                Text("Watching @\(app.handle)").font(ReelieFont.ui(13, weight: .bold)).foregroundStyle(Palette.ink)
            }
            .padding(.horizontal, 16).padding(.vertical, 9)
            .background(Palette.soft, in: Capsule())

            Text("Post like you\nalways do")
                .displayStyle(28)
                .multilineTextAlignment(.center)
                .padding(.top, 22)
            Text("The moment your next video is up, we'll build its page and put it right here.")
                .font(ReelieFont.ui(15)).foregroundStyle(Palette.grey)
                .multilineTextAlignment(.center).frame(maxWidth: 280).lineSpacing(2)
                .padding(.top, 12)

            // Ghost placeholder card.
            HStack(spacing: 13) {
                RoundedRectangle(cornerRadius: 14).fill(Palette.soft).frame(width: 54, height: 54)
                VStack(alignment: .leading, spacing: 8) {
                    RoundedRectangle(cornerRadius: 6).fill(Palette.soft).frame(height: 11)
                    RoundedRectangle(cornerRadius: 6).fill(Palette.soft).frame(width: 100, height: 11)
                }
                RoundedRectangle(cornerRadius: 11).fill(Palette.soft).frame(width: 64, height: 34)
            }
            .padding(14)
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .strokeBorder(style: StrokeStyle(lineWidth: 1.5, dash: [5]))
                    .foregroundStyle(Color(hex: 0xE0E0E0))
            )
            .opacity(0.75)
            .padding(.top, 30)

            Text("Your first page will appear here")
                .font(ReelieFont.ui(12)).foregroundStyle(Palette.faint).padding(.top, 10)

            NavigationLink(value: AppRoute.pickVideo) {
                Text("Make a page from a past video")
                    .font(ReelieFont.ui(16, weight: .bold)).foregroundStyle(Palette.ink)
                    .frame(maxWidth: .infinity).frame(height: 54)
                    .background(Palette.sun, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            }
            .padding(.top, 28)

            Spacer()
        }
        .padding(.horizontal, 28)
    }
}

// MARK: - Populated list (screen 10)

private struct HomeList: View {
    @Environment(AppState.self) private var app

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(spacing: 0) {
                if app.showingAPIPages {
                    // Account-scoped: the creator's own published pages from the API.
                    let active = app.generatedPages.filter { !$0.archived }
                    let archived = app.generatedPages.filter { $0.archived }
                    if !active.isEmpty {
                        SectionLabel(text: "YOUR PAGES").padding(.top, 18).padding(.bottom, 10)
                        ForEach(active) { page in GeneratedPageCard(page: page) }
                    }
                    if !archived.isEmpty {
                        SectionLabel(text: "ARCHIVED").padding(.top, 18).padding(.bottom, 10)
                        ForEach(archived) { page in GeneratedPageCard(page: page).opacity(0.6) }
                    }
                } else {
                    mockSections
                }
            }
            .padding(.horizontal, 28)
            .padding(.bottom, 16)
        }
    }

    @ViewBuilder private var mockSections: some View {
        Group {
            if !app.generatedPages.isEmpty {
                SectionLabel(text: "JUST GENERATED").padding(.top, 18).padding(.bottom, 10)
                ForEach(app.generatedPages) { page in GeneratedPageCard(page: page) }
            }
                if !app.pagesNeedingReview.isEmpty {
                    SectionLabel(text: "NEEDS YOUR OK").padding(.top, 18).padding(.bottom, 10)
                    ForEach(app.pagesNeedingReview) { page in PageCard(page: page) }
                }
                if !app.pagesProcessing.isEmpty {
                    SectionLabel(text: "WORKING ON IT").padding(.top, 18).padding(.bottom, 10)
                    ForEach(app.pagesProcessing) { page in PageCard(page: page) }
                }
                if !app.pagesLive.isEmpty {
                    SectionLabel(text: "LIVE").padding(.top, 18).padding(.bottom, 10)
                    ForEach(app.pagesLive) { page in PageCard(page: page) }
                }
            if !app.pagesArchived.isEmpty {
                SectionLabel(text: "ARCHIVED").padding(.top, 18).padding(.bottom, 10)
                ForEach(app.pagesArchived) { page in PageCard(page: page) }
            }
        }
    }
}

/// One card in the Home list. Trailing control depends on status.
private struct PageCard: View {
    let page: Page

    var body: some View {
        let content = HStack(spacing: 13) {
            GradientPoster(colors: [Color(hex: 0xE8E4DA), Color(hex: 0xD8D2C4)], corner: 14)
                .frame(width: 54, height: 54)
                .overlay(Text(page.emoji).font(.system(size: 22)))

            VStack(alignment: .leading, spacing: 3) {
                Text(page.title)
                    .font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.ink)
                    .lineLimit(1)
                Text(page.meta)
                    .font(ReelieFont.ui(12.5)).foregroundStyle(Palette.grey)
                    .lineLimit(1)
            }
            Spacer(minLength: 8)
            trailing
        }
        .padding(14)
        .hairlineCard(color: page.status == .needsReview ? Palette.ink : Palette.line)
        .padding(.bottom, 10)

        // Live pages navigate to detail; others aren't tappable at the row level.
        switch page.status {
        case .live:
            NavigationLink(value: AppRoute.pageDetail(pageID: page.id)) { content }
                .buttonStyle(.plain)
        default:
            content
        }
    }

    @ViewBuilder private var trailing: some View {
        switch page.status {
        case .needsReview:
            NavigationLink(value: AppRoute.approve(pageID: page.id)) {
                Text("Review")
                    .font(ReelieFont.ui(13.5, weight: .bold)).foregroundStyle(Palette.ink)
                    .padding(.horizontal, 16).padding(.vertical, 10)
                    .background(Palette.sun, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            .buttonStyle(.plain)
        case .processing:
            ProcessingDots()
        case .live:
            Image(systemName: "chevron.right")
                .font(.system(size: 15, weight: .bold)).foregroundStyle(Color(hex: 0xD5D5D5))
        case .archived:
            Text("ARCHIVED")
                .font(ReelieFont.ui(10.5, weight: .bold)).tracking(0.6).foregroundStyle(Palette.faint)
        }
    }
}

/// A card for an auto-generated page — taps through to the generated-page preview.
private struct GeneratedPageCard: View {
    let page: GeneratedPage

    var body: some View {
        NavigationLink(value: AppRoute.generatedPage(pageID: page.id)) {
            HStack(spacing: 13) {
                GradientPoster(colors: [Color(hex: 0xE8E4DA), Color(hex: 0xD8D2C4)], corner: 14)
                    .frame(width: 54, height: 54)
                    .overlay(Text(page.emoji).font(.system(size: 22)))

                VStack(alignment: .leading, spacing: 3) {
                    Text(page.title)
                        .font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.ink)
                        .lineLimit(1)
                    Text(page.meta)
                        .font(ReelieFont.ui(12.5)).foregroundStyle(Palette.grey)
                        .lineLimit(1)
                }
                Spacer(minLength: 8)
                Text("Preview")
                    .font(ReelieFont.ui(13.5, weight: .bold)).foregroundStyle(Palette.ink)
                    .padding(.horizontal, 16).padding(.vertical, 10)
                    .background(Palette.sun, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            .padding(14)
            .hairlineCard(color: Palette.ink)
            .padding(.bottom, 10)
        }
        .buttonStyle(.plain)
    }
}

/// Three pulsing dots for the "working on it" state.
private struct ProcessingDots: View {
    @State private var animate = false
    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3, id: \.self) { i in
                Circle().fill(Color(hex: 0xD5D5D5)).frame(width: 6, height: 6)
                    .opacity(animate ? 1 : 0.3)
                    .animation(.easeInOut(duration: 1.2).repeatForever().delay(Double(i) * 0.2), value: animate)
            }
        }
        .onAppear { animate = true }
    }
}

#Preview {
    NavigationStack { HomeView() }
        .environment({ let a = AppState(); a.onboardingComplete = true; return a }())
}
