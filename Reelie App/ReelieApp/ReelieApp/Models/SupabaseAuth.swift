import Foundation
import CryptoKit
import AuthenticationServices

/// Native Supabase (GoTrue) auth — no SDK dependency. Talks to the project's
/// `/auth/v1` REST endpoints with the public anon key and returns a Supabase
/// access token, which the app then uses as the `Bearer` for the Reelie API
/// (the backend verifies it via Supabase's JWKS). Three methods: email OTP,
/// Sign in with Apple (native id_token), and Google (web OAuth).
struct SupabaseAuth {
    let url: URL           // https://<project>.supabase.co
    let anonKey: String

    private func request(_ path: String, body: [String: Any]) -> URLRequest {
        var req = URLRequest(url: url.appendingPathComponent(path))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue(anonKey, forHTTPHeaderField: "apikey")
        req.setValue("Bearer \(anonKey)", forHTTPHeaderField: "Authorization")
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        return req
    }

    /// A Supabase session — the short-lived access token plus the refresh token
    /// used to renew it (so the user stays signed in past the ~1h expiry).
    struct Session: Decodable { let access_token: String; let refresh_token: String? }

    private func send(_ req: URLRequest) async throws -> Session {
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw AuthError.server(String(data: data, encoding: .utf8) ?? "Sign-in failed.")
        }
        return try JSONDecoder().decode(Session.self, from: data)
    }

    /// Exchange a refresh token for a fresh session.
    func refresh(refreshToken: String) async throws -> Session {
        try await send(request("auth/v1/token?grant_type=refresh_token",
                               body: ["refresh_token": refreshToken]))
    }

    enum AuthError: LocalizedError {
        case server(String), cancelled
        var errorDescription: String? {
            switch self { case .server(let m): return m; case .cancelled: return "Cancelled." }
        }
    }

    // MARK: Email magic-link / OTP

    /// Send a 6-digit code (and magic link) to the email.
    func sendEmailOTP(_ email: String) async throws {
        let (data, resp) = try await URLSession.shared.data(
            for: request("auth/v1/otp", body: ["email": email, "create_user": true]))
        guard let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw AuthError.server(String(data: data, encoding: .utf8) ?? "Couldn't send the code.")
        }
    }

    /// Verify the emailed code → Supabase session.
    func verifyEmailOTP(email: String, code: String) async throws -> Session {
        try await send(request("auth/v1/verify",
                               body: ["type": "email", "email": email, "token": code]))
    }

    // MARK: Sign in with Apple (native)

    /// Exchange Apple's identity token for a Supabase session.
    func signInWithApple(idToken: String, rawNonce: String) async throws -> Session {
        try await send(request("auth/v1/token?grant_type=id_token",
                               body: ["provider": "apple", "id_token": idToken, "nonce": rawNonce]))
    }

    // MARK: Google (web OAuth via ASWebAuthenticationSession)

    /// The hosted consent URL that redirects back to the app scheme with tokens.
    func googleAuthorizeURL(redirect: String) -> URL {
        var c = URLComponents(url: url.appendingPathComponent("auth/v1/authorize"),
                              resolvingAgainstBaseURL: false)!
        c.queryItems = [.init(name: "provider", value: "google"),
                        .init(name: "redirect_to", value: redirect)]
        return c.url!
    }

    /// Pull the session out of the `reelie://auth-callback#access_token=…&refresh_token=…` redirect.
    static func session(fromCallback callback: URL) -> Session? {
        guard let frag = URLComponents(url: callback, resolvingAgainstBaseURL: false)?.fragment else { return nil }
        var params: [String: String] = [:]
        for pair in frag.split(separator: "&") {
            let kv = pair.split(separator: "=", maxSplits: 1)
            if kv.count == 2 { params[String(kv[0])] = kv[1].removingPercentEncoding }
        }
        guard let access = params["access_token"] else { return nil }
        return Session(access_token: access, refresh_token: params["refresh_token"])
    }
}

// MARK: - Apple nonce helpers

enum AppleNonce {
    /// A random nonce; its SHA256 goes to Apple, the raw value to Supabase.
    static func make(length: Int = 32) -> String {
        let chars = Array("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-._")
        var result = ""
        var remaining = length
        while remaining > 0 {
            var random: UInt8 = 0
            _ = SecRandomCopyBytes(kSecRandomDefault, 1, &random)
            if Int(random) < chars.count { result.append(chars[Int(random)]); remaining -= 1 }
        }
        return result
    }
    static func sha256(_ input: String) -> String {
        SHA256.hash(data: Data(input.utf8)).map { String(format: "%02x", $0) }.joined()
    }
}
