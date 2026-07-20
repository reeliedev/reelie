import SwiftUI

// App configuration. Set `productionAPIBaseURL` to the deployed HTTPS API once it's
// live (e.g. "https://api.reelie.shop"). Until then it's empty and release builds
// run on mock data. In any build, the REELIE_API_URL env var overrides this (used
// for local dev + TestFlight pointing at staging).
enum AppConfig {
    // The deployed API + public site (one service). Release builds talk to this;
    // REELIE_API_URL env overrides it for local dev / staging.
    static let productionAPIBaseURL = "https://reelie.shop"
}

// Thin client for the Reelie backend. Used when a base URL is configured
// (env override or the production URL above); otherwise the app runs on seeded
// mock data. Loads the catalogue so Discover/creators/routines come from the API.

extension Color {
    init(hexString: String) {
        let s = hexString.trimmingCharacters(in: CharacterSet(charactersIn: "# "))
        var v: UInt64 = 0
        Scanner(string: s).scanHexInt64(&v)
        self.init(hex: UInt(v))
    }
}

private struct CreatorDTO: Decodable {
    let handle: String
    let displayName: String
    let avatarGradient: [String]
    let platforms: [String]
    func toCreator() -> Creator {
        Creator(displayName: displayName, handle: handle,
                avatarGradient: avatarGradient.map { Color(hexString: $0) },
                platforms: platforms)
    }
}

// Live earnings for a creator (Phase 3) — replaces the hardcoded dashboard values.
struct EarningsSummary: Decodable {
    let lifetime: Double
    let thisWeek: Double
    let thisMonth: Double
    let pending: Double
    let ready: Double
    let readyToPayout: Double
    let paidSoFar: Double
    let clicks: Int
    let conversions: Int
    let byPage: [PageEarning]
    let recentSales: [APISale]

    struct PageEarning: Decodable { let slug: String; let title: String; let total: Double }
    struct APISale: Decodable { let name: String; let emoji: String; let page: String; let value: Double; let state: String }
}

// Account payloads (mirror the backend /auth + /me responses).
struct UserDTO: Decodable {
    let id: String
    let email: String
    let displayName: String
    let handle: String?
    let avatarGradient: [String]
    let role: String
    func toUser() -> User {
        User(email: email, displayName: displayName, handle: handle ?? "",
             avatarGradient: avatarGradient.map { Color(hexString: $0) },
             role: Role.from(role))
    }
}
struct AuthResult: Decodable { let token: String; let user: UserDTO }

struct APIClient {
    let baseURL: URL

    func get<T: Decodable>(_ path: String, as type: T.Type, token: String? = nil) async throws -> T {
        var req = URLRequest(url: baseURL.appendingPathComponent(path))
        if let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        let (data, _) = try await URLSession.shared.data(for: req)
        return try JSONDecoder().decode(T.self, from: data)
    }

