import SwiftUI

/// Screen 01 — Login. Email is the real MVP path (creates/fetches an account via
/// the backend `/auth/dev-login`); Apple & Google sign-in come later.
struct LoginView: View {
    @Environment(AppState.self) private var app
    var onContinue: () -> Void

    @State private var showEmail = false
    @State private var soon = false

    var body: some View {
        VStack(spacing: 0) {
            // Centered wordmark + tagline.
            Spacer()
            VStack(spacing: 16) {
                Wordmark(size: 44)
                Text("Your videos, turned into shoppable pages. Automatically.")
                    .font(ReelieFont.ui(16))
                    .foregroundStyle(Palette.grey)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 260)
                    .lineSpacing(3)
            }
            Spacer()

            // Auth buttons. Email works today; the OAuth sign-ins are staged.
            VStack(spacing: 12) {
                BigButton(title: "Continue with email", style: .sun) { showEmail = true }

                BigButton(title: "Sign in with Apple", style: .ink,
                          icon: Image(systemName: "apple.logo")) { soon = true }

                BigButton(title: "Continue with Google", style: .outline,
                          icon: Image(systemName: "g.circle.fill")) { soon = true }

                legal.padding(.top, 2)
            }
            .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .sheet(isPresented: $showEmail) {
            EmailEntrySheet { email in
                let ok = await app.signIn(email: email)
                if ok { showEmail = false; onContinue() }
                return ok
            }
            .presentationDetents([.height(320)])
        }
        .alert("Coming soon", isPresented: $soon) {
            Button("OK", role: .cancel) {}
        } message: {
            Text("Apple & Google sign-in are on the way. Use email for now.")
        }
    }

    private var legal: some View {
        // Markdown links open the public Terms/Privacy pages in Safari.
        let base = AppConfig.productionAPIBaseURL.isEmpty ? "https://reelie.io"
                                                          : AppConfig.productionAPIBaseURL
        return Text(.init(
            "By continuing you agree to our [Terms](\(base)/terms) & [Privacy Policy](\(base)/privacy)."))
            .font(ReelieFont.ui(11.5))
            .foregroundStyle(Palette.fainter)
            .tint(Palette.ink)
            .multilineTextAlignment(.center)
            .lineSpacing(2)
    }
}

/// Email entry. Calls `submit` (which signs in against the backend) and reports
/// success; on failure it shows an inline error and stays open.
private struct EmailEntrySheet: View {
    /// Returns true on a successful sign-in.
    let submit: (String) async -> Bool

    @Environment(\.dismiss) private var dismiss
    @State private var email = ""
    @State private var busy = false
    @State private var error: String?
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("What's your email?").displayStyle(26).padding(.top, 26)
            Text("We'll use it to save your pages and sign you back in.")
                .font(ReelieFont.ui(14)).foregroundStyle(Palette.grey)
                .lineSpacing(2).padding(.top, 6)

            HStack(spacing: 9) {
                Image(systemName: "envelope").font(.system(size: 14, weight: .medium))
                    .foregroundStyle(Palette.grey)
                TextField("you@example.com", text: $email)
                    .font(ReelieFont.ui(15)).foregroundStyle(Palette.ink)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                    .keyboardType(.emailAddress).textContentType(.emailAddress)
                    .focused($focused)
                    .onSubmit { Task { await go() } }
            }
            .padding(.horizontal, 14).padding(.vertical, 14)
            .hairlineCard(cornerRadius: 14, color: error == nil ? Palette.ink : Color.red.opacity(0.6))
            .padding(.top, 20)

            if let error {
                Text(error).font(ReelieFont.ui(12.5)).foregroundStyle(.red).padding(.top, 8)
            }

            Spacer(minLength: 0)

            BigButton(title: busy ? "Signing in…" : "Continue", style: .sun) {
                Task { await go() }
            }
            .opacity(isValid && !busy ? 1 : 0.5)
            .disabled(!isValid || busy)
            .padding(.bottom, 20)
        }
        .padding(.horizontal, 28)
        .presentationDragIndicator(.visible)
        .onAppear { focused = true }
    }

    private var isValid: Bool {
        let e = email.trimmingCharacters(in: .whitespaces)
        return e.contains("@") && e.contains(".")
    }

    private func go() async {
        guard isValid, !busy else { return }
        busy = true; error = nil
        let ok = await submit(email.trimmingCharacters(in: .whitespaces).lowercased())
        busy = false
        if !ok { error = "Couldn't sign in. Check your connection and try again." }
    }
}

#Preview {
    NavigationStack { LoginView(onContinue: {}) }.environment(AppState())
}
