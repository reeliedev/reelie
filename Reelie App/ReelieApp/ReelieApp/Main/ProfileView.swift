import SwiftUI

/// Profile / account tab. Adapts to the account's role: viewers see a
/// "Become a creator" entry + saved shortcut; creators see the studio settings.
struct ProfileView: View {
    @Environment(AppState.self) private var app
    @State private var becomingCreator = false
    @State private var showDeleteAccount = false

    var body: some View {
        @Bindable var app = app
        VStack(spacing: 0) {
            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {
                    identity

                    if app.isCreator {
                        creatorSections
                    } else {
                        viewerSections
                    }

                    // App (both).
                    SectionLabel(text: "APP").padding(.top, 22).padding(.bottom, 10)
                    SettingsGroup {
                        SettingsRow(icon: "🔔", title: "Notifications", subtitle: "Pages ready, money earned")
                        SettingsRow(icon: "💬", title: "Help & support", subtitle: nil)
                        SettingsRow(icon: "📄", title: "Terms & privacy", subtitle: nil)
                    }

                    if app.isCreator {
                        Button("Sign out") { app.signOut() }
                            .font(ReelieFont.ui(14, weight: .medium)).foregroundStyle(Palette.fainter)
                            .buttonStyle(.plain).padding(.top, 24)
                        Button("Delete account") { showDeleteAccount = true }
                            .font(ReelieFont.ui(12.5, weight: .medium)).foregroundStyle(.red.opacity(0.75))
                            .buttonStyle(.plain).padding(.top, 12)
                    }
                    Text("Reelie 0.1.0")
                        .font(ReelieFont.ui(11)).foregroundStyle(Color(hex: 0xDDDDDD))
                        .padding(.top, 8)
                }
                .padding(.horizontal, 28)
                .padding(.top, 14).padding(.bottom, 16)
            }

            ReelieTabBar(selection: $app.selectedTab, showsCreator: app.isCreator)
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .fullScreenCover(isPresented: $becomingCreator) { BecomeCreatorView() }
        .confirmationDialog("Delete your account?", isPresented: $showDeleteAccount, titleVisibility: .visible) {
            Button("Delete everything", role: .destructive) { Task { await app.deleteAccount() } }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This permanently deletes your account, pages, and earnings history. This can't be undone.")
        }
    }

    private var identity: some View {
        VStack(spacing: 0) {
            CreatorAvatar(gradient: app.currentUser.avatarGradient, size: 76)
            Text(app.displayName).displayStyle(24).padding(.top, 12)
            Group {
                if app.isCreator {
                    (Text(app.baseURL).foregroundStyle(Palette.grey).fontWeight(.medium)
                     + Text(app.handle).foregroundStyle(Palette.ink).fontWeight(.bold))
                } else {
                    Text("Shopping on Reelie").foregroundStyle(Palette.grey)
                }
            }
            .font(ReelieFont.ui(13)).padding(.top, 6)
        }
        .padding(.top, 8)
    }

    // MARK: viewer

    @ViewBuilder private var viewerSections: some View {
        // Become a creator.
        Button { becomingCreator = true } label: {
            HStack(spacing: 14) {
                EmojiThumb(emoji: "🎬", size: 46, corner: 12, fill: Palette.sun)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Become a creator").font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.ink)
                    Text("Turn your videos into shoppable pages").font(ReelieFont.ui(12.5)).foregroundStyle(Palette.grey)
                }
                Spacer(minLength: 4)
                Image(systemName: "chevron.right").font(.system(size: 15, weight: .bold)).foregroundStyle(Palette.faint)
            }
            .padding(15).hairlineCard(color: Palette.ink)
        }
        .buttonStyle(PressableStyle())
        .padding(.top, 22)

        SectionLabel(text: "YOU").padding(.top, 22).padding(.bottom, 10)
        SettingsGroup {
            Button { app.selectedTab = .saved } label: {
                SettingsRow(icon: "💛", title: "Saved", subtitle: "\(app.favoritePages.count) routines · \(app.favoriteCreatorList.count) creators")
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: creator

    @ViewBuilder private var creatorSections: some View {
        SectionLabel(text: "MY PAGE").padding(.top, 22).padding(.bottom, 10)
        SettingsGroup {
            SettingsRow(icon: "👤", title: "Page details", subtitle: "Name, photo, bio line")
            SettingsRow(icon: "🌐", title: "View my public page", subtitle: "What your viewers see")
        }

        SectionLabel(text: "CONNECTED ACCOUNTS").padding(.top, 22).padding(.bottom, 10)
        SettingsGroup {
            SettingsRow(icon: "▶️", title: "YouTube", subtitle: "@\(app.handle)", trailing: .watching)
            SettingsRow(icon: "📷", title: "Instagram",
                        subtitle: "Connection expired — we can't see new posts", trailing: .reconnect)
            SettingsRow(icon: "🎵", title: "TikTok", subtitle: nil, trailing: .soon)
        }

        SectionLabel(text: "LINKS & MONEY").padding(.top, 22).padding(.bottom, 10)
        SettingsGroup {
            SettingsRow(icon: "🔗", title: "Link preferences", subtitle: "Default: Reelie picks the best rate")
            SettingsRow(icon: "🏦", title: "Payouts", subtitle: "Monthly to •••• 4821")
        }
    }
}

/// A rounded, hairline-bordered group of rows.
private struct SettingsGroup<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        VStack(spacing: 0) { content }
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .hairlineCard(cornerRadius: 18)
    }
}

private struct SettingsRow: View {
    enum Trailing { case chevron, watching, reconnect, soon }
    let icon: String
    let title: String
    let subtitle: String?
    var trailing: Trailing = .chevron

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Text(icon).font(.system(size: 17)).frame(width: 24)
                VStack(alignment: .leading, spacing: 1) {
                    Text(title).font(ReelieFont.ui(14, weight: .medium)).foregroundStyle(Palette.ink)
                    if let subtitle {
                        Text(subtitle).font(ReelieFont.ui(11.5)).foregroundStyle(Palette.grey).lineLimit(1)
                    }
                }
                Spacer(minLength: 4)
                trailingView
            }
            .padding(.horizontal, 15).padding(.vertical, 14)
            Rectangle().fill(Color(hex: 0xF5F5F5)).frame(height: 1.5)
        }
    }

    @ViewBuilder private var trailingView: some View {
        switch trailing {
        case .chevron:
            Image(systemName: "chevron.right").font(.system(size: 14, weight: .bold)).foregroundStyle(Color(hex: 0xD5D5D5))
        case .watching:
            HStack(spacing: 5) {
                SunTick(size: 16)
                Text("Watching").font(ReelieFont.ui(11.5, weight: .bold)).foregroundStyle(Palette.grey)
            }
        case .reconnect:
            Text("Reconnect")
                .font(ReelieFont.ui(12, weight: .bold)).foregroundStyle(Palette.ink)
                .padding(.horizontal, 13).padding(.vertical, 8)
                .background(Palette.sun, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        case .soon:
            Text("SOON").font(ReelieFont.ui(11, weight: .bold)).tracking(0.5).foregroundStyle(Palette.faint)
        }
    }
}

#Preview {
    NavigationStack { ProfileView() }
        .environment({ let a = AppState(); a.onboardingComplete = true; a.selectedTab = .profile; return a }())
}
