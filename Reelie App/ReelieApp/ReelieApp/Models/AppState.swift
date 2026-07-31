import SwiftUI
import Observation
#if canImport(UIKit)
import UIKit
#endif

enum MainTab: Hashable {
    // Consumer surface (always available)
    case discover, saved, profile
    // Creator studio (shown only when the account has creator role)
    case pages, earnings
}

/// Result of a self-serve generation from the app's point of view.
enum GenerationOutcome {
    case done(slug: String)
    case failed(reason: String?)   // reason is the backend's creator-facing message
    case building                  // backend still working past our watch window → lands in Drafts
}

@Observable
final class AppState {

    // Onboarding gate. Flip to `true` to jump straight into the app.
    var onboardingComplete = false

    // The signed-in account. Viewer by default; "become a creator" unlocks the
    // studio on the same identity.
    var currentUser = User(
        displayName: "Jess Tan", handle: "glowbyjess",
        avatarGradient: [Color(hex: 0xE8E4DA), Color(hex: 0xD8D2C4)],
        role: .viewer
    )
    var isCreator: Bool { currentUser.role.isCreator }

    // Last-known role/creator-status, persisted so the tab bar shows the right
    // tabs from the first frame (no 3→5 flicker) and the Pages tab loads on the
    // first open — instead of waiting for /me to come back before we know the
    // account is a creator.
    private static let roleKey = "reelie.role"
    private static let creatorStatusKey = "reelie.creatorStatus"

    init() {
        // A stored token means the account signed in — and in this app ONLY
        // creators sign in (consumers browse as guests). So a token implies at
        // least creator role: show the 5 creator tabs from the first frame instead
        // of flipping 3→5 once /me returns. The cached role refines viewer/both;
        // restoreSession() then confirms against the server.
        if authToken != nil {
            if let r = UserDefaults.standard.string(forKey: Self.roleKey) {
                currentUser.role = Role.from(r)
            } else {
                currentUser.role = .both
            }
            currentUser.creatorStatus = UserDefaults.standard.string(forKey: Self.creatorStatusKey)
        }
    }

    private func cacheRole() {
        UserDefaults.standard.set(currentUser.role.raw, forKey: Self.roleKey)
        UserDefaults.standard.setValue(currentUser.creatorStatus, forKey: Self.creatorStatusKey)
    }

    // Legacy convenience (creator studio still reads/writes these).
    var displayName: String {
        get { currentUser.displayName }
        set { currentUser.displayName = newValue }
    }
    var handle: String {
        get { currentUser.handle }
        set { currentUser.handle = newValue }
    }
    var baseURL = "reelie.com/"

    // Which main tab is showing. Consumers land on Discover.
    var selectedTab: MainTab = .discover

    // Connected social accounts (YouTube / Instagram), from the backend.
    var connections: [ConnectionDTO] = []
    func isConnected(_ platform: String) -> Bool { connections.contains { $0.platform == platform } }
    func connection(_ platform: String) -> ConnectionDTO? { connections.first { $0.platform == platform } }

    // Navigation path for the Pages tab, so screens can pop to root.
    var homePath: [AppRoute] = []
    // Navigation path for the consumer tabs (Discover / Saved).
    var consumerPath: [ConsumerRoute] = []

    // ---- Consumer corpus & favorites -------------------------------------
    var creators: [Creator] = Catalog.creators
    var catalog: [GeneratedPage] = Catalog.routines
    var favorites: Set<String> = FavoritesStore.loadPages()        // page keys "handle/slug"
    var favoriteCreators: Set<String> = FavoritesStore.loadCreators()  // handles

    func isFavorite(_ page: GeneratedPage) -> Bool { favorites.contains(page.key) }
    func toggleFavorite(_ page: GeneratedPage) {
        let adding = !favorites.contains(page.key)
        if adding { favorites.insert(page.key) } else { favorites.remove(page.key) }
        FavoritesStore.savePages(favorites)
        syncFavorite(kind: "page", ref: page.key, adding: adding)
    }

    /// Save/unsave a routine by its key ("handle/slug") — used by the reels feed
    /// heart, where we only have the key. Pulls the routine into the catalog so it
    /// actually shows up in the Saved tab (feed routines often aren't loaded yet).
    func isSaved(key: String) -> Bool { favorites.contains(key) }
    @MainActor
    func setSaved(key: String, _ saved: Bool) {
        if saved { favorites.insert(key) } else { favorites.remove(key) }
        FavoritesStore.savePages(favorites)
        syncFavorite(kind: "page", ref: key, adding: saved)
        if saved, page(withKey: key) == nil {
            Task { _ = await fetchRoutine(key: key) }
        }
    }

