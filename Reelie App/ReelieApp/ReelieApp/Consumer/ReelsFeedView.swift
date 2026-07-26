import SwiftUI
import AVKit

// MARK: - Feed models (decoded from GET /feed)

struct ReelItem: Codable, Identifiable {
    let clipUrl: String
    let poster: String
    let creator: ReelCreator
    let handle: String
    let slug: String
    let title: String
    let caption: String
    let likes: Int
    let likeKey: String
    let products: [ReelProduct]
    var id: String { likeKey }
}

struct ReelCreator: Codable {
    let name: String
    let handle: String
    let avatarGradient: [String]
}

struct ReelProduct: Codable, Identifiable {
    let brand: String
    let name: String
    let emoji: String
    let priceDisplay: String
    let shopUrl: String
    var id: String { name + shopUrl }
}

extension APIClient {
    func feed() async throws -> [ReelItem] {
        try await get("feed", as: [ReelItem].self)
    }
}

// MARK: - Backing AVPlayerLayer view (gravity is configurable)

struct PlayerLayerView: UIViewRepresentable {
    let player: AVPlayer
    /// `.resizeAspect` shows the whole video (Instagram reels); `.resizeAspectFill`
    /// crops to fill. Defaults to fill for callers that want cover behavior.
    var gravity: AVLayerVideoGravity = .resizeAspectFill
    func makeUIView(context: Context) -> PlayerUIView { PlayerUIView(player: player, gravity: gravity) }
    func updateUIView(_ view: PlayerUIView, context: Context) {
        view.playerLayer.player = player
        view.playerLayer.videoGravity = gravity
    }
}

final class PlayerUIView: UIView {
    override class var layerClass: AnyClass { AVPlayerLayer.self }
    var playerLayer: AVPlayerLayer { layer as! AVPlayerLayer }
    init(player: AVPlayer, gravity: AVLayerVideoGravity = .resizeAspectFill) {
        super.init(frame: .zero)
        playerLayer.player = player
        playerLayer.videoGravity = gravity
        backgroundColor = .clear
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
}

// MARK: - The feed (vertical paging, one reel per screen)

struct ReelsFeedView: View {
    @Environment(AppState.self) private var app
    @State private var items: [ReelItem] = []
    @State private var activeID: String?
    @State private var loaded = false
    @State private var refreshed = false

    var body: some View {
        Group {
            if !items.isEmpty {
                // The ScrollView fills the WHOLE screen (ignoresSafeArea), so each
                // cell (containerRelativeFrame) is exactly one screen tall and paging
                // snaps cleanly — no black bar, no peek, and the cell's tap targets
                // line up with what's on screen. Kept deliberately simple: no
                // GeometryReader wrapper (it made the container a different height
                // than the cells and mis-placed the first cell's controls).
                ScrollView(.vertical, showsIndicators: false) {
                    LazyVStack(spacing: 0) {
                        ForEach(items.filter { !app.isBlocked(creator: $0.handle) }) { item in
                            ReelCell(item: item, isActive: activeID == item.id)
                                .containerRelativeFrame([.horizontal, .vertical])
                                .id(item.id)
                        }
                    }
                    .scrollTargetLayout()
                }
                .scrollTargetBehavior(.paging)
                .scrollPosition(id: $activeID)
                .background(Color.black)
                // Ignore only the TOP safe area: the video runs full-bleed under
                // the status bar (no black space up top), but the container stops
                // at the tab bar — so each cell spans status-bar → tab-bar and the
                // overlay controls sit inside the video, never hidden behind the bar.
                .ignoresSafeArea(edges: .top)
            } else if loaded {
                EmptyDiscover()                 // no videos — branded light state
            } else {
                LoadingDiscover()               // first load — branded light, not a black void
            }
        }
        .task { await load() }
    }

    // Persist the last feed so reopening the app paints instantly instead of waiting.
    private static let cacheKey = "reelie.feed.v1"
    private static func cachedFeed() -> [ReelItem]? {
        guard let d = UserDefaults.standard.data(forKey: cacheKey) else { return nil }
        return try? JSONDecoder().decode([ReelItem].self, from: d)
    }
    private static func cacheFeed(_ items: [ReelItem]) {
        if let d = try? JSONEncoder().encode(items) { UserDefaults.standard.set(d, forKey: cacheKey) }
    }

    private func load() async {
        // 1) instant paint from the cached feed
        if items.isEmpty, let cached = Self.cachedFeed(), !cached.isEmpty {
            items = cached; activeID = cached.first?.id; loaded = true
        }
        // 2) refresh from the API once
        guard !refreshed else { return }
        refreshed = true
        guard let base = app.apiBaseURL else { loaded = true; return }
        let fresh = (try? await APIClient(baseURL: base).feed()) ?? []
        if !fresh.isEmpty {
            items = fresh
            if activeID == nil || !fresh.contains(where: { $0.id == activeID }) { activeID = fresh.first?.id }
            Self.cacheFeed(fresh)
        }
        loaded = true
    }
}

// MARK: - Branded empty state (shown when the feed has no videos)

private struct EmptyDiscover: View {
    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            Wordmark(size: 30)
            Text("Every routine, shoppable")
                .displayStyle(26).multilineTextAlignment(.center).padding(.top, 18)
            Text("Creators' videos show up here — every product found, priced and linked, automatically.")
                .font(ReelieFont.ui(14)).foregroundStyle(Palette.grey)
                .multilineTextAlignment(.center).lineSpacing(2)
                .padding(.top, 12).padding(.horizontal, 44)
            Spacer(); Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(
            ZStack {
                Color.white
                RadialGradient(colors: [Palette.sun.opacity(0.16), .clear],
                               center: .top, startRadius: 0, endRadius: 440)
            }
            .ignoresSafeArea()
        )
    }
}

