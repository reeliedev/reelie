import SwiftUI
import AVKit

// MARK: - Feed models (decoded from GET /feed)

struct ReelItem: Decodable, Identifiable {
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

struct ReelCreator: Decodable {
    let name: String
    let handle: String
    let avatarGradient: [String]
}

struct ReelProduct: Decodable, Identifiable {
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

// MARK: - Aspect-fill video layer (SwiftUI's VideoPlayer only aspect-fits)

struct PlayerLayerView: UIViewRepresentable {
    let player: AVPlayer
    func makeUIView(context: Context) -> PlayerUIView { PlayerUIView(player: player) }
    func updateUIView(_ view: PlayerUIView, context: Context) { view.playerLayer.player = player }
}

final class PlayerUIView: UIView {
    override class var layerClass: AnyClass { AVPlayerLayer.self }
    var playerLayer: AVPlayerLayer { layer as! AVPlayerLayer }
    init(player: AVPlayer) {
        super.init(frame: .zero)
        playerLayer.player = player
        playerLayer.videoGravity = .resizeAspectFill
        backgroundColor = .black
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
}

// MARK: - The feed (vertical paging, one reel per screen)

struct ReelsFeedView: View {
    @Environment(AppState.self) private var app
    @State private var items: [ReelItem] = []
    @State private var activeID: String?
    @State private var loaded = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            if items.isEmpty && loaded {
                VStack(spacing: 8) {
                    Text("No videos yet").font(ReelieFont.ui(16, weight: .bold)).foregroundStyle(.white)
                    Text("Creators' clips will show up here.").font(ReelieFont.ui(13)).foregroundStyle(.white.opacity(0.6))
                }
            } else {
                ScrollView(.vertical, showsIndicators: false) {
                    LazyVStack(spacing: 0) {
                        ForEach(items) { item in
                            ReelCell(item: item, isActive: activeID == item.id)
                                .containerRelativeFrame([.horizontal, .vertical])
                                .id(item.id)
                        }
                    }
                    .scrollTargetLayout()
                }
                .scrollTargetBehavior(.paging)
                .scrollPosition(id: $activeID)
            }
        }
        .overlay(alignment: .top) {
            Text("Reelie").font(ReelieFont.display(22)).foregroundStyle(.white)
                .shadow(color: .black.opacity(0.4), radius: 6)
                .padding(.top, 6)
        }
        .task { await load() }
    }

    private func load() async {
        guard !loaded, let base = app.apiBaseURL else { loaded = true; return }
        items = (try? await APIClient(baseURL: base).feed()) ?? []
        activeID = items.first?.id
        loaded = true
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

    var body: some View {
        ZStack {
            Color.black
            PlayerLayerView(player: player).ignoresSafeArea()

            // dim gradient so overlay text is legible
            LinearGradient(colors: [.clear, .clear, .black.opacity(0.7)],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()

            // tap anywhere to toggle sound
            Color.clear.contentShape(Rectangle())
                .onTapGesture { toggleMute() }

            overlay
        }
        .onAppear { setup() }
        .onDisappear { player.pause() }
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
            HStack(alignment: .bottom) {
                VStack(alignment: .leading, spacing: 12) {
                    creatorRow
                    Text(item.caption)
                        .font(ReelieFont.ui(14)).foregroundStyle(.white)
                        .lineLimit(2).shadow(color: .black.opacity(0.4), radius: 6)
                        .frame(maxWidth: 260, alignment: .leading)
                    shopCard
                }
                Spacer()
                actionRail
            }
            .padding(.horizontal, 16).padding(.bottom, 22)
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
        likeCount = item.likes
        liked = LikeStore.contains(item.likeKey)
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