    /// Make sure every saved routine is loaded into the catalog so the Saved tab can
    /// render it — routines saved from the feed may not be in the loaded catalog.
    @MainActor
    func loadSavedRoutines() async {
        for key in favorites where page(withKey: key) == nil {
            _ = await fetchRoutine(key: key)
        }
    }
    // ---- UGC safety: block a creator (device-local) + report content ---------
    var blockedCreators: Set<String> = FavoritesStore.loadBlocked()

    func isBlocked(creator handle: String) -> Bool { blockedCreators.contains(handle) }
    func blockCreator(_ handle: String) {
        blockedCreators.insert(handle)
        FavoritesStore.saveBlocked(blockedCreators)
    }
    func unblockCreator(_ handle: String) {
        blockedCreators.remove(handle)
        FavoritesStore.saveBlocked(blockedCreators)
    }

    /// Flag a routine ("page") or a creator to the team. Best-effort; guest-ok.
    @MainActor
    func report(kind: String, ref: String, reason: String, detail: String = "") async {
        guard let base = apiBaseURL else { return }
        try? await APIClient(baseURL: base).report(
            kind: kind, ref: ref, reason: reason, detail: detail,
            clientId: LikeStore.clientId, token: authToken)
    }

    func isFavorite(creator handle: String) -> Bool { favoriteCreators.contains(handle) }
    func toggleFavorite(creator handle: String) {
        let adding = !favoriteCreators.contains(handle)
        if adding { favoriteCreators.insert(handle) } else { favoriteCreators.remove(handle) }
        FavoritesStore.saveCreators(favoriteCreators)
        syncFavorite(kind: "creator", ref: handle, adding: adding)
    }

    /// Mirror a save to the account when signed in (guests stay device-local).
    private func syncFavorite(kind: String, ref: String, adding: Bool) {
        guard let base = apiBaseURL, let token = authToken else { return }
        Task {
            do {
                let c = APIClient(baseURL: base)
                if adding { try await c.addFavorite(kind: kind, ref: ref, token: token) }
                else { try await c.removeFavorite(kind: kind, ref: ref, token: token) }
            } catch { print("[Reelie] syncFavorite: \(error)") }
        }
    }

    /// Merge the account's saved pages/creators into the local sets on sign-in/refresh.
    @MainActor
    func loadFavorites() async {
        guard let base = apiBaseURL, let token = authToken else { return }
        do {
            let f = try await APIClient(baseURL: base).favorites(token: token)
            favorites.formUnion(f.pageKeys)
            favoriteCreators.formUnion(f.creatorHandles)
            FavoritesStore.savePages(favorites)
            FavoritesStore.saveCreators(favoriteCreators)
        } catch { print("[Reelie] loadFavorites: \(error)") }
    }

    // Creator application state (from /me). Absent (nil) in dev/offline → treated
    // as approved so local testing isn't blocked.
    var isPendingCreator: Bool { isCreator && currentUser.creatorStatus == "pending" }
    var creatorApproved: Bool { currentUser.creatorStatus == nil || currentUser.creatorStatus == "approved" }

    var favoritePages: [GeneratedPage] { catalog.filter { favorites.contains($0.key) } }
    var favoriteCreatorList: [Creator] { creators.filter { favoriteCreators.contains($0.handle) } }

    func creator(_ handle: String) -> Creator? { creators.first { $0.handle == handle } }
    func routines(for handle: String) -> [GeneratedPage] { catalog.filter { $0.handle == handle } }
    func page(withKey key: String) -> GeneratedPage? { catalog.first { $0.key == key } }

    /// Resolve a routine by key ("handle/slug"): return the local one if loaded,
    /// otherwise fetch it from the API (reels come from /feed, which can include
    /// routines not in the loaded /routines catalog) and cache it.
    @MainActor
    func fetchRoutine(key: String) async -> GeneratedPage? {
        if let p = page(withKey: key) { return p }
        guard let base = apiBaseURL else { return nil }
        let parts = key.split(separator: "/", maxSplits: 1).map(String.init)
        guard parts.count == 2 else { return nil }
        do {
            let p = try await APIClient(baseURL: base).routine(handle: parts[0], slug: parts[1])
            if !catalog.contains(where: { $0.key == p.key }) { catalog.append(p) }
            return p
        } catch { print("[Reelie] fetchRoutine: \(error)"); return nil }
    }

    /// Search published routines + creators via the backend.
    @MainActor
    func search(_ query: String) async -> (creators: [Creator], routines: [GeneratedPage]) {
        guard let base = apiBaseURL else { return ([], []) }
        do { return try await APIClient(baseURL: base).search(query: query) }
        catch { print("[Reelie] search: \(error)"); return ([], []) }
    }

