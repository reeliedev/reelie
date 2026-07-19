import SwiftUI

/// Screen 04 — Notifications opt-in (final onboarding step).
struct NotificationsView: View {
    @Environment(AppState.self) private var app

    var body: some View {
        VStack(spacing: 0) {
            Color.clear.frame(height: 44) // matches nav spacer in mockup

            VStack(spacing: 12) {
                Text("Know the moment\na page is ready")
                    .displayStyle(30)
                    .multilineTextAlignment(.center)
                Text("Your page is built minutes after you post — approve it while your video is still getting views.")
                    .font(ReelieFont.ui(15))
                    .foregroundStyle(Palette.grey)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 290)
                    .lineSpacing(2)
            }
            .padding(.top, 26)

            Spacer()

            VStack(spacing: 12) {
                NotifCard(time: "now",
                          title: "Your new page is ready ✓",
                          message: "6 products found in your Reel — tap to review and go live.",
                          dimmed: false)
                NotifCard(time: "2d ago",
                          title: "First sale on your K-beauty page 🎉",
                          message: "Someone shopped the Anua toner from your link.",
                          dimmed: true)

                (
                    Text("That's all we send — ")
                    + Text("pages ready and money earned.").foregroundStyle(Palette.grey).fontWeight(.medium)
                    + Text(" No streaks, no nagging.")
                )
                .font(ReelieFont.ui(12.5))
                .foregroundStyle(Palette.faint)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 280)
                .lineSpacing(2)
                .padding(.top, 4)
            }

            Spacer()

            VStack(spacing: 14) {
                BigButton(title: "Turn on notifications", style: .sun) { finish() }
                Button("Maybe later") { finish() }
                    .font(ReelieFont.ui(14, weight: .medium))
                    .foregroundStyle(Palette.grey)
                    .buttonStyle(.plain)
            }
            .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
    }

    // Reaching this screen means the creator path was chosen — unlock the studio.
    private func finish() {
        app.currentUser.role = .both
        app.onboardingComplete = true
        app.selectedTab = .pages
    }
}

/// A single notification preview card.
private struct NotifCard: View {
    let time: String
    let title: String
    let message: String
    let dimmed: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(Palette.sun)
                .frame(width: 38, height: 38)
                .overlay(Text("R").font(ReelieFont.display(22)).foregroundStyle(Palette.ink))

            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text("Reelie").font(ReelieFont.ui(13, weight: .bold)).foregroundStyle(Palette.ink)
                    Spacer()
                    Text(time).font(ReelieFont.ui(11.5)).foregroundStyle(Palette.fainter)
                }
                Text(title).font(ReelieFont.ui(13.5, weight: .bold)).foregroundStyle(Palette.ink)
                Text(message).font(ReelieFont.ui(13)).foregroundStyle(Palette.grey).lineSpacing(1)
            }
        }
        .padding(.horizontal, 15)
        .padding(.vertical, 14)
        .background(Palette.soft, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .opacity(dimmed ? 0.5 : 1)
        .scaleEffect(dimmed ? 0.96 : 1)
    }
}

#Preview {
    NavigationStack { NotificationsView() }.environment(AppState())
}