// MARK: - Branded loading (first launch, while the feed fetches)

private struct LoadingDiscover: View {
    var body: some View {
        VStack(spacing: 18) {
            Spacer()
            Wordmark(size: 30)
            ProgressView().tint(Palette.ink)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(
            ZStack {
                Color.white
                RadialGradient(colors: [Palette.sun.opacity(0.16), .clear],
                               center: .top, startRadius: 0, endRadius: 440)
            }
            .ignoresSafeArea()
        )
    }
}

// MARK: - One reel

struct ReelCell: View {
    @Environment(AppState.self) private var app
    let item: ReelItem
    let isActive: Bool

    @State private var player = AVPlayer()
    @State private var muted = true
    @State private var ready = false
    @State private var liked = false
    @State private var likeCount = 0
    @State private var showHeart = false
    @State private var timeObserver: Any?

    var body: some View {
        ZStack {
            Color.black

            // Ambient blurred fill — the whole screen is covered even when the
            // video isn't 9:16, so there's never a black band (Instagram/TikTok do
            // exactly this). Cheap: a one-time blur of the poster, not the video.
            if let purl = URL(string: item.poster), !item.poster.isEmpty {
                AsyncImage(url: purl) { img in
                    img.resizable().aspectRatio(contentMode: .fill)
                } placeholder: { Color.black }
                    .blur(radius: 34)
                    .opacity(0.55)
                    .allowsHitTesting(false)
            }

            // The video itself, aspect-FIT so the entire frame is visible — never
            // cropped or zoomed past the edges. This is how reels are shown.
            PlayerLayerView(player: player, gravity: .resizeAspect)

            // Poster (also fit) covers the video until its first frame renders, so
            // you see the video instantly, never a black void.
            if !item.poster.isEmpty, let purl = URL(string: item.poster) {
                AsyncImage(url: purl) { img in
                    img.resizable().aspectRatio(contentMode: .fit)
                } placeholder: { Color.clear }
                    .allowsHitTesting(false)
                    .opacity(ready ? 0 : 1)
                    .animation(.easeOut(duration: 0.25), value: ready)
            }

            // dim gradient so overlay text is legible
            LinearGradient(colors: [.clear, .clear, .black.opacity(0.7)],
                           startPoint: .top, endPoint: .bottom)

            // tap anywhere to toggle sound
            Color.clear.contentShape(Rectangle())
                .onTapGesture { toggleMute() }

            overlay
        }
        .onAppear { setup() }
        .onDisappear {
            player.pause()
            if let o = timeObserver { player.removeTimeObserver(o); timeObserver = nil }
        }
        .onChange(of: isActive) { _, active in active ? play() : player.pause() }
        .onReceive(NotificationCenter.default.publisher(for: .AVPlayerItemDidPlayToEndTime)) { note in
            if let it = note.object as? AVPlayerItem, it == player.currentItem {
                player.seek(to: .zero); if isActive { player.play() }
            }
        }
    }

    // MARK: overlay

    private var overlay: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer()
            HStack(alignment: .bottom, spacing: 10) {
                // Left column flexes to fill the space that's left after the action
                // rail — so it can never push the rail (the Like button!) off the
                // right edge, and its own content never spills off the left.
                VStack(alignment: .leading, spacing: 12) {
                    creatorRow
                    Text(item.caption)
                        .font(ReelieFont.ui(14)).foregroundStyle(.white)
                        .lineLimit(2).shadow(color: .black.opacity(0.4), radius: 6)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    shopCard
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                actionRail
            }
            // The cell already stops at the tab bar, so only a small breathing gap
            // is needed — the shop card + action rail are guaranteed on-screen.
            // A little extra on the leading edge so the card/text aren't flush left.
            .padding(.leading, 24).padding(.trailing, 16).padding(.bottom, 20)
        }
    }

    private var creatorRow: some View {
        NavigationLink(value: ConsumerRoute.creatorProfile(handle: item.creator.handle)) {
            HStack(spacing: 9) {
                CreatorAvatar(gradient: item.creator.avatarGradient.map { Color(hexString: $0) }, size: 34)
                    .overlay(Circle().strokeBorder(.white, lineWidth: 1.5))
                VStack(alignment: .leading, spacing: 1) {
                    Text(item.creator.name).font(ReelieFont.ui(14, weight: .bold)).foregroundStyle(.white)
                    Text("@\(item.creator.handle)").font(ReelieFont.ui(12)).foregroundStyle(.white.opacity(0.85))
                }
            }
        }
        .buttonStyle(.plain)
    }