    // ---- Backend (optional) ----------------------------------------------
    // When REELIE_API_URL is set, load creators/routines from the API; otherwise
    // the seeded mock corpus is used. Failures fall back silently to the mock.
    var apiBaseURL: URL? {
        if let s = ProcessInfo.processInfo.environment["REELIE_API_URL"], let u = URL(string: s) {
            return u   // dev / TestFlight override
        }
        return AppConfig.productionAPIBaseURL.isEmpty ? nil : URL(string: AppConfig.productionAPIBaseURL)
    }
    var backendConnected = false

    @MainActor
    func refreshFromAPI() async {
        guard let base = apiBaseURL else {
            print("[Reelie] refreshFromAPI: no REELIE_API_URL set — using mock corpus")
            return
        }
        print("[Reelie] refreshFromAPI: loading from \(base)")
        let client = APIClient(baseURL: base)
        do {
            async let cs = client.creators()
            async let rs = client.routines()
            let (creators, routines) = try await (cs, rs)
            if !creators.isEmpty { self.creators = creators }
            if !routines.isEmpty { self.catalog = routines }
            backendConnected = true
            print("[Reelie] refreshFromAPI: OK — \(creators.count) creators, \(routines.count) routines")
            if authToken != nil { await loadFavorites() }
            if isCreator { await loadMyPages() }
        } catch {
            backendConnected = false   // keep the mock corpus
            print("[Reelie] refreshFromAPI: FAILED — \(error)")
        }
    }

    // The creator's own published pages, loaded from the API. When set, the studio
    // shows these instead of the mock sample pages.
    // True once the first /me/pages fetch has returned, so the Pages tab can show a
    // loader instead of an empty flash before the real pages arrive.
    var pagesLoaded = false
    // Set when the /me/pages fetch fails, so the tab shows a retry state instead of a
    // misleading "no pages yet" empty (or, previously, a fallback to bundled mock pages).
    var pagesLoadError = false

    /// A real, signed-in creator whose data comes from the backend (not mock data).
    var isBackedCreator: Bool { apiBaseURL != nil && isCreator && authToken != nil }
    var usesAPIPages: Bool { isBackedCreator }
    // True once the first earnings fetch has returned, so the Earnings tab can show
    // a loader instead of briefly flashing mock sample earnings.
    var earningsLoaded = false

    @MainActor
    func loadMyPages() async {
        guard let base = apiBaseURL, isCreator, let token = authToken else {
            pagesLoaded = true; return
        }
        pagesLoadError = false
        do {
            generatedPages = try await APIClient(baseURL: base).myPages(token: token)
        } catch {
            print("[Reelie] loadMyPages: \(error)")
            pagesLoadError = true
        }
        pagesLoaded = true
    }

    /// Load the creator-authored FAQs for a page so the editor can edit them.
    @MainActor
    func loadCustomFaqs(slug: String) async -> [(q: String, a: String)] {
        guard let base = apiBaseURL, let token = authToken else { return [] }
        do { return try await APIClient(baseURL: base).customFaqs(slug: slug, token: token).map { ($0.q, $0.a) } }
        catch { print("[Reelie] loadCustomFaqs: \(error)"); return [] }
    }

    /// Save edits. `customFaqs` (when non-nil) REPLACES the page's custom-FAQ list;
    /// pass nil to leave FAQs untouched (the editor only sends them once loaded).
    @MainActor
    func savePageEdits(_ page: GeneratedPage, customFaqs: [[String: String]]? = nil,
                       removedProductIds: [String] = []) async {
        guard let base = apiBaseURL, let token = authToken else {
            OverridesStore.save(page); return
        }
        var fields: [String: Any] = ["title": page.title, "intro": page.intro, "disclosure": page.disclosure]
        // Existing products carry their id (update); new ones omit it (backend adds
        // them); removed ones are sent as {id, remove:true}.
        var products: [[String: Any]] = page.products.map { p -> [String: Any] in
            var d: [String: Any] = ["brand": p.brand, "name": p.name]
            if let sid = p.serverId { d["id"] = sid }
            if let n = p.note { d["note"] = n }
            if let g = p.guide { d["guide"] = g }
            return d
        }
        for id in removedProductIds { products.append(["id": id, "remove": true]) }
        if !products.isEmpty { fields["products"] = products }
        if let customFaqs { fields["customFaqs"] = customFaqs }
        do {
            _ = try await APIClient(baseURL: base).editPage(slug: page.slug, fields: fields, token: token)
            await loadMyPages()
        } catch { print("[Reelie] savePageEdits: \(error)") }
    }

    @MainActor
    func setArchived(_ page: GeneratedPage, archived: Bool) async {
        guard let base = apiBaseURL, let token = authToken else { return }
        do { try await APIClient(baseURL: base).setArchived(slug: page.slug, archived: archived, token: token); await loadMyPages() }
        catch { print("[Reelie] setArchived: \(error)") }
    }