    func post<T: Decodable>(_ path: String, body: [String: Any], as type: T.Type,
                            token: String? = nil) async throws -> T {
        var req = URLRequest(url: baseURL.appendingPathComponent(path))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, _) = try await URLSession.shared.data(for: req)
        return try JSONDecoder().decode(T.self, from: data)
    }

    // --- auth ---
    func devLogin(email: String) async throws -> AuthResult {
        try await post("auth/dev-login", body: ["email": email], as: AuthResult.self)
    }
    func me(token: String) async throws -> UserDTO {
        try await get("me", as: UserDTO.self, token: token)
    }
    func becomeCreator(handle: String, displayName: String, platforms: [String],
                       token: String) async throws -> UserDTO {
        try await post("me/become-creator",
                       body: ["handle": handle, "displayName": displayName, "platforms": platforms],
                       as: UserDTO.self, token: token)
    }

    func creators() async throws -> [Creator] {
        try await get("creators", as: [CreatorDTO].self).map { $0.toCreator() }
    }

    func routines() async throws -> [GeneratedPage] {
        try await get("routines", as: [GeneratedPageDTO].self).map { $0.toGeneratedPage() }
    }

    func myRoutines(handle: String) async throws -> [GeneratedPage] {
        try await get("creators/\(handle)/routines", as: [GeneratedPageDTO].self).map { $0.toGeneratedPage() }
    }

    func earnings(handle: String) async throws -> EarningsSummary {
        try await get("creators/\(handle)/earnings", as: EarningsSummary.self)
    }

    // --- self-serve generation ---
    func availableVideos(token: String) async throws -> [AvailableVideo] {
        try await get("me/videos", as: [AvailableVideo].self, token: token)
    }
    func startGeneration(videoId: String?, url: String?, token: String) async throws -> String {
        var body: [String: Any] = [:]
        if let url { body["url"] = url }
        if let videoId { body["videoId"] = videoId }
        return try await post("me/generate", body: body, as: StartGen.self, token: token).jobId
    }
    func generationStatus(jobId: String, token: String) async throws -> GenStatus {
        try await get("me/generate/\(jobId)", as: GenStatus.self, token: token)
    }

    // --- social connections (OAuth: YouTube / Instagram) ---
    func startConnect(platform: String, token: String) async throws -> ConnectStart {
        try await get("me/connect/\(platform)", as: ConnectStart.self, token: token)
    }
    func connections(token: String) async throws -> [ConnectionDTO] {
        try await get("me/connections", as: [ConnectionDTO].self, token: token)
    }
    func disconnect(platform: String, token: String) async throws {
        _ = try await send("DELETE", "me/connections/\(platform)", body: nil, as: Ack.self, token: token)
    }
    func connectionVideos(platform: String, token: String) async throws -> [ConnectedVideo] {
        try await get("me/connections/\(platform)/videos", as: [ConnectedVideo].self, token: token)
    }

    // --- creator page management ---
    func myPages(token: String) async throws -> [GeneratedPage] {
        try await get("me/pages", as: [GeneratedPageDTO].self, token: token).map { $0.toGeneratedPage() }
    }
    func editPage(slug: String, fields: [String: Any], token: String) async throws -> GeneratedPage {
        try await send("PATCH", "me/pages/\(slug)", body: fields, as: GeneratedPageDTO.self, token: token).toGeneratedPage()
    }
    func setArchived(slug: String, archived: Bool, token: String) async throws {
        _ = try await send("POST", "me/pages/\(slug)/\(archived ? "archive" : "unarchive")", body: [:], as: Ack.self, token: token)
    }
    func deletePage(slug: String, token: String) async throws {
        _ = try await send("DELETE", "me/pages/\(slug)", body: nil, as: Ack.self, token: token)
    }

    // --- payouts ---
    func payouts(token: String) async throws -> PayoutsSummary {
        try await get("me/payouts", as: PayoutsSummary.self, token: token)
    }
    func connectPayouts(token: String) async throws -> String {
        try await send("POST", "me/payouts/connect", body: [:], as: ConnectResp.self, token: token).url
    }
    func withdraw(token: String) async throws {
        _ = try await send("POST", "me/payouts/withdraw", body: [:], as: Ack.self, token: token)
    }

    // --- account ---
    func deleteAccount(token: String) async throws {
        _ = try await send("DELETE", "me", body: nil, as: Ack.self, token: token)
    }

    /// Generic mutation with an optional JSON body.
    private func send<T: Decodable>(_ method: String, _ path: String, body: [String: Any]?,
                                    as type: T.Type, token: String?) async throws -> T {
        var req = URLRequest(url: baseURL.appendingPathComponent(path))
        req.httpMethod = method
        if let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (data, _) = try await URLSession.shared.data(for: req)
        return try JSONDecoder().decode(T.self, from: data)
    }
}

struct Ack: Decodable { let ok: Bool }
private struct ConnectResp: Decodable { let url: String }

struct PayoutsSummary: Decodable {
    let connected: Bool
    let ready: Double
    let pending: Double
    let paidSoFar: Double
    let history: [PayoutItem]
    struct PayoutItem: Decodable, Identifiable { let id: String; let amount: Double; let status: String; let date: String }
}

struct AvailableVideo: Decodable, Identifiable {
    let videoId: String
    let title: String
    let numProducts: Int
    var id: String { videoId }
}
private struct StartGen: Decodable { let jobId: String }
struct GenStatus: Decodable { let status: String; let stage: String; let pageSlug: String?; let error: String? }

// Social-connection payloads.
struct ConnectStart: Decodable { let authorizeUrl: String; let mock: Bool; let callbackScheme: String }
struct ConnectionDTO: Decodable, Identifiable {
    let platform: String; let username: String; let connectedAt: String; let mock: Bool
    var id: String { platform }
}
struct ConnectedVideo: Decodable, Identifiable {
    let id: String; let title: String; let url: String; let thumb: String; let published: String
}
