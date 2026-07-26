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
    @State private var showSplash = true

    var body: some View {
        ZStack {
            MainTabView()
            .task {
                await app.restoreSession()   // if a creator token is stored
                await app.refreshFromAPI()   // catalog from API (no-op unless a base URL is set)
                #if DEBUG
                // Dev-only hooks to exercise the auth + generation paths for verification.
                if ProcessInfo.processInfo.environment["REELIE_DEMO_SIGNIN"] != nil, !app.isCreator {
                    await app.signIn(email: "demo.creator@reelie.io")
                    await app.becomeCreatorAPI(handle: "demoauthcreator")
                    app.selectedTab = .pages
                }
                if ProcessInfo.processInfo.environment["REELIE_DEMO_GENERATE"] != nil, app.isCreator {
                    _ = await app.generatePage(videoId: "FaL8JhFuBBo")
                    app.selectedTab = .discover
                }
                #endif
            }

            if showSplash {
                LaunchSplashView { showSplash = false }
                    .zIndex(10)
            }
        }
    }
}

// MARK: - Animated launch splash

/// Shown once at cold launch: the Reelie wordmark settles in while a bright shine
/// sweeps across the letters (the "loading" motion), then the whole thing lifts
/// away to reveal the app. Branded warm-white backdrop matches the OS launch screen.
struct LaunchSplashView: View {
    var onFinished: () -> Void

    @State private var appear = false        // wordmark scales/fades in
    @State private var shine: CGFloat = -1   // shimmer sweep position (fraction of width)
    @State private var leaving = false       // exit lift + fade

    var body: some View {
        ZStack {
            ZStack {
                Color.white
                RadialGradient(colors: [Palette.sun.opacity(0.22), .clear],
                               center: .center, startRadius: 0, endRadius: 520)
            }
            .ignoresSafeArea()

            Wordmark(size: 52)
                .overlay { shineStreak }
                .scaleEffect(appear ? 1 : 0.9)
                .opacity(appear ? 1 : 0)
                .offset(y: leaving ? -44 : 0)
        }
        .opacity(leaving ? 0 : 1)
        .onAppear(perform: run)
    }

    /// A white streak masked to the wordmark's shape, swept left→right on repeat.
    private var shineStreak: some View {
        GeometryReader { geo in
            let w = geo.size.width
            LinearGradient(colors: [.white.opacity(0), .white.opacity(0.9), .white.opacity(0)],
                           startPoint: .leading, endPoint: .trailing)
                .frame(width: w * 0.45)
                .offset(x: shine * (w * 1.5))
                .blendMode(.plusLighter)
        }
        .mask(Wordmark(size: 52))
        .allowsHitTesting(false)
    }

    private func run() {
        withAnimation(.spring(response: 0.6, dampingFraction: 0.72)) { appear = true }
        withAnimation(.easeInOut(duration: 1.15).repeatForever(autoreverses: false).delay(0.25)) {
            shine = 1
        }
        Task {
            try? await Task.sleep(nanoseconds: 1_650_000_000)   // hold
            await MainActor.run { withAnimation(.easeInOut(duration: 0.5)) { leaving = true } }
            try? await Task.sleep(nanoseconds: 520_000_000)      // let the exit finish
            await MainActor.run { onFinished() }
        }
    }
}

#Preview {
    RootView().environment(AppState())
}

#Preview("Splash") {
    LaunchSplashView {}
}
