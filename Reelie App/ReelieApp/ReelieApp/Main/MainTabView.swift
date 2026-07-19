import SwiftUI

/// Routes pushed within a tab's NavigationStack.
enum AppRoute: Hashable {
    case pickVideo
    case approve(pageID: UUID)
    case pageLive(slug: String, title: String)
    case pageDetail(pageID: UUID)
    case generatedPage(pageID: UUID)
    case pageEditor(pageID: UUID)
}

/// Consumer routes (pushed within the Discover / Saved stacks).
enum ConsumerRoute: Hashable {
    case creatorProfile(handle: String)
    case routine(key: String)
}

/// The main app. Consumers get Discover / Saved / Profile; creators additionally
/// get the Pages / Earnings studio tabs. Each tab owns its own NavigationStack.
struct MainTabView: View {
    @Environment(AppState.self) private var app

    var body: some View {
        @Bindable var app = app
        switch app.selectedTab {
        case .discover:
            NavigationStack(path: $app.consumerPath) { DiscoverView() }
        case .saved:
            NavigationStack(path: $app.consumerPath) { SavedView() }
        case .pages:
            NavigationStack(path: $app.homePath) { HomeView() }
        case .earnings:
            NavigationStack { EarningsView() }
        case .profile:
            NavigationStack { ProfileView() }
        }
    }
}

#Preview {
    MainTabView().environment({ let a = AppState(); a.onboardingComplete = true; return a }())
}
