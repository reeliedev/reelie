import SwiftUI
import AuthenticationServices

/// The fork right after login: browse as a viewer (default) or set up as a creator.
struct PickRoleView: View {
    var onBrowse: () -> Void
    var onCreator: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            VStack(spacing: 12) {
                Text("How do you want\nto start?")
                    .displayStyle(30)
                    .multilineTextAlignment(.center)
                Text("You can always do both later — become a creator any time from your profile.")
                    .font(ReelieFont.ui(15))
                    .foregroundStyle(Palette.grey)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 290)
                    .lineSpacing(2)
            }
            Spacer()

            VStack(spacing: 14) {
                RoleCard(emoji: "🛍️", title: "I'm here to shop",
                         subtitle: "Browse creators, save your favorites, and get recommendations.",
                         action: onBrowse)
                RoleCard(emoji: "🎬", title: "I'm a creator",
                         subtitle: "Turn my videos into shoppable pages and earn.",
                         action: onCreator)
            }

            Spacer()

            Button("Just let me browse for now") { onBrowse() }
                .font(ReelieFont.ui(14, weight: .medium))
                .foregroundStyle(Palette.grey)
                .buttonStyle(.plain)
                .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
    }
}

private struct RoleCard: View {
    let emoji: String
    let title: String
    let subtitle: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                EmojiThumb(emoji: emoji, size: 52, corner: 14)
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).font(ReelieFont.ui(16, weight: .bold)).foregroundStyle(Palette.ink)
                    Text(subtitle).font(ReelieFont.ui(13)).foregroundStyle(Palette.grey)
                        .multilineTextAlignment(.leading).lineSpacing(1)
                }
                Spacer(minLength: 6)
                Image(systemName: "chevron.right")
                    .font(.system(size: 15, weight: .bold)).foregroundStyle(Palette.faint)
            }
            .padding(15)
            .hairlineCard()
        }
        .buttonStyle(PressableStyle())
    }
}