    private var shopCard: some View {
        let p = item.products.first
        return NavigationLink(value: ConsumerRoute.routine(key: item.likeKey)) {
            HStack(spacing: 11) {
                Text(p?.emoji ?? "🛍️").font(.system(size: 22))
                    .frame(width: 40, height: 40)
                    .background(.white.opacity(0.18), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                VStack(alignment: .leading, spacing: 1) {
                    Text(p?.brand.isEmpty == false ? p!.brand : "Featured")
                        .font(ReelieFont.ui(10.5, weight: .bold)).foregroundStyle(.white.opacity(0.8))
                        .textCase(.uppercase)
                    Text(p?.name ?? item.title).font(ReelieFont.ui(14, weight: .semibold))
                        .foregroundStyle(.white).lineLimit(1)
                    if let d = p?.priceDisplay, !d.isEmpty {
                        Text(d).font(ReelieFont.display(14)).foregroundStyle(.white)
                    }
                }
                Spacer(minLength: 4)
                Text("\(item.products.count) items")
                    .font(ReelieFont.ui(11, weight: .bold)).foregroundStyle(.white)
                    .padding(.horizontal, 11).padding(.vertical, 7)
                    .background(Color(hex: 0x6F5DF0), in: Capsule())
            }
            .padding(10)
            .frame(maxWidth: 300, alignment: .leading)
            .background(.white.opacity(0.14), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(.white.opacity(0.22), lineWidth: 1))
        }
        .buttonStyle(.plain)
    }

    private var actionRail: some View {
        VStack(spacing: 5) {
            Button { toggleLike() } label: {
                Image(systemName: liked ? "heart.fill" : "heart")
                    .font(.system(size: 27))
                    .foregroundStyle(liked ? Color(hex: 0xFF3B6B) : .white)
                    .shadow(color: .black.opacity(0.35), radius: 5)
            }
            .buttonStyle(.plain)
            Text("\(likeCount)").font(ReelieFont.ui(12.5, weight: .bold)).foregroundStyle(.white)
                .shadow(color: .black.opacity(0.4), radius: 4)
            Image(systemName: muted ? "speaker.slash.fill" : "speaker.wave.2.fill")
                .font(.system(size: 17)).foregroundStyle(.white.opacity(0.9))
                .padding(.top, 14)
                .onTapGesture { toggleMute() }
            UGCMenu(kind: "page", ref: item.likeKey, handle: item.handle, tint: .white)
                .padding(.top, 8)
        }
        .padding(.bottom, 4)
    }

    // MARK: playback + actions

    private func setup() {
        if player.currentItem == nil, let url = URL(string: item.clipUrl) {
            player.replaceCurrentItem(with: AVPlayerItem(url: url))
            player.isMuted = true
            player.actionAtItemEnd = .none
        }
        // Reveal the video (fade out the poster) once it actually starts rendering.
        if timeObserver == nil {
            timeObserver = player.addPeriodicTimeObserver(
                forInterval: CMTime(seconds: 0.1, preferredTimescale: 600), queue: .main) { t in
                    if t.seconds > 0.05 { ready = true }
                }
        }
        likeCount = item.likes
        liked = app.isSaved(key: item.likeKey)   // heart reflects Saved state
        if isActive { play() }
    }
    private func play() { player.isMuted = muted; player.play() }
    private func toggleMute() {
        muted.toggle(); player.isMuted = muted
        if !muted { player.play() }
    }
    private func toggleLike() {
        liked.toggle()
        likeCount = max(0, likeCount + (liked ? 1 : -1))
        LikeStore.set(item.likeKey, liked)
        app.setSaved(key: item.likeKey, liked)   // heart also saves to the Saved tab
        Task {
            if let base = app.apiBaseURL,
               let n = try? await APIClient(baseURL: base)
                .toggleLike(handle: item.handle, slug: item.slug, clientId: LikeStore.clientId, liked: liked) {
                await MainActor.run { likeCount = n }
            }
        }
    }
}

// MARK: - Guest likes (device-local, mirrors the web)

enum LikeStore {
    private static let key = "reelie.likes"
    static var clientId: String {
        if let v = UserDefaults.standard.string(forKey: "reelie.cid") { return v }
        let v = UUID().uuidString
        UserDefaults.standard.set(v, forKey: "reelie.cid")
        return v
    }
    static func liked() -> Set<String> { Set(UserDefaults.standard.stringArray(forKey: key) ?? []) }
    static func contains(_ k: String) -> Bool { liked().contains(k) }
    static func set(_ k: String, _ on: Bool) {
        var s = liked(); if on { s.insert(k) } else { s.remove(k) }
        UserDefaults.standard.set(Array(s), forKey: key)
    }
}

extension APIClient {
    func toggleLike(handle: String, slug: String, clientId: String, liked: Bool) async throws -> Int {
        try await post("likes/toggle",
                       body: ["handle": handle, "slug": slug, "clientId": clientId, "liked": liked],
                       as: LikeResp.self).count
    }
}
private struct LikeResp: Decodable { let count: Int }
