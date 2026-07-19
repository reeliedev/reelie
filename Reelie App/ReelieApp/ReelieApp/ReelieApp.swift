import SwiftUI

@main
struct ReelieMainApp: App {
    @State private var app: AppState

    init() {
        let a = AppState()
        #if DEBUG
        // Debug-only launch presets for screenshotting (compiled out of release).
        switch ProcessInfo.processInfo.environment["REELIE_START"] {
        case "discover":
            a.onboardingComplete = true; a.currentUser.role = .viewer; a.selectedTab = .discover
        case "saved":
            a.onboardingComplete = true; a.currentUser.role = .viewer; a.selectedTab = .saved
            a.favoriteCreators = ["mariskincare"]
            a.favorites = ["mariskincare/night-routine", "thefacefiles/soft-glam"]
        case "creator":
            a.onboardingComplete = true; a.currentUser.role = .both; a.selectedTab = .pages
        case "earnings":
            a.onboardingComplete = true; a.currentUser.role = .both; a.selectedTab = .earnings
        case "profile":
            a.onboardingComplete = true; a.currentUser.role = .viewer; a.selectedTab = .profile
        case "creatorprofile":
            a.onboardingComplete = true; a.currentUser.role = .viewer; a.selectedTab = .discover
            a.consumerPath = [.creatorProfile(handle: "thefacefiles")]
        case "routine":
            a.onboardingComplete = true; a.currentUser.role = .viewer; a.selectedTab = .discover
            a.consumerPath = [.routine(key: "mariskincare/night-routine")]
        case "editor":
            a.onboardingComplete = true; a.currentUser.role = .both; a.selectedTab = .pages
            if let first = a.generatedPages.first {
                a.homePath = [.generatedPage(pageID: first.id), .pageEditor(pageID: first.id)]
            }
        default:
            break
        }
        #endif
        _app = State(initialValue: a)
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(app)
                .tint(Palette.ink)
        }
    }
}

/// The app opens straight into the browsable experience as a guest — consumers
/// never sign in. Auth happens only on the creator path (Become a creator).
struct RootView: View {
    @Environment(AppState.self) private var app

    var body: some View {
        MainTabView()
            .task {
                await app.restoreSession()   // if a creator token is stored
                await app.refreshFromAPI()   // catalog from API (no-op unless a base URL is set)
                #if DEBUG
                // Dev-only hooks to exercise the auth + generation paths for verification.
                if ProcessInfo.processInfo.environment["REELIE_DEMO_SIGNIN"] != nil, !app.isCreator {
                    await app.signIn(email: "demo.creator@reelie.shop")
                    await app.becomeCreatorAPI(handle: "demoauthcreator")
                    app.selectedTab = .pages
                }
                if ProcessInfo.processInfo.environment["REELIE_DEMO_GENERATE"] != nil, app.isCreator {
                    _ = await app.generatePage(videoId: "FaL8JhFuBBo")
                    app.selectedTab = .discover
                }
                #endif
            }
    }
}

#Preview {
    RootView().environment(AppState())
}