    @MainActor
    func deletePageAPI(_ page: GeneratedPage) async {
        guard let base = apiBaseURL, let token = authToken else { return }
        do { try await APIClient(baseURL: base).deletePage(slug: page.slug, token: token); await loadMyPages() }
        catch { print("[Reelie] deletePage: \(error)") }
    }

    /// Publish (go live) or unpublish (back to draft) a generated page.
    @MainActor @discardableResult
    func setPublished(_ page: GeneratedPage, published: Bool) async -> Bool {
        guard let base = apiBaseURL, let token = authToken else { return false }
        do {
            try await APIClient(baseURL: base).setPublished(slug: page.slug, published: published, token: token)
            await loadMyPages()
            return true
        } catch { print("[Reelie] setPublished: \(error)"); return false }
    }

    // ---- Payouts ----------------------------------------------------------
    var payoutsSummary: PayoutsSummary?

    @MainActor
    func loadPayouts() async {
        guard let base = apiBaseURL, isCreator, let token = authToken else { return }
        do { payoutsSummary = try await APIClient(baseURL: base).payouts(token: token) }
        catch { print("[Reelie] loadPayouts: \(error)") }
    }

    @MainActor @discardableResult
    func cashOut() async -> Bool {
        guard let base = apiBaseURL, let token = authToken else { return false }
        do {
            try await APIClient(baseURL: base).withdraw(token: token)
            await loadPayouts(); await loadEarnings()
            return true
        } catch { print("[Reelie] cashOut: \(error)"); return false }
    }

    // ---- Account deletion -------------------------------------------------
    @MainActor
    func deleteAccount() async {
        if let base = apiBaseURL, let token = authToken {
            try? await APIClient(baseURL: base).deleteAccount(token: token)
        }
        signOut()
    }

    // Live earnings (Phase 3). Loaded when the account is a creator and the
    // backend is reachable; otherwise the dashboard uses local mock rollups.
    var earningsSummary: EarningsSummary?

    @MainActor
    func loadEarnings() async {
        guard let base = apiBaseURL, isCreator, let token = authToken else { earningsLoaded = true; return }
        do {
            earningsSummary = try await APIClient(baseURL: base).earnings(handle: handle, token: token)
            backendConnected = true
        } catch {
            print("[Reelie] loadEarnings: FAILED — \(error)")
        }
        earningsLoaded = true
    }

    // Page analytics: human views + AI answer-engine crawls (GEO/AEO) + funnel.
    var creatorStats: PageStats?

    @MainActor
    func loadStats() async {
        guard let base = apiBaseURL, isCreator, let token = authToken else { return }
        do { creatorStats = try await APIClient(baseURL: base).myStats(token: token) }
        catch { print("[Reelie] loadStats: \(error)") }
    }

    /// Per-page funnel + AI-engine breakdown (loaded on demand from a page screen).
    @MainActor
    func pageStats(slug: String) async -> PageStats? {
        guard let base = apiBaseURL, let token = authToken else { return nil }
        return try? await APIClient(baseURL: base).pageStats(slug: slug, token: token)
    }

    // ---- Creator auth ----------------------------------------------------
    // Consumers stay guests (no login). Auth only happens on the creator path.
    // Degrades gracefully offline (no API) so the app still works on mock data.
    private static let tokenKey = "reelie.authToken"
    private static let refreshKey = "reelie.refreshToken"
    // Stored in the Keychain (encrypted), not UserDefaults. One-time migration of
    // any token previously written to UserDefaults.
    var authToken: String? = (KeychainStore.get(account: AppState.tokenKey)
        ?? UserDefaults.standard.string(forKey: AppState.tokenKey)) {
        didSet {
            KeychainStore.set(authToken, account: AppState.tokenKey)
            UserDefaults.standard.removeObject(forKey: AppState.tokenKey)   // clear legacy
        }
    }
    // Supabase refresh token — renews the short-lived access token so sign-in persists.
    var refreshToken: String? = KeychainStore.get(account: AppState.refreshKey) {
        didSet { KeychainStore.set(refreshToken, account: AppState.refreshKey) }
    }

    private func applyUser(_ u: User) {
        currentUser.email = u.email
        if !u.displayName.isEmpty { currentUser.displayName = u.displayName }
        if !u.handle.isEmpty { currentUser.handle = u.handle }
        if !u.avatarGradient.isEmpty { currentUser.avatarGradient = u.avatarGradient }
        currentUser.role = u.role
        currentUser.creatorStatus = u.creatorStatus
        cacheRole()
    }

    @MainActor
    func restoreSession() async {
        guard let base = apiBaseURL, let token = authToken else { return }
        if authConfig == nil { await loadAuthConfig() }   // needed for refresh below
        do { applyUser(try await APIClient(baseURL: base).me(token: token).toUser()) }
        catch {
            // Access token likely expired — try a Supabase refresh before giving up.
            if await refreshSupabaseSession() { return }
            authToken = nil; refreshToken = nil   // truly invalid → back to guest
        }
    }

