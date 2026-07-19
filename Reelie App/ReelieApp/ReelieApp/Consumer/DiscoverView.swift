import SwiftUI

/// Consumer home — browse creators and routines. Root of the Discover tab.
struct DiscoverView: View {
    @Environment(AppState.self) private var app
    @State private var query = ""

    private var matchingCreators: [Creator] {
        guard !query.isEmpty else { return app.creators }
        let q = query.lowercased()
        return app.creators.filter {
            $0.displayName.lowercased().contains(q) || $0.handle.lowercased().contains(q)
        }
    }

    private var matchingRoutines: [GeneratedPage] {
        guard !query.isEmpty else { return app.catalog }
        let q = query.lowercased()
        return app.catalog.filter {
            $0.title.lowercased().contains(q)
            || $0.creatorName.lowercased().contains(q)
            || $0.products.contains { $0.brand.lowercased().contains(q) }
        }
    }

    var body: some View {
        @Bindable var app = app
        VStack(spacing: 0) {
            Wordmark(size: 24).padding(.top, 14).padding(.bottom, 8)

            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {
                    searchField

                    // Creators rail.
                    if !matchingCreators.isEmpty {
                        SectionLabel(text: "CREATORS").padding(.top, 20).padding(.bottom, 12)
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 16) {
                                ForEach(matchingCreators) { c in
                                    NavigationLink(value: ConsumerRoute.creatorProfile(handle: c.handle)) {
                                        VStack(spacing: 7) {
                                            CreatorAvatar(gradient: c.avatarGradient, size: 64)
                                            Text(c.displayName)
                                                .font(ReelieFont.ui(12.5, weight: .bold))
                                                .foregroundStyle(Palette.ink).lineLimit(1)
                                            Text("@\(c.handle)")
                                                .font(ReelieFont.ui(11)).foregroundStyle(Palette.grey).lineLimit(1)
                                        }
                                        .frame(width: 84)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            .padding(.vertical, 2)
                        }
                    }

                    // Popular routines.
                    if !matchingRoutines.isEmpty {
                        SectionLabel(text: "POPULAR ROUTINES").padding(.top, 24).padding(.bottom, 12)
                        ForEach(matchingRoutines) { RoutineCard(page: $0) }
                    }

                    if matchingCreators.isEmpty && matchingRoutines.isEmpty {
                        Text("No matches for \u{201C}\(query)\u{201D}")
                            .font(ReelieFont.ui(14)).foregroundStyle(Palette.grey)
                            .padding(.top, 60)
                    }
                }
                .padding(.horizontal, 28)
                .padding(.bottom, 16)
            }

            ReelieTabBar(selection: $app.selectedTab, showsCreator: app.isCreator)
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .consumerDestinations()
    }

    private var searchField: some View {
        HStack(spacing: 9) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 15, weight: .medium)).foregroundStyle(Palette.grey)
            TextField("Search creators, routines, products", text: $query)
                .font(ReelieFont.ui(14)).foregroundStyle(Palette.ink)
                .textInputAutocapitalization(.never).autocorrectionDisabled()
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .background(Palette.soft, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .padding(.top, 6)
    }
}

#Preview {
    NavigationStack { DiscoverView() }
        .environment({ let a = AppState(); a.onboardingComplete = true; return a }())
}
