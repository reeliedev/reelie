import SwiftUI

enum OnboardingStep: Hashable {
    case pickRole
    case connectSocials
    case claimPage
    case notifications
}

/// Onboarding: Login › pick role. Viewers go straight into the app; creators
/// continue Connect socials › Claim page › Notifications.
struct OnboardingFlow: View {
    @Environment(AppState.self) private var app
    @State private var path: [OnboardingStep] = []

    var body: some View {
        NavigationStack(path: $path) {
            LoginView(onContinue: { path.append(.pickRole) })
                .navigationDestination(for: OnboardingStep.self) { step in
                    switch step {
                    case .pickRole:
                        PickRoleView(
                            onBrowse: {
                                app.currentUser.role = .viewer
                                app.selectedTab = .discover
                                app.onboardingComplete = true
                            },
                            onCreator: { path.append(.connectSocials) }
                        )
                    case .connectSocials:
                        ConnectSocialsView(onContinue: { path.append(.claimPage) })
                    case .claimPage:
                        ClaimPageView(onContinue: { path.append(.notifications) })
                    case .notifications:
                        NotificationsView()
                    }
                }
        }
        .tint(Palette.ink)
    }
}
