import SwiftUI

/// Consumer home — a full-screen vertical video feed (Reels/Shorts) of creators'
/// clips, with the tab bar below. Root of the Discover tab.
struct DiscoverView: View {
    @Environment(AppState.self) private var app

    var body: some View {
        @Bindable var app = app
        VStack(spacing: 0) {
            ReelsFeedView()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            ReelieTabBar(selection: $app.selectedTab, showsCreator: app.isCreator)
                .background(.white)
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