/// Reached from the profile: real creator sign-up. Step 1 signs in (creates the
/// account), step 2 claims the handle — both hit the backend when connected, and
/// degrade to a local unlock offline.
struct BecomeCreatorView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss

    private enum Step { case signIn, claim }
    @State private var step: Step = .signIn
    @State private var email = ""
    @State private var handle = ""
    @State private var instagram = ""
    @State private var youtube = ""
    @State private var busy = false
    @State private var error: String?
    @State private var showEmail = false
    @State private var appleNonce = ""

    var body: some View {
        VStack(spacing: 0) {
            HStack { BackButton { dismiss() }; Spacer() }
                .frame(height: 44).padding(.horizontal, 28)

            switch step {
            case .signIn: signInStep
            case .claim: claimStep
            }
        }
        .background(.white)
        .tint(Palette.ink)
    }

    private var signInStep: some View {
        VStack(spacing: 0) {
            Spacer()
            VStack(spacing: 12) {
                Text("Create your\ncreator account").displayStyle(30).multilineTextAlignment(.center)
                Text("Sign in to turn your videos into shoppable pages and start earning.")
                    .font(ReelieFont.ui(15)).foregroundStyle(Palette.grey)
                    .multilineTextAlignment(.center).frame(maxWidth: 290).lineSpacing(2)
            }
            Spacer()
            VStack(spacing: 12) {
                BigButton(title: "Continue with email", style: .sun) { showEmail = true }

                SignInWithAppleButton(.signIn) { request in
                    appleNonce = AppleNonce.make()
                    request.requestedScopes = [.fullName, .email]
                    request.nonce = AppleNonce.sha256(appleNonce)
                } onCompletion: { handleApple($0) }
                .signInWithAppleButtonStyle(.black)
                .frame(height: 54).clipShape(Capsule())

                BigButton(title: busy ? "…" : "Continue with Google", style: .outline,
                          icon: Image(systemName: "g.circle.fill")) {
                    Task {
                        busy = true
                        let ok = await app.signInWithGoogle()
                        busy = false
                        if ok { afterSignedIn() } else { error = "Google sign-in didn't complete." }
                    }
                }
                if let error { Text(error).font(ReelieFont.ui(12.5)).foregroundStyle(.red).multilineTextAlignment(.center) }
            }
            .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
        .task { await app.loadAuthConfig() }
        .sheet(isPresented: $showEmail) {
            EmailSignInSheet { showEmail = false; afterSignedIn() }
                .presentationDetents([.height(360)])
        }
    }

    private func afterSignedIn() {
        handle = app.handle
        step = .claim
    }

    private func handleApple(_ result: Result<ASAuthorization, Error>) {
        guard case .success(let auth) = result,
              let cred = auth.credential as? ASAuthorizationAppleIDCredential,
              let data = cred.identityToken,
              let idToken = String(data: data, encoding: .utf8) else {
            error = "Apple sign-in was cancelled."; return
        }
        Task {
            if await app.signInWithApple(idToken: idToken, rawNonce: appleNonce) { afterSignedIn() }
            else { error = app.lastAuthError ?? "Apple sign-in failed. Please try again." }
        }
    }

    private var claimStep: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 0) {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Set up your\ncreator profile").displayStyle(30)
                    Text("Claim your link and add your socials. We verify creators over Instagram DM — so make sure your handle is right.")
                        .font(ReelieFont.ui(15)).foregroundStyle(Palette.grey).lineSpacing(2)
                }
                .padding(.top, 8)

                SectionLabel(text: "YOUR LINK").padding(.top, 26).padding(.bottom, 8)
                HStack(spacing: 2) {
                    Text(app.baseURL).font(ReelieFont.ui(16, weight: .medium)).foregroundStyle(Palette.grey)
                    TextField("yourname", text: $handle)
                        .font(ReelieFont.ui(16, weight: .bold)).foregroundStyle(Palette.ink)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                }
                .padding(.horizontal, 16).frame(height: 56).hairlineCard(cornerRadius: 16, color: Palette.ink)

                SectionLabel(text: "YOUR SOCIALS").padding(.top, 24).padding(.bottom, 8)
                socialField(icon: "📸", prefix: "instagram.com/", placeholder: "handle", text: $instagram)
                socialField(icon: "▶️", prefix: "youtube.com/@", placeholder: "handle", text: $youtube).padding(.top, 10)
                Text("Add at least one — that's how our team confirms it's really you and sends your invite.")
                    .font(ReelieFont.ui(12.5)).foregroundStyle(Palette.faint).lineSpacing(1).padding(.top, 10)

                if let error { Text(error).font(ReelieFont.ui(12.5)).foregroundStyle(.red).padding(.top, 10) }

                BigButton(title: busy ? "…" : "Apply for access", style: .sun) { Task { await doClaim() } }
                    .padding(.top, 22).padding(.bottom, 24)
            }
            .padding(.horizontal, 28)
        }
        .scrollDismissesKeyboard(.interactively)
    }

    private func socialField(icon: String, prefix: String, placeholder: String, text: Binding<String>) -> some View {
        HStack(spacing: 8) {
            Text(icon).font(.system(size: 16))
            Text(prefix).font(ReelieFont.ui(14.5, weight: .medium)).foregroundStyle(Palette.grey)
            TextField(placeholder, text: text)
                .font(ReelieFont.ui(14.5, weight: .bold)).foregroundStyle(Palette.ink)
                .textInputAutocapitalization(.never).autocorrectionDisabled()
        }
        .padding(.horizontal, 14).frame(height: 54).hairlineCard(cornerRadius: 14)
    }

    private func finish() {
        app.selectedTab = .pages
        dismiss()
    }

    private func doClaim() async {
        let ig = instagram.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: "@", with: "")
        let yt = youtube.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: "@", with: "")
        guard handle.trimmingCharacters(in: .whitespaces).count >= 3 else {
            error = "Pick a handle (3+ characters)."; return
        }
        guard !ig.isEmpty || !yt.isEmpty else {
            error = "Add your Instagram or YouTube so we can verify you."; return
        }
        busy = true; error = nil
        let ok = await app.becomeCreatorAPI(handle: handle, instagram: ig, youtube: yt)
        busy = false
        if ok, app.isCreator {
            finish()                 // → Pages tab shows the "under review" state
        } else {
            error = "That handle may be taken — try another."
        }
    }
}

#Preview {
    NavigationStack { PickRoleView(onBrowse: {}, onCreator: {}) }.environment(AppState())
}
