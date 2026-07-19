import SwiftUI

/// Favorites — saved routines + saved creators. Root of the Saved tab.
struct SavedView: View {
    @Environment(AppState.self) private var app

    /// Recommendations seeded from what the user saved: creators using a product
    /// that appears in any saved routine.
    private var becauseYouSaved: [(creator: Creator, reason: String)] {
        var seen = Set<String>()
        var out: [(creator: Creator, reason: String)] = []
        for page in app.favoritePages {
            for product in page.products {
                for c in app.creatorsUsing(brand: product.brand, name: product.name, excluding: page.handle)
                where !seen.contains(c.handle) && !app.favoriteCreators.contains(c.handle) {
                    seen.insert(c.handle)
                    out.append((creator: c, reason: "Also uses \(product.brand)"))
                }
            }
        }
        return Array(out.prefix(8))
    }

    var body: some View {
        @Bindable var app = app
        VStack(spacing: 0) {
            HStack {
                Text("Saved").displayStyle(26)
                Spacer()
            }
            .padding(.horizontal, 28).padding(.top, 16).padding(.bottom, 4)

            if app.favoritePages.isEmpty && app.favoriteCreatorList.isEmpty {
                emptyState
            } else {
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 0) {
                        if !app.favoriteCreatorList.isEmpty {
                            SectionLabel(text: "CREATORS").padding(.top, 16).padding(.bottom, 12)
                            ForEach(app.favoriteCreatorList) { c in
                                NavigationLink(value: ConsumerRoute.creatorProfile(handle: c.handle)) {
                                    HStack(spacing: 13) {
                                        CreatorAvatar(gradient: c.avatarGradient, size: 46)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(c.displayName).font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.ink)
                                            Text("@\(c.handle)").font(ReelieFont.ui(12.5)).foregroundStyle(Palette.grey)
                                        }
                                        Spacer()
                                        Image(systemName: "chevron.right").font(.system(size: 15, weight: .bold)).foregroundStyle(Color(hex: 0xD5D5D5))
                                    }
                                    .padding(14).hairlineCard().padding(.bottom, 10)
                                }
                                .buttonStyle(.plain)
                            }
                        }

                        if !app.favoritePages.isEmpty {
                            SectionLabel(text: "ROUTINES").padding(.top, 18).padding(.bottom, 12)
                            ForEach(app.favoritePages) { RoutineCard(page: $0) }
                        }

                        RecoRail(title: "BECAUSE YOU SAVED THESE", items: becauseYouSaved)
                            .padding(.top, 16)
                    }
                    .padding(.horizontal, 28).padding(.bottom, 16)
                }
            }

            ReelieTabBar(selection: $app.selectedTab, showsCreator: app.isCreator)
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .consumerDestinations()
    }

    private var emptyState: some View {
        VStack(spacing: 0) {
            Spacer()
            Text("💛").font(.system(size: 44))
            Text("Nothing saved yet")
                .displayStyle(24).padding(.top, 14)
            Text("Tap the heart on any creator or routine to keep it here.")
                .font(ReelieFont.ui(15)).foregroundStyle(Palette.grey)
                .multilineTextAlignment(.center).frame(maxWidth: 260).lineSpacing(2).padding(.top, 10)
            Button {
                app.selectedTab = .discover
            } label: {
                Text("Browse creators")
                    .font(ReelieFont.ui(16, weight: .bold)).foregroundStyle(Palette.ink)
                    .frame(maxWidth: .infinity).frame(height: 54)
                    .background(Palette.sun, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            }
            .buttonStyle(PressableStyle())
            .padding(.top, 28).padding(.horizontal, 28)
            Spacer(); Spacer()
        }
        .padding(.horizontal, 28)
    }
}

#Preview {
    let a = AppState(); a.onboardingComplete = true
    a.favoriteCreators = ["mariskincare"]; a.favorites = ["mariskincare/night-routine"]
    return NavigationStack { SavedView() }.environment(a)
}
