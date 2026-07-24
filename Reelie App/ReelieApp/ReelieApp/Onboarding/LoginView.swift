import SwiftUI
import AuthenticationServices

/// Screen 01 — Login. Real auth via Supabase (Apple / Google / email code) when
/// the backend reports `provider: "supabase"`; falls back to the local dev email
/// login otherwise. Whatever the method, the app ends up with a bearer token.
struct LoginView: View {
    @Environment(AppState.self) private var app
    var onContinue: () -> Void

    @State private var showEmail = false
    @State private var appleNonce = ""
    @State private var authError: String?
    @State private var busy = false

    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            VStack(spacing: 16) {
                Wordmark(size: 44)
                Text("Your videos, turned into shoppable pages. Automatically.")
                    .font(ReelieFont.ui(16)).foregroundStyle(Palette.grey)
                    .multilineTextAlignment(.center).frame(maxWidth: 260).lineSpacing(3)
            }
            Spacer()

            VStack(spacing: 12) {
                BigButton(title: "Continue with email", style: .sun) { showEmail = true }

                SignInWithAppleButton(.signIn) { request in
                    appleNonce = AppleNonce.make()
                    request.requestedScopes = [.fullName, .email]
                    request.nonce = AppleNonce.sha256(appleNonce)
                } onCompletion: { result in
                    handleApple(result)
                }
                .signInWithAppleButtonStyle(.black)
                .frame(height: 54)
                .clipShape(Capsule())

                BigButton(title: busy ? "…" : "Continue with Google", style: .outline,
                          icon: Image(systemName: "g.circle.fill")) {
                    Task {
                        busy = true
                        let ok = await app.signInWithGoogle()
                        busy = false
                        if ok { onContinue() } else { authError = "Google sign-in didn't complete." }
                    }
                }

                if let authError {
                    Text(authError).font(ReelieFont.ui(12.5)).foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                }
                legal.padding(.top, 2)
            }
            .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .task { await app.loadAuthConfig() }
        .sheet(isPresented: $showEmail) {
            EmailSignInSheet { showEmail = false; onContinue() }
                .presentationDetents([.height(360)])
        }
    }

    private func handleApple(_ result: Result<ASAuthorization, Error>) {
        guard case .success(let auth) = result,
              let cred = auth.credential as? ASAuthorizationAppleIDCredential,
              let data = cred.identityToken,
              let idToken = String(data: data, encoding: .utf8) else {
            authError = "Apple sign-in was cancelled."
            return
        }
        Task {
            if await app.signInWithApple(idToken: idToken, rawNonce: appleNonce) { onContinue() }
            else { authError = app.lastAuthError ?? "Apple sign-in failed. Please try again." }
        }
    }

    private var legal: some View {
        let base = AppConfig.productionAPIBaseURL.isEmpty ? "https://reelie.io"
                                                          : AppConfig.productionAPIBaseURL
        return Text(.init(
            "By continuing you agree to our [Terms](\(base)/terms) & [Privacy Policy](\(base)/privacy)."))
            .font(ReelieFont.ui(11.5)).foregroundStyle(Palette.fainter).tint(Palette.ink)
            .multilineTextAlignment(.center).lineSpacing(2)
    }
}

/// Email sign-in. With Supabase: send a 6-digit code, then verify it. With the
/// dev provider: a single-step password-less email login. Shared by the login and
/// become-creator screens.
struct EmailSignInSheet: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    var onDone: () -> Void

    private enum Stage { case email, code }
    @State private var stage: Stage = .email
    @State private var email = ""
    @State private var code = ""
    @State private var busy = false
    @State private var error: String?
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if stage == .email {
                Text("What's your email?").displayStyle(26).padding(.top, 26)
                Text("We'll email you a code to sign in.")
                    .font(ReelieFont.ui(14)).foregroundStyle(Palette.grey).lineSpacing(2).padding(.top, 6)
                field(placeholder: "you@example.com", text: $email,
                      keyboard: .emailAddress, content: .emailAddress)
            } else {
                Text("Enter your code").displayStyle(26).padding(.top, 26)
                Text("We sent a 6-digit code to \(email).")
                    .font(ReelieFont.ui(14)).foregroundStyle(Palette.grey).lineSpacing(2).padding(.top, 6)
                field(placeholder: "123456", text: $code,
                      keyboard: .numberPad, content: .oneTimeCode)
            }

            if let error {
                Text(error).font(ReelieFont.ui(12.5)).foregroundStyle(.red).padding(.top, 8)
            }
            Spacer(minLength: 0)

            BigButton(title: busy ? "…" : (stage == .email ? "Continue" : "Verify & sign in"),
                      style: .sun) { Task { await go() } }
                .opacity(canContinue && !busy ? 1 : 0.5)
                .disabled(!canContinue || busy)
                .padding(.bottom, 20)
        }
        .padding(.horizontal, 28)
        .presentationDragIndicator(.visible)
        .onAppear { focused = true }
    }

    private func field(placeholder: String, text: Binding<String>,
                       keyboard: UIKeyboardType, content: UITextContentType) -> some View {
        HStack(spacing: 9) {
            TextField(placeholder, text: text)
                .font(ReelieFont.ui(15)).foregroundStyle(Palette.ink)
                .textInputAutocapitalization(.never).autocorrectionDisabled()
                .keyboardType(keyboard).textContentType(content).focused($focused)
        }
        .padding(.horizontal, 14).padding(.vertical, 14)
        .hairlineCard(cornerRadius: 14, color: error == nil ? Palette.ink : Color.red.opacity(0.6))
        .padding(.top, 20)
    }

    private var canContinue: Bool {
        stage == .email ? (email.contains("@") && email.contains(".")) : code.count >= 6
    }

    private func go() async {
        guard canContinue, !busy else { return }
        busy = true; error = nil
        let mail = email.trimmingCharacters(in: .whitespaces).lowercased()
        if stage == .email {
            if app.usesSupabaseAuth {
                if await app.startEmailOTP(mail) { stage = .code; code = ""; focused = true }
                else { error = "Couldn't send the code. Check your email and try again." }
            } else {
                // Dev provider: single-step email login.
                if await app.signIn(email: mail) { onDone() }
                else { error = "Couldn't sign in. Check your connection." }
            }
        } else {
            if await app.verifyEmailOTP(email: mail, code: code.trimmingCharacters(in: .whitespaces)) {
                onDone()
            } else { error = "That code didn't work. Try again." }
        }
        busy = false
    }
}

#Preview {
    NavigationStack { LoginView(onContinue: {}) }.environment(AppState())
}
