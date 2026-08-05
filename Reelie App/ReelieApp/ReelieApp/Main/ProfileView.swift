import SwiftUI

/// Profile / account tab. Adapts to the account's role: viewers see a
/// "Become a creator" entry + saved shortcut; creators see the studio settings.
struct ProfileView: View {
    @Environment(AppState.self) private var app
    @State private var becomingCreator = false
    @State private var signingIn = false
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
                        Link(destination: URL(string: "mailto:hello@reelie.io")!) {
                            SettingsRow(icon: "💬", title: "Help & support", subtitle: "hello@reelie.io")
                        }.buttonStyle(.plain)
                        Link(destination: URL(string: "https://reelie.io/terms")!) {
                            SettingsRow(icon: "📄", title: "Terms of Service", subtitle: nil)
                        }.buttonStyle(.plain)
                        Link(destination: URL(string: "https://reelie.io/privacy")!) {
                            SettingsRow(icon: "🔒", title: "Privacy Policy", subtitle: nil)
                        }.buttonStyle(.plain)
                    }

                    // Blocked accounts (UGC safety) — undo a block.
                    if !app.blockedCreators.isEmpty {
                        SectionLabel(text: "BLOCKED ACCOUNTS").padding(.top, 22).padding(.bottom, 10)
                        SettingsGroup {
                            ForEach(Array(app.blockedCreators).sorted(), id: \.self) { h in
                                HStack {
                                    Text("@\(h)").font(ReelieFont.ui(14.5, weight: .medium)).foregroundStyle(Palette.ink)
                                    Spacer()
                                    Button("Unblock") { app.unblockCreator(h) }
                                        .font(ReelieFont.ui(13, weight: .bold)).foregroundStyle(Palette.ink)
                                        .buttonStyle(.plain)
                                }
                                .padding(.horizontal, 15).padding(.vertical, 13)
                            }
                        }
                    }

                    if app.isSignedIn {
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
        .fullScreenCover(isPresented: $signingIn) {
            // Plain sign-in for returning users. On success /me sets their real role,
            // so a returning creator lands back in their studio (no re-claiming a handle).
            LoginView(onContinue: {
                signingIn = false
                Task {
                    await app.restoreSession()
                    if app.isCreator { await app.loadMyPages() } else { await app.loadFavorites() }
                }
            }, onCancel: { signingIn = false })
        }
        .confirmationDialog("Delete your account?", isPresented: $showDeleteAccount, titleVisibility: .visible) {
            Button("Delete everything", role: .destructive) { Task { await app.deleteAccount() } }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This permanently deletes your account, pages, and earnings history. This can't be undone.")
        }
    }

    /// Name shown on the profile: real name when signed in (falling back to email,
    /// then "You"), and "Guest" when just browsing — never a stale/mock identity.
    private var profileName: String {
        guard app.isSignedIn else { return "Guest" }
        if !app.displayName.isEmpty { return app.displayName }
        return app.currentUser.email.isEmpty ? "You" : app.currentUser.email
    }

    private var identity: some View {
        VStack(spacing: 0) {
            CreatorAvatar(gradient: app.currentUser.avatarGradient, size: 76)
            Text(profileName).displayStyle(24).padding(.top, 12)
            Group {
                if app.isCreator {
                    (Text(app.baseURL).foregroundStyle(Palette.grey).fontWeight(.medium)
                     + Text(app.handle).foregroundStyle(Palette.ink).fontWeight(.bold))
                } else if app.isSignedIn {
                    Text(app.currentUser.email.isEmpty ? "Shopping on Reelie" : app.currentUser.email)
                        .foregroundStyle(Palette.grey)
                } else {
                    Text("You're browsing as a guest").foregroundStyle(Palette.grey)
                }
            }
            .font(ReelieFont.ui(13)).padding(.top, 6)
        }
        .padding(.top, 8)
    }

    // MARK: viewer

    /// Shared layout for the profile action cards (Sign in / Become a creator).
    private func profileCard(emoji: String, fill: Color, title: String, subtitle: String) -> some View {
        HStack(spacing: 14) {
            EmojiThumb(emoji: emoji, size: 46, corner: 12, fill: fill)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.ink)
                Text(subtitle).font(ReelieFont.ui(12.5)).foregroundStyle(Palette.grey)
            }
            Spacer(minLength: 4)
            Image(systemName: "chevron.right").font(.system(size: 15, weight: .bold)).foregroundStyle(Palette.faint)
        }
        .padding(15).hairlineCard(color: Palette.ink)
    }

    @ViewBuilder private var viewerSections: some View {
        // Sign in — for RETURNING users (existing creators/accounts) to log back in.
        // Guests only: once signed in, this is replaced by account actions below.
        if !app.isSignedIn {
            Button { signingIn = true } label: {
                profileCard(emoji: "👋", fill: Palette.soft, title: "Sign in",
                            subtitle: "Already have an account? Log back in")
            }
            .buttonStyle(PressableStyle())
            .padding(.top, 22)
        }

        // Become a creator — sign up + claim a handle (a different action from Sign in).
        Button { becomingCreator = true } label: {
            profileCard(emoji: "🎬", fill: Palette.sun, title: "Become a creator",
                        subtitle: "Turn your videos into shoppable pages")
        }
        .buttonStyle(PressableStyle())
        .padding(.top, app.isSignedIn ? 22 : 12)

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
            Link(destination: URL(string: app.profileURL) ?? URL(string: "https://reelie.io")!) {
                SettingsRow(icon: "🌐", title: "View my public page", subtitle: "What your viewers see")
            }.buttonStyle(.plain)
        }

        SectionLabel(text: "CONNECTED ACCOUNTS").padding(.top, 22).padding(.bottom, 10)
        SettingsGroup {
            connectionRow("youtube", "▶️", "YouTube")
            connectionRow("instagram", "📷", "Instagram")
            SettingsRow(icon: "🎵", title: "TikTok", subtitle: "Coming soon", trailing: .soon)
        }
        .task { await app.loadConnections() }
    }

    /// Real connection status — connected shows the linked @username, otherwise
    /// "Not connected" (managed in the New-page flow). No fake/hardcoded state.
    private func connectionRow(_ platform: String, _ icon: String, _ label: String) -> some View {
        let conn = app.connection(platform)
        return SettingsRow(icon: icon, title: label,
                           subtitle: conn.map { "@\($0.username)" } ?? "Not connected",
                           trailing: conn != nil ? .connected : .blank)
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
    enum Trailing { case chevron, watching, reconnect, soon, connected, blank }
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
        case .connected:
            HStack(spacing: 5) {
                SunTick(size: 16)
                Text("Connected").font(ReelieFont.ui(11.5, weight: .bold)).foregroundStyle(Palette.grey)
            }
        case .blank:
            EmptyView()
        }
    }
}

#Preview {
    NavigationStack { ProfileView() }
        .environment({ let a = AppState(); a.onboardingComplete = true; a.selectedTab = .profile; return a }())
}