    /// Renew an expired Supabase access token using the stored refresh token.
    @MainActor @discardableResult
    func refreshSupabaseSession() async -> Bool {
        guard let sb = supabase(), let rt = refreshToken else { return false }
        do {
            let session = try await sb.refresh(refreshToken: rt)
            return await adoptSupabaseSession(session)
        } catch { print("[Reelie] refreshSupabaseSession: \(error)"); return false }
    }

    @MainActor @discardableResult
    func signIn(email: String) async -> Bool {
        currentUser.email = email
        guard let base = apiBaseURL else { return true }   // offline: local session
        do {
            let r = try await APIClient(baseURL: base).devLogin(email: email)
            authToken = r.token
            applyUser(r.user.toUser())
            return true
        } catch { print("[Reelie] signIn: FAILED — \(error)"); return false }
    }

    // ---- Real auth (Supabase: Apple / Google / email OTP) -------------------
    // The backend tells us which provider to use via /auth/config. When it's
    // "supabase" the app authenticates directly with Supabase and uses the
    // returned access token as the Reelie API Bearer (backend verifies via JWKS).
    var authConfig: AuthConfigDTO?
    var usesSupabaseAuth: Bool { authConfig?.provider == "supabase" }
    var lastAuthError: String?   // surfaced in the UI so sign-in failures are debuggable

    @MainActor
    func loadAuthConfig() async {
        guard let base = apiBaseURL else { return }
        authConfig = try? await APIClient(baseURL: base).authConfig()
    }

    private func supabase() -> SupabaseAuth? {
        guard let c = authConfig, c.provider == "supabase",
              let u = c.supabaseUrl.flatMap(URL.init(string:)), let key = c.supabaseAnonKey
        else { return nil }
        return SupabaseAuth(url: u, anonKey: key)
    }

    /// Adopt a Supabase session (access + refresh) and load /me (the backend
    /// provisions/links the account by verifying the token).
    @MainActor @discardableResult
    func adoptSupabaseSession(_ session: SupabaseAuth.Session) async -> Bool {
        guard let base = apiBaseURL else { return false }
        authToken = session.access_token
        if let rt = session.refresh_token { refreshToken = rt }
        do { applyUser(try await APIClient(baseURL: base).me(token: session.access_token).toUser()); return true }
        catch {
            authToken = nil
            lastAuthError = "Signed in, but we couldn't load your account. Please try again."
            print("[Reelie] adoptSupabaseSession: \(error)"); return false
        }
    }

    @MainActor @discardableResult
    func startEmailOTP(_ email: String) async -> Bool {
        currentUser.email = email
        guard let sb = supabase() else { return await signIn(email: email) }  // dev fallback
        do { try await sb.sendEmailOTP(email); return true }
        catch { print("[Reelie] sendEmailOTP: \(error)"); return false }
    }

    @MainActor @discardableResult
    func verifyEmailOTP(email: String, code: String) async -> Bool {
        guard let sb = supabase() else { return false }
        do { return await adoptSupabaseSession(try await sb.verifyEmailOTP(email: email, code: code)) }
        catch { print("[Reelie] verifyEmailOTP: \(error)"); return false }
    }

    @MainActor @discardableResult
    func signInWithApple(idToken: String, rawNonce: String) async -> Bool {
        guard let sb = supabase() else { lastAuthError = "Auth isn't configured (no Supabase)."; return false }
        do { return await adoptSupabaseSession(try await sb.signInWithApple(idToken: idToken, rawNonce: rawNonce)) }
        catch {
            lastAuthError = (error as? SupabaseAuth.AuthError)?.errorDescription ?? error.localizedDescription
            print("[Reelie] signInWithApple: \(error)"); return false
        }
    }

    @MainActor @discardableResult
    func signInWithGoogle() async -> Bool {
        guard let sb = supabase() else { return false }
        let coordinator = WebAuthCoordinator()
        guard let cb = await coordinator.run(url: sb.googleAuthorizeURL(redirect: "reelie://auth-callback"),
                                             callbackScheme: "reelie"),
              let session = SupabaseAuth.session(fromCallback: cb) else { return false }
        return await adoptSupabaseSession(session)
    }

    @MainActor @discardableResult
    func becomeCreatorAPI(handle: String, instagram: String = "", youtube: String = "") async -> Bool {
        let h = handle.trimmingCharacters(in: .whitespaces).lowercased()
        currentUser.handle = h
        guard let base = apiBaseURL, let token = authToken else {
            currentUser.role = .both; cacheRole()   // offline: unlock locally
            return true
        }
        do {
            let u = try await APIClient(baseURL: base)
                .becomeCreator(handle: h, displayName: currentUser.displayName, platforms: [],
                               instagram: instagram, youtube: youtube, token: token)
            applyUser(u.toUser())
            return true
        } catch { print("[Reelie] becomeCreator: FAILED — \(error)"); return false }
    }

