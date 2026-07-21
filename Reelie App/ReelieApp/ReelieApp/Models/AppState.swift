import SwiftUI
import Observation

enum MainTab: Hashable {
    // Consumer surface (always available)
    case discover, saved, profile
    // Creator studio (shown only when the account has creator role)
    case pages, earnings
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
        if favorites.contains(page.key) { favorites.remove(page.key) }
        else { favorites.insert(page.key) }
        FavoritesStore.savePages(favorites)
    }
    func isFavorite(creator handle: String) -> Bool { favoriteCreators.contains(handle) }
    func toggleFavorite(creator handle: String) {
        if favoriteCreators.contains(handle) { favoriteCreators.remove(handle) }
        else { favoriteCreators.insert(handle) }
        FavoritesStore.saveCreators(favoriteCreators)
    }

    var favoritePages: [GeneratedPage] { catalog.filter { favorites.contains($0.key) } }
    var favoriteCreatorList: [Creator] { creators.filter { favoriteCreators.contains($0.handle) } }

    func creator(_ handle: String) -> Creator? { creators.first { $0.handle == handle } }
    func routines(for handle: String) -> [GeneratedPage] { catalog.filter { $0.handle == handle } }
    func page(withKey key: String) -> GeneratedPage? { catalog.first { $0.key == key } }

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
            if isCreator { await loadMyPages() }
        } catch {
            backendConnected = false   // keep the mock corpus
            print("[Reelie] refreshFromAPI: FAILED — \(error)")
        }
    }

    // The creator's own published pages, loaded from the API. When set, the studio
    // shows these instead of the mock sample pages.
    var showingAPIPages = false

    @MainActor
    func loadMyPages() async {
        guard let base = apiBaseURL, isCreator, let token = authToken else { return }
        do {
            generatedPages = try await APIClient(baseURL: base).myPages(token: token)
            showingAPIPages = true
        } catch { print("[Reelie] loadMyPages: \(error)") }
    }

    /// Persist creator text edits to the backend (PATCH). Offline → local overrides.
    @MainActor
    func savePageEdits(_ page: GeneratedPage) async {
        guard let base = apiBaseURL, let token = authToken else {
            OverridesStore.save(page); return
        }
        var fields: [String: Any] = ["title": page.title, "intro": page.intro, "disclosure": page.disclosure]
        let products: [[String: Any]] = page.products.compactMap { p in
            guard let sid = p.serverId else { return nil }
            var d: [String: Any] = ["id": sid, "name": p.name]
            if let n = p.note { d["note"] = n }
            if let g = p.guide { d["guide"] = g }
            return d
        }
        if !products.isEmpty { fields["products"] = products }
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
        guard let base = apiBaseURL, isCreator else { return }
        do {
            earningsSummary = try await APIClient(baseURL: base).earnings(handle: handle)
            backendConnected = true
        } catch {
            print("[Reelie] loadEarnings: FAILED — \(error)")
        }
    }

    // ---- Creator auth ----------------------------------------------------
    // Consumers stay guests (no login). Auth only happens on the creator path.
    // Degrades gracefully offline (no API) so the app still works on mock data.
    private static let tokenKey = "reelie.authToken"
    // Stored in the Keychain (encrypted), not UserDefaults. One-time migration of
    // any token previously written to UserDefaults.
    var authToken: String? = (KeychainStore.get(account: AppState.tokenKey)
        ?? UserDefaults.standard.string(forKey: AppState.tokenKey)) {
        didSet {
            KeychainStore.set(authToken, account: AppState.tokenKey)
            UserDefaults.standard.removeObject(forKey: AppState.tokenKey)   // clear legacy
        }
    }

    private func applyUser(_ u: User) {
        currentUser.email = u.email
        if !u.displayName.isEmpty { currentUser.displayName = u.displayName }
        if !u.handle.isEmpty { currentUser.handle = u.handle }
        if !u.avatarGradient.isEmpty { currentUser.avatarGradient = u.avatarGradient }
        currentUser.role = u.role
    }

    @MainActor
    func restoreSession() async {
        guard let base = apiBaseURL, let token = authToken else { return }
        do { applyUser(try await APIClient(baseURL: base).me(token: token).toUser()) }
        catch { authToken = nil }   // token invalid/expired → back to guest
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

    @MainActor @discardableResult
    func becomeCreatorAPI(handle: String) async -> Bool {
        let h = handle.trimmingCharacters(in: .whitespaces).lowercased()
        currentUser.handle = h
        guard let base = apiBaseURL, let token = authToken else {
            currentUser.role = .both   // offline: unlock locally
            return true
        }
        do {
            let u = try await APIClient(baseURL: base)
                .becomeCreator(handle: h, displayName: currentUser.displayName, platforms: [], token: token)
            applyUser(u.toUser())
            return true
        } catch { print("[Reelie] becomeCreator: FAILED — \(error)"); return false }
    }

    func signOut() {
        authToken = nil
        currentUser.role = .viewer
        earningsSummary = nil
        selectedTab = .discover
    }

    // ---- Self-serve generation (creator picks a video → server builds a page) --
    @MainActor
    func availableVideos() async -> [AvailableVideo] {
        guard let base = apiBaseURL, let token = authToken else { return [] }
        do { return try await APIClient(baseURL: base).availableVideos(token: token) }
        catch { print("[Reelie] availableVideos: \(error)"); return [] }
    }

    /// Starts generation and polls to completion. Returns the new page's slug (or
    /// nil on failure). Refreshes the catalogue so the page is browsable.
    @MainActor @discardableResult
    func generatePage(videoId: String? = nil, url: String? = nil,
                      uploadFileURL: URL? = nil, title: String? = nil,
                      onStage: ((String) -> Void)? = nil) async -> String? {
        guard let base = apiBaseURL, let token = authToken else { return nil }
        let client = APIClient(baseURL: base)
        // A pasted link or upload runs live extraction (download → transcribe → find
        // products), so allow more time than generating from an already-extracted video.
        let maxPolls = (url != nil || uploadFileURL != nil) ? 150 : 40
        do {
            var uploadKey: String? = nil
            if let f = uploadFileURL {
                onStage?("Uploading your video…")
                uploadKey = try await client.uploadVideo(fileURL: f, token: token)
            }
            let jobId = try await client.startGeneration(videoId: videoId, url: url,
                                                         uploadKey: uploadKey, title: title, token: token)
            for _ in 0..<maxPolls {
                let st = try await client.generationStatus(jobId: jobId, token: token)
                onStage?(st.stage)
                if st.status == "done" {
                    await refreshFromAPI()
                    await loadMyPages()
                    return st.pageSlug
                }
                if st.status == "error" { print("[Reelie] generate error: \(st.error ?? "")"); return nil }
                try? await Task.sleep(nanoseconds: 1_200_000_000)
            }
        } catch { print("[Reelie] generatePage: \(error)") }
        return nil
    }

    // ---- Creator studio --------------------------------------------------
    var socials: [SocialAccount] = [
        SocialAccount(platform: .youtube, status: .connected(handle: "@glowbyjess")),
        SocialAccount(platform: .instagram, status: .disconnected),
        SocialAccount(platform: .tiktok, status: .comingSoon),
    ]
    var videos: [SourceVideo] = SampleData.videos
    var pages: [Page] = SampleData.pages
    var generatedPages: [GeneratedPage] = GeneratedPageStore.loadAll()

    var pagesNeedingReview: [Page] { pages.filter { $0.status == .needsReview } }
    var pagesProcessing: [Page] { pages.filter { $0.status == .processing } }
    var pagesLive: [Page] { pages.filter { $0.status == .live } }
    var pagesArchived: [Page] { pages.filter { $0.status == .archived } }

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

    static let pages: [Page] = [
        Page(title: "Your morning skincare routine", emoji: "🎬", slug: "morning-skincare",
             status: .needsReview, meta: "From your Reel, yesterday · 6 products",
             products: morningRoutineProducts),
        Page(title: "New YouTube video", emoji: "🎬", slug: "new-video",
             status: .processing, meta: "Watching \"GRWM: date night\" · posted 2h ago"),
        Page(title: "Everyday \"no makeup\" makeup", emoji: "💄", slug: "no-makeup-makeup",
             status: .live, meta: "1.2k views · 214 shop clicks",
             views: "1.2k", shopClicks: "214", earned: "$41.10"),
        Page(title: "My K-beauty night routine", emoji: "🧴", slug: "k-beauty-night",
             status: .live, meta: "3.8k views · 689 shop clicks",
             views: "3.8k", shopClicks: "689", earned: "$84.20", products: kBeautyProducts),
        Page(title: "Summer SPF favourites", emoji: "🌞", slug: "summer-spf",
             status: .live, meta: "640 views · 96 shop clicks",
             views: "640", shopClicks: "96", earned: "$18.40"),
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
