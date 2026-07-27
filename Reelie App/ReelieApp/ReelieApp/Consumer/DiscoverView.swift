import SwiftUI

/// Consumer home — a full-screen vertical video feed (Reels/Shorts) of creators'
/// clips, with the tab bar below. Root of the Discover tab.
struct DiscoverView: View {
    @Environment(AppState.self) private var app

    var body: some View {
        @Bindable var app = app
        ReelsFeedView()
            // Tab bar rides in the bottom safe area; the video fills behind it.
            .safeAreaInset(edge: .bottom, spacing: 0) {
                ReelieTabBar(selection: $app.selectedTab, showsCreator: app.isCreator)
            }
            .overlay(alignment: .topTrailing) {
                NavigationLink(value: ConsumerRoute.search) {
                    Image(systemName: "magnifyingglass")
                        .font(.system(size: 18, weight: .semibold)).foregroundStyle(.white)
                        .shadow(color: .black.opacity(0.45), radius: 6)
                        .frame(width: 40, height: 40)
                }
                .buttonStyle(.plain)
                .padding(.top, 52).padding(.trailing, 10)
            }
            .background(.white)
            .navigationBarBackButtonHidden(true)
            .toolbar(.hidden, for: .navigationBar)
            .consumerDestinations()
    }
}

#Preview {
    NavigationStack { DiscoverView() }
        .environment({ let a = AppState(); a.onboardingComplete = true; return a }())
}