    func signOut() {
        authToken = nil
        refreshToken = nil
        currentUser.role = .viewer
        currentUser.creatorStatus = nil
        UserDefaults.standard.removeObject(forKey: Self.roleKey)
        UserDefaults.standard.removeObject(forKey: Self.creatorStatusKey)
        earningsSummary = nil
        creatorStats = nil
        selectedTab = .discover
    }

    // ---- Self-serve generation (creator picks a video → server builds a page) --
    @MainActor
    func availableVideos() async -> [AvailableVideo] {
        guard let base = apiBaseURL, let token = authToken else { return [] }
        do { return try await APIClient(baseURL: base).availableVideos(token: token) }
        catch { print("[Reelie] availableVideos: \(error)"); return [] }
    }

    /// Starts generation and watches it. Returns `.done(slug)` when the page is
    /// built, `.failed` on a real error, or `.building` if our watch window elapses
    /// while the backend is still working (the page will land in Drafts) — so a slow
    /// (e.g. 1080p) job is never mistaken for a failure.
    @MainActor @discardableResult
    func generatePage(videoId: String? = nil, url: String? = nil,
                      uploadFileURL: URL? = nil, title: String? = nil,
                      onProgress: ((_ stage: String, _ phase: String?, _ preview: [GenPreviewItem], _ posterUrl: String?) -> Void)? = nil) async -> GenerationOutcome {
        guard let base = apiBaseURL, let token = authToken else { return .failed(reason: nil) }
        let client = APIClient(baseURL: base)
        // A pasted link or upload runs live extraction (download → transcribe → find
        // products → cut clips), which can take several minutes — especially at 1080p.
        // Watch generously so we don't declare failure while the backend is still busy.
        let isHeavy = (url != nil || uploadFileURL != nil)
        let maxPolls = isHeavy ? 300 : 40                 // ~10 min for links/uploads
        let interval: UInt64 = isHeavy ? 2_000_000_000 : 1_500_000_000

        // Ask iOS for background time so polling keeps going if the user leaves the
        // app. The actual analysis runs server-side regardless — this just keeps the
        // live progress alive as long as iOS allows; the finished page is waiting in
        // Drafts either way.
        #if canImport(UIKit)
        var bgTask: UIBackgroundTaskIdentifier = .invalid
        bgTask = UIApplication.shared.beginBackgroundTask(withName: "reelie.generate") {
            if bgTask != .invalid { UIApplication.shared.endBackgroundTask(bgTask); bgTask = .invalid }
        }
        defer { if bgTask != .invalid { UIApplication.shared.endBackgroundTask(bgTask); bgTask = .invalid } }
        #endif

        do {
            var uploadKey: String? = nil
            if let f = uploadFileURL {
                onProgress?("Uploading your video…", "upload", [], nil)
                uploadKey = try await client.uploadVideo(fileURL: f, token: token)
            }
            let jobId = try await client.startGeneration(videoId: videoId, url: url,
                                                         uploadKey: uploadKey, title: title, token: token)
            for _ in 0..<maxPolls {
                let st = try await client.generationStatus(jobId: jobId, token: token)
                onProgress?(st.stage, st.phase, st.preview ?? [], st.posterUrl)
                if st.status == "done" {
                    await refreshFromAPI()
                    await loadMyPages()
                    return .done(slug: st.pageSlug ?? "")
                }
                if st.status == "error" {
                    print("[Reelie] generate error: \(st.error ?? "")")
                    return .failed(reason: st.error)
                }
                try? await Task.sleep(nanoseconds: interval)
            }
            // Watch window elapsed — the backend keeps building; it'll show in Drafts.
            await loadMyPages()
            return .building
        } catch { print("[Reelie] generatePage: \(error)"); return .failed(reason: nil) }
    }

    // ---- Creator studio --------------------------------------------------
    var socials: [SocialAccount] = [
        SocialAccount(platform: .youtube, status: .connected(handle: "@glowbyjess")),
        SocialAccount(platform: .instagram, status: .disconnected),
        SocialAccount(platform: .tiktok, status: .comingSoon),
    ]
    var videos: [SourceVideo] = SampleData.videos
    var generatedPages: [GeneratedPage] = GeneratedPageStore.loadAll()

    func fullURL(for slug: String) -> String { "\(baseURL)\(handle)/\(slug)" }
    var profileURL: String { "\(baseURL)\(handle)" }

    // ---- Earnings --------------------------------------------------------
    var pending = "$62.10"
    var ready = "$186.40"
    var readyToPayout = "$186.40"
    var paidSoFar = "$412.85"
    var sales: [Sale] = SampleData.sales

