import SwiftUI

/// Screen 02 — Connect your socials. Real OAuth: tapping "Connect" opens the
/// platform's consent flow (backend `/me/connect/{platform}`) and, on success,
/// the row flips to "Connected" with the fetched handle. TikTok is staged.
struct ConnectSocialsView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    var onContinue: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            OnboardingNav(step: "STEP 1 OF 2", onBack: { dismiss() })

            VStack(spacing: 12) {
                Text("Connect your socials").displayStyle(30)
                    .multilineTextAlignment(.center)
                Text("Reelie reads your videos and builds shoppable, AI-discoverable pages from them.")
                    .font(ReelieFont.ui(15))
                    .foregroundStyle(Palette.grey)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 290)
                    .lineSpacing(2)
            }
            .padding(.top, 26)

            Spacer()

            ConnectAccountsList()

            Spacer()

            (
                Text("Reelie only ")
                + Text("reads the posts you publish").foregroundStyle(Palette.grey).fontWeight(.medium)
                + Text(". We never post, message, or change anything on your accounts.")
            )
            .font(ReelieFont.ui(12.5))
            .foregroundStyle(Palette.fainter)
            .multilineTextAlignment(.center)
            .frame(maxWidth: 280)
            .lineSpacing(2)

            VStack(spacing: 14) {
                BigButton(title: "Continue", style: .sun, action: onContinue)
                Button("I'll do this later", action: onContinue)
                    .font(ReelieFont.ui(14, weight: .medium))
                    .foregroundStyle(Palette.grey)
                    .buttonStyle(.plain)
            }
            .padding(.top, 18)
            .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .task { await app.loadConnections() }
    }
}

/// Reusable list of connectable platforms (Instagram / YouTube / TikTok-soon).
/// Loads current connection state and reflects connect/disconnect live.
struct ConnectAccountsList: View {
    @Environment(AppState.self) private var app
    private let platforms: [Platform] = [.instagram, .youtube, .tiktok]

    var body: some View {
        VStack(spacing: 14) {
            ForEach(platforms) { platform in
                SocialRow(platform: platform)
            }
        }
        .task { await app.loadConnections() }
    }
}

/// One platform row. State comes from `app.connections`; "Connect" runs the real
/// OAuth flow. TikTok (no `connectKey`) shows "SOON".
private struct SocialRow: View {
    @Environment(AppState.self) private var app
    let platform: Platform

    @State private var busy = false

    private var key: String? { platform.connectKey }
    private var connected: ConnectionDTO? { key.flatMap { app.connection($0) } }

    var body: some View {
        HStack(spacing: 14) {
            platformIcon
            VStack(alignment: .leading, spacing: 1) {
                Text(platform.rawValue)
                    .font(ReelieFont.ui(16, weight: .medium))
                    .foregroundStyle(Palette.ink)
                if let hint {
                    Text(hint)
                        .font(ReelieFont.ui(12))
                        .foregroundStyle(Palette.faint)
                }
            }
            Spacer()
            trailing
        }
        .padding(.horizontal, 18)
        .frame(height: 64)
        .hairlineCard(color: connected != nil ? Palette.ink : Palette.line)
        .opacity(key == nil ? 0.45 : 1)
    }

    private var platformIcon: some View {
        RoundedRectangle(cornerRadius: 6, style: .continuous)
            .fill(platform.tint)
            .frame(width: 26, height: 26)
            .overlay(
                Image(systemName: platform.symbol)
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(.white)
            )
    }

    @ViewBuilder private var trailing: some View {
        if let c = connected {
            HStack(spacing: 6) {
                SunTick(size: 18)
                Text("Connected").font(ReelieFont.ui(13.5, weight: .bold)).foregroundStyle(Palette.ink)
            }
            .contextMenu {
                Button("Disconnect", role: .destructive) {
                    Task { if let k = key { await app.disconnectPlatform(k) } }
                }
            }
            .accessibilityLabel("\(platform.rawValue) connected as \(c.username)")
        } else if key == nil {
            Text("SOON").font(ReelieFont.ui(12, weight: .bold)).tracking(0.5).foregroundStyle(Palette.faint)
        } else if busy {
            ProgressView().tint(Palette.ink)
        } else {
            PillButton(title: "Connect", style: .ink) { Task { await connect() } }
        }
    }

    private func connect() async {
        guard let k = key, !busy else { return }
        busy = true
        _ = await app.connectPlatform(k)
        busy = false
    }

    private var hint: String? {
        if let c = connected { return "@\(c.username)" }
        switch platform {
        case .instagram: return "Reels & posts"
        case .youtube:   return "Videos & Shorts"
        case .tiktok:    return nil
        }
    }
}

/// Shared onboarding nav header (back chevron + centered step label).
struct OnboardingNav: View {
    let step: String
    var onBack: (() -> Void)? = nil

    var body: some View {
        ZStack {
            if let onBack {
                HStack {
                    BackButton(action: onBack)
                    Spacer()
                }
            }
            StepLabel(text: step)
        }
        .frame(height: 44)
    }
}

#Preview {
    NavigationStack { ConnectSocialsView(onContinue: {}) }.environment(AppState())
}
