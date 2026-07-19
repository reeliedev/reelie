import SwiftUI
import AuthenticationServices

/// Runs the OAuth consent flow in a system web-auth session and returns the
/// `reelie://…` callback URL the backend redirects to. Used to connect a
/// creator's YouTube / Instagram account.
@MainActor
final class WebAuthCoordinator: NSObject, ASWebAuthenticationPresentationContextProviding {
    private var session: ASWebAuthenticationSession?

    func run(url: URL, callbackScheme: String) async -> URL? {
        await withCheckedContinuation { cont in
            let s = ASWebAuthenticationSession(url: url, callbackURLScheme: callbackScheme) { callback, _ in
                cont.resume(returning: callback)
            }
            s.presentationContextProvider = self
            s.prefersEphemeralWebBrowserSession = false   // reuse the platform login if present
            session = s
            s.start()
        }
    }

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        let scene = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive } ?? UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first
        return scene?.keyWindow ?? ASPresentationAnchor()
    }
}

extension AppState {
    /// Refresh the list of connected platforms from the backend.
    @MainActor
    func loadConnections() async {
        guard let base = apiBaseURL, let token = authToken else { connections = []; return }
        connections = (try? await APIClient(baseURL: base).connections(token: token)) ?? []
    }

    /// Kick off the OAuth flow for a platform ("youtube" | "instagram"). Returns
    /// true once the account is connected. Works today against the backend's mock
    /// provider; real Google/Meta consent once their keys are configured server-side.
    @MainActor @discardableResult
    func connectPlatform(_ platform: String) async -> Bool {
        guard let base = apiBaseURL, let token = authToken else { return false }
        let client = APIClient(baseURL: base)
        guard let start = try? await client.startConnect(platform: platform, token: token),
              let url = URL(string: start.authorizeUrl) else { return false }
        let coordinator = WebAuthCoordinator()
        guard let callback = await coordinator.run(url: url, callbackScheme: start.callbackScheme) else {
            return false   // user cancelled
        }
        let ok = URLComponents(url: callback, resolvingAgainstBaseURL: false)?
            .queryItems?.first { $0.name == "ok" }?.value == "1"
        await loadConnections()
        return ok
    }

    @MainActor
    func disconnectPlatform(_ platform: String) async {
        guard let base = apiBaseURL, let token = authToken else { return }
        try? await APIClient(baseURL: base).disconnect(platform: platform, token: token)
        await loadConnections()
    }

    /// The connected account's videos (feeds PickVideo).
    func connectionVideos(_ platform: String) async -> [ConnectedVideo] {
        guard let base = apiBaseURL, let token = authToken else { return [] }
        return (try? await APIClient(baseURL: base).connectionVideos(platform: platform, token: token)) ?? []
    }
}