    var lifetimeEarnings: Double { sales.reduce(0) { $0 + $1.value } }
    func earnings(sinceDaysAgo days: Int) -> Double {
        let cutoff = Date(timeIntervalSinceNow: -Double(days) * 86_400)
        return sales.filter { $0.date >= cutoff }.reduce(0) { $0 + $1.value }
    }
    var earningsThisWeek: Double { earnings(sinceDaysAgo: 7) }
    var earningsThisMonth: Double { earnings(sinceDaysAgo: 30) }
    func earnings(forPageSlug slug: String) -> Double {
        sales.filter { $0.pageSlug == slug }.reduce(0) { $0 + $1.value }
    }
    /// Per-page rollup for the "Earnings by page" list, richest first.
    var earningsByPage: [(slug: String, title: String, total: Double)] {
        let live = pages.filter { $0.status == .live }
        return live.map { pg in (pg.slug, pg.title, earnings(forPageSlug: pg.slug)) }
            .sorted { $0.total > $1.total }
    }

    // ---- Recommendations (content-based over the mock corpus) ------------

    /// Normalized product identity used to join across creators.
    static func productKey(_ brand: String, _ name: String) -> String {
        func norm(_ s: String) -> String {
            s.lowercased().filter { $0.isLetter || $0.isNumber || $0 == " " }
                .trimmingCharacters(in: .whitespaces)
        }
        return norm(brand) + "|" + norm(name)
    }

    /// Other creators whose routines include a product with the same identity.
    func creatorsUsing(brand: String, name: String, excluding handle: String? = nil) -> [Creator] {
        let key = Self.productKey(brand, name)
        var handles: [String] = []
        for page in catalog where page.handle != handle {
            if page.products.contains(where: { Self.productKey($0.brand, $0.name) == key }),
               !handles.contains(page.handle) {
                handles.append(page.handle)
            }
        }
        return handles.compactMap { creator($0) }
    }

    private func brandSet(_ handle: String) -> Set<String> {
        Set(routines(for: handle).flatMap { $0.products.map { $0.brand.lowercased() } })
    }

    /// Creators ranked by shared-brand overlap (Jaccard), with a reason string.
    func similarCreators(to handle: String, limit: Int = 5) -> [(creator: Creator, reason: String)] {
        let a = brandSet(handle)
        guard !a.isEmpty else { return [] }
        var scored: [(Creator, Double, [String])] = []
        for c in creators where c.handle != handle {
            let b = brandSet(c.handle)
            let shared = a.intersection(b)
            guard !shared.isEmpty else { continue }
            let score = Double(shared.count) / Double(a.union(b).count)
            // Restore display-cased brand names for the reason line.
            let names = routines(for: c.handle).flatMap { $0.products }
                .filter { shared.contains($0.brand.lowercased()) }
                .map { $0.brand }
            let uniqueNames = Array(Set(names)).sorted().prefix(2)
            scored.append((c, score, Array(uniqueNames)))
        }
        return scored.sorted { $0.1 > $1.1 }.prefix(limit).map {
            ($0.0, "Also uses \($0.2.joined(separator: ", "))")
        }
    }
}

// MARK: - Sample data (creator studio)

enum SampleData {
    static let videos: [SourceVideo] = [
        SourceVideo(title: "GRWM: date night edition 💄", meta: "2w ago · 48k views",
                    source: .reel, gradient: [Color(hex: 0xE8E4DA), Color(hex: 0xD8D2C4)]),
        SourceVideo(title: "My updated everyday makeup (2026)", meta: "3w ago · 112k views",
                    source: .youtube, gradient: [Color(hex: 0xE3DCD2), Color(hex: 0xCFC6B6)]),
        SourceVideo(title: "My K-beauty night routine", meta: "1mo ago · 96k views",
                    source: .reel, gradient: [Color(hex: 0xEDE8DF), Color(hex: 0xD9D2C2)], hasPage: true),
        SourceVideo(title: "Testing viral skincare so you don't have to", meta: "1mo ago · 203k views",
                    source: .youtube, gradient: [Color(hex: 0xE6E0D6), Color(hex: 0xD2CABA)]),
        SourceVideo(title: "5-minute school run face ⏱️", meta: "2mo ago · 31k views",
                    source: .reel, gradient: [Color(hex: 0xEAE5DC), Color(hex: 0xD6CEBF)]),
        SourceVideo(title: "Everything I repurchased this year", meta: "2mo ago · 87k views",
                    source: .youtube, gradient: [Color(hex: 0xE4DED3), Color(hex: 0xD0C7B7)]),
    ]

