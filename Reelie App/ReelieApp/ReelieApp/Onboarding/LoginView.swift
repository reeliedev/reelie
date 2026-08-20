import SwiftUI
import AuthenticationServices

/// Screen 01 — Login. Real auth via Supabase (Apple / Google / email code) when
/// the backend reports `provider: "supabase"`; falls back to the local dev email
/// login otherwise. Whatever the method, the app ends up with a bearer token.
struct LoginView: View {
    @Environment(AppState.self) private var app
    var onContinue: () -> Void
    /// When presented modally (e.g. "Sign in" from the profile), shows a close
    /// button. Nil during onboarding, where there's nothing to dismiss to.
    var onCancel: (() -> Void)? = nil

    @State private var showEmail = false
    @State private var appleNonce = ""
    @State private var authError: String?
    @State private var busy = false

    var body: some View {
        VStack(spacing: 0) {
            if let onCancel {
                HStack {
                    Spacer()
                    Button { onCancel() } label: {
                        Image(systemName: "xmark").font(.system(size: 15, weight: .bold))
                            .foregroundStyle(Palette.grey).padding(10)
                    }
                }
                .padding(.horizontal, 18).padding(.top, 8)
            }
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
            EmailSignInSheet(mode: .signIn) { showEmail = false; onContinue() }
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

    /// signIn = email + password (with a "forgot password → code" backup).
    /// signUp = email + code (verify) then set a password.
    enum AuthMode { case signIn, signUp }
    var mode: AuthMode = .signIn
    var onDone: () -> Void

    // email → (signUp: code → setPassword) | (signIn: password, or forgot → code → setPassword)
    private enum Stage { case email, password, code, setPassword }
    @State private var stage: Stage = .email
    @State private var email = ""
    @State private var password = ""
    @State private var code = ""
    @State private var busy = false
    @State private var error: String?
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(title).displayStyle(26).padding(.top, 26)
            Text(subtitle).font(ReelieFont.ui(14)).foregroundStyle(Palette.grey)
                .lineSpacing(2).padding(.top, 6)

            inputField

            if let error {
                Text(error).font(ReelieFont.ui(12.5)).foregroundStyle(.red).padding(.top, 8)
            }
            Spacer(minLength: 0)

            // Forgot-password backup: only on the sign-in password step.
            if mode == .signIn && stage == .password {
                Button("Forgot password? Email me a code") { Task { await sendCode() } }
                    .font(ReelieFont.ui(13, weight: .medium)).foregroundStyle(Palette.grey)
                    .buttonStyle(.plain).padding(.bottom, 10)
            }

            BigButton(title: busy ? "…" : primaryTitle, style: .sun) { Task { await go() } }
                .opacity(canContinue && !busy ? 1 : 0.5)
                .disabled(!canContinue || busy)
                .padding(.bottom, 20)
        }
        .padding(.horizontal, 28)
        .presentationDragIndicator(.visible)
        .onAppear { focused = true }
    }

    private var title: String {
        switch stage {
        case .email:       return mode == .signUp ? "What's your email?" : "Sign in"
        case .password:    return "Enter your password"
        case .code:        return "Enter your code"
        case .setPassword: return mode == .signUp ? "Set a password" : "Set a new password"
        }
    }

    private var subtitle: String {
        switch stage {
        case .email:       return mode == .signUp ? "We'll email you a code to verify it."
                                                   : "Enter your email to continue."
        case .password:    return "Signing in as \(email)."
        case .code:        return "We sent a sign-in code to \(email)."
        case .setPassword: return "You'll use this to sign in next time."
        }
    }

    private var primaryTitle: String {
        switch stage {
        case .email:       return "Continue"
        case .password:    return "Sign in"
        case .code:        return "Verify"
        case .setPassword: return "Set password & continue"
        }
    }

    @ViewBuilder private var inputField: some View {
        switch stage {
        case .email:
            field(placeholder: "you@example.com", text: $email,
                  keyboard: .emailAddress, content: .emailAddress, secure: false)
        case .password:
            field(placeholder: "Your password", text: $password,
                  keyboard: .default, content: .password, secure: true)
        case .setPassword:
            field(placeholder: "Create a password", text: $password,
                  keyboard: .default, content: .newPassword, secure: true)
        case .code:
            field(placeholder: "123456", text: $code,
                  keyboard: .numberPad, content: .oneTimeCode, secure: false)
        }
    }

    @ViewBuilder
    private func field(placeholder: String, text: Binding<String>,
                       keyboard: UIKeyboardType, content: UITextContentType,
                       secure: Bool) -> some View {
        HStack(spacing: 9) {
            Group {
                if secure { SecureField(placeholder, text: text) }
                else { TextField(placeholder, text: text) }
            }
            .font(ReelieFont.ui(15)).foregroundStyle(Palette.ink)
            .textInputAutocapitalization(.never).autocorrectionDisabled()
            .keyboardType(keyboard).textContentType(content).focused($focused)
        }
        .padding(.horizontal, 14).padding(.vertical, 14)
        .hairlineCard(cornerRadius: 14, color: error == nil ? Palette.ink : Color.red.opacity(0.6))
        .padding(.top, 20)
    }

    private var canContinue: Bool {
        switch stage {
        case .email:                  return email.contains("@") && email.contains(".")
        case .password, .setPassword: return password.count >= 6
        case .code:                   return code.count >= 4   // OTP length can vary
        }
    }

    private var mail: String { email.trimmingCharacters(in: .whitespaces).lowercased() }

    private func go() async {
        guard canContinue, !busy else { return }
        busy = true; error = nil
        switch stage {
        case .email:
            if !app.usesSupabaseAuth {                       // dev provider: passwordless
                if await app.signIn(email: mail) { onDone() }
                else { error = "Couldn't sign in. Check your connection." }
            } else if mode == .signUp {
                await sendCode()                             // verify email first
            } else {
                stage = .password; password = ""; focused = true   // collect password
            }
        case .password:
            if await app.signInWithPassword(email: mail, password: password) { onDone() }
            else { error = app.lastAuthError ?? "Wrong email or password." }
        case .code:
            if await app.verifyEmailOTP(email: mail, code: code.trimmingCharacters(in: .whitespaces)) {
                stage = .setPassword; password = ""; focused = true   // now set/reset the password
            } else { error = "That code didn't work. Try again." }
        case .setPassword:
            _ = await app.setPassword(password)              // best-effort; they're already signed in
            onDone()
        }
        busy = false
    }

    /// Send the email code (sign-up verification, or the forgot-password backup).
    private func sendCode() async {
        busy = true; error = nil
        if await app.startEmailOTP(mail) { stage = .code; code = ""; focused = true }
        else { error = "Couldn't send the code. Check your email and try again." }
        busy = false
    }
}

#Preview {
    NavigationStack { LoginView(onContinue: {}) }.environment(AppState())
}
