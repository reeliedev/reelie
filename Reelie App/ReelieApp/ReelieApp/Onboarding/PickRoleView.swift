import SwiftUI

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

    private enum Step { case signIn, claim, connect }
    @State private var step: Step = .signIn
    @State private var email = ""
    @State private var handle = ""
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        VStack(spacing: 0) {
            HStack { BackButton { dismiss() }; Spacer() }
                .frame(height: 44).padding(.horizontal, 28)

            switch step {
            case .signIn: signInStep
            case .claim: claimStep
            case .connect: connectStep
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
                TextField("you@email.com", text: $email)
                    .font(ReelieFont.ui(16, weight: .medium)).foregroundStyle(Palette.ink)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                    .keyboardType(.emailAddress)
                    .padding(.horizontal, 16).frame(height: 58)
                    .hairlineCard(cornerRadius: 16, color: Palette.ink)
                if let error { Text(error).font(ReelieFont.ui(12.5)).foregroundStyle(.red) }
                BigButton(title: busy ? "…" : "Continue", style: .sun) { Task { await doSignIn() } }
            }
            .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
    }

    private var claimStep: some View {
        VStack(spacing: 0) {
            Spacer()
            VStack(spacing: 12) {
                Text("Claim your page").displayStyle(30)
                Text("This is the link you'll say in your videos — keep it easy to type.")
                    .font(ReelieFont.ui(15)).foregroundStyle(Palette.grey)
                    .multilineTextAlignment(.center).frame(maxWidth: 280).lineSpacing(2)
            }
            Spacer()
            VStack(spacing: 12) {
                HStack(spacing: 2) {
                    Text(app.baseURL).font(ReelieFont.ui(16, weight: .medium)).foregroundStyle(Palette.grey)
                    TextField("yourname", text: $handle)
                        .font(ReelieFont.ui(16, weight: .bold)).foregroundStyle(Palette.ink)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                }
                .padding(.horizontal, 16).frame(height: 58)
                .hairlineCard(cornerRadius: 16, color: Palette.ink)
                if let error { Text(error).font(ReelieFont.ui(12.5)).foregroundStyle(.red) }
                BigButton(title: busy ? "…" : "Claim & finish", style: .sun) { Task { await doClaim() } }
            }
            .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
    }

    private var connectStep: some View {
        VStack(spacing: 0) {
            VStack(spacing: 12) {
                Text("Connect your videos").displayStyle(30).multilineTextAlignment(.center)
                Text("Link an account and Reelie turns your videos into shoppable, AI-discoverable pages.")
                    .font(ReelieFont.ui(15)).foregroundStyle(Palette.grey)
                    .multilineTextAlignment(.center).frame(maxWidth: 300).lineSpacing(2)
            }
            .padding(.top, 20)

            Spacer()
            ConnectAccountsList()
            Spacer()

            VStack(spacing: 12) {
                BigButton(title: "Finish", style: .sun) { finish() }
                Button("I'll connect later") { finish() }
                    .font(ReelieFont.ui(14, weight: .medium)).foregroundStyle(Palette.grey)
                    .buttonStyle(.plain)
            }
            .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
    }

    private func finish() {
        app.selectedTab = .pages
        dismiss()
    }

    private func doSignIn() async {
        guard email.contains("@") else { error = "Enter a valid email"; return }
        busy = true; error = nil
        let ok = await app.signIn(email: email)
        busy = false
        if ok { handle = app.handle; step = .claim } else { error = "Couldn't sign in — is the API running?" }
    }

    private func doClaim() async {
        guard handle.trimmingCharacters(in: .whitespaces).count >= 3 else { error = "Pick a handle (3+ characters)"; return }
        busy = true; error = nil
        let ok = await app.becomeCreatorAPI(handle: handle)
        busy = false
        if ok, app.isCreator {
            step = .connect          // now let them connect YouTube / Instagram
        } else {
            error = "That handle may be taken — try another."
        }
    }
}

#Preview {
    NavigationStack { PickRoleView(onBrowse: {}, onCreator: {}) }.environment(AppState())
}