    static let morningRoutineProducts: [Product] = [
        Product(brand: "CeraVe", name: "Foaming Facial Cleanser", emoji: "🧼",
                evidence: .spoken, timestamp: "0:12", link: .reelie(rate: 6)),
        Product(brand: "The Ordinary", name: "Niacinamide 10% + Zinc 1%", emoji: "💧",
                evidence: .spoken, timestamp: "0:48", link: .own(label: "LTK")),
        Product(brand: "Beauty of Joseon", name: "Relief Sun SPF 50+", emoji: "🧴",
                evidence: .both, timestamp: "3:02", link: .reelie(rate: 8)),
        Product(brand: "Rare Beauty", name: "Soft Pinch Liquid Blush", emoji: "🪞",
                evidence: .spoken, timestamp: "4:15", note: "which shade?", link: .reelie(rate: 7)),
        Product(brand: "Laneige", name: "Lip Sleeping Mask", emoji: "💤",
                evidence: .shown, timestamp: "2:31", note: "are we right?",
                link: .reelie(rate: 6), status: .needsReview),
        Product(brand: "Arencia", name: "Green Rice Cleanser", emoji: "🌿",
                evidence: .shown, timestamp: "0:27", note: "are we right?",
                link: .reelie(rate: 7), status: .needsReview),
    ]

    static let kBeautyProducts: [Product] = [
        Product(brand: "Anua", name: "Anua Heartleaf 77% Toner", emoji: "🧴",
                evidence: .spoken, timestamp: "0:20", link: .reelie(rate: 8),
                earned: "$29.80", clicks: 241),
        Product(brand: "COSRX", name: "COSRX Snail 96 Mucin Essence", emoji: "💧",
                evidence: .spoken, timestamp: "1:02", link: .reelie(rate: 7),
                earned: "$24.10", clicks: 186),
        Product(brand: "Beauty of Joseon", name: "Beauty of Joseon Revive Eye Serum", emoji: "🌙",
                evidence: .spoken, timestamp: "2:14", link: .own(label: "LTK"),
                earned: nil, clicks: 124),
        Product(brand: "Laneige", name: "Laneige Water Sleeping Mask", emoji: "💤",
                evidence: .shown, timestamp: "3:30", link: .reelie(rate: 6),
                earned: "$10.90", clicks: 98),
        Product(brand: "Banila Co", name: "Banila Co Clean It Zero Balm", emoji: "🧼",
                evidence: .spoken, timestamp: "0:05", link: .reelie(rate: 7),
                earned: "$4.80", clicks: 40),
    ]

    // Dated sales so month/week/per-page rollups are computable.
    static let sales: [Sale] = [
        Sale(name: "Anua Heartleaf 77% Toner", emoji: "🧴", page: "K-beauty night routine · Ulta",
             value: 3.20, state: .pending, date: Date(timeIntervalSinceNow: -1 * 86_400), pageSlug: "k-beauty-night"),
        Sale(name: "Rare Beauty Soft Pinch Blush", emoji: "💄", page: "Everyday no-makeup makeup · Sephora",
             value: 2.10, state: .pending, date: Date(timeIntervalSinceNow: -2 * 86_400), pageSlug: "no-makeup-makeup"),
        Sale(name: "COSRX Snail 96 Essence", emoji: "💧", page: "K-beauty night routine · YesStyle",
             value: 1.85, state: .ready, date: Date(timeIntervalSinceNow: -4 * 86_400), pageSlug: "k-beauty-night"),
        Sale(name: "Charlotte Tilbury Flawless Filter", emoji: "✨", page: "Everyday no-makeup makeup · Sephora",
             value: 4.90, state: .ready, date: Date(timeIntervalSinceNow: -6 * 86_400), pageSlug: "no-makeup-makeup"),
        Sale(name: "Beauty of Joseon Relief Sun", emoji: "🌞", page: "Summer SPF favourites · Olive Young",
             value: 2.40, state: .ready, date: Date(timeIntervalSinceNow: -12 * 86_400), pageSlug: "summer-spf"),
        Sale(name: "Laneige Water Sleeping Mask", emoji: "💤", page: "K-beauty night routine · Sephora",
             value: 3.60, state: .ready, date: Date(timeIntervalSinceNow: -18 * 86_400), pageSlug: "k-beauty-night"),
        Sale(name: "Armani Luminous Silk Concealer", emoji: "🪞", page: "Everyday no-makeup makeup · Sephora",
             value: 5.20, state: .ready, date: Date(timeIntervalSinceNow: -24 * 86_400), pageSlug: "no-makeup-makeup"),
        Sale(name: "Beauty of Joseon Relief Sun", emoji: "🌞", page: "Summer SPF favourites · Amazon",
             value: 1.90, state: .ready, date: Date(timeIntervalSinceNow: -48 * 86_400), pageSlug: "summer-spf"),
        Sale(name: "COSRX Snail 96 Essence", emoji: "💧", page: "K-beauty night routine · Amazon",
             value: 2.75, state: .ready, date: Date(timeIntervalSinceNow: -66 * 86_400), pageSlug: "k-beauty-night"),
    ]
}
