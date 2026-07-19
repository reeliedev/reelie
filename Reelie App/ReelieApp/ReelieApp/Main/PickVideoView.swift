import SwiftUI

/// Screen 06 — Pick a video to build a page from. Self-serve: the chosen video is
/// generated into a shoppable page server-side and published to the creator's
/// account. Videos + generation come from the backend (`/me/videos`, `/me/generate`).
struct PickVideoView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss

    @State private var videos: [AvailableVideo] = []
    @State private var connected: [ConnectedVideo] = []
    @State private var connectedPlatform = ""
    @State private var loaded = false
    @State private var selected: String?
    @State private var linkText = ""
    @State private var phase: Phase = .pick
    @State private var stage = "Starting…"
    @State private var newTitle = ""

    enum Phase { case pick, generating, done, failed }

    private let columns = [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)]

    var body: some View {
        VStack(spacing: 0) {
            ZStack {
                HStack { BackButton { dismiss() }; Spacer() }
                Text(phase == .generating ? "Building your page" : "Pick a video")
                    .font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.ink)
            }
            .frame(height: 44).padding(.horizontal, 28)

            switch phase {
            case .pick: pickBody
            case .generating: generatingBody
            case .done: doneBody
            case .failed: failedBody
            }
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .task { await load() }
    }

    private func load() async {
        guard !loaded else { return }
        await app.loadConnections()
        // Prefer videos from a connected account (YouTube, then Instagram).
        for platform in ["youtube", "instagram"] where app.isConnected(platform) {
            let vids = await app.connectionVideos(platform)
            if !vids.isEmpty { connected = vids; connectedPlatform = platform; break }
        }
        videos = await app.availableVideos()
        loaded = true
        selected = videos.first?.videoId
    }

    // MARK: pick

    private var pickBody: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 0) {
                // Primary: paste a link to your own video.
                SectionLabel(text: "PASTE A VIDEO LINK").padding(.top, 8).padding(.bottom, 10)
                HStack(spacing: 9) {
                    Image(systemName: "link").font(.system(size: 14, weight: .medium)).foregroundStyle(Palette.grey)
                    TextField("YouTube, TikTok, or a video URL", text: $linkText)
                        .font(ReelieFont.ui(14)).foregroundStyle(Palette.ink)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                        .keyboardType(.URL)
                }
                .padding(.horizontal, 14).padding(.vertical, 13)
                .hairlineCard(cornerRadius: 14, color: linkText.isEmpty ? Palette.line : Palette.ink)
                BigButton(title: "Make a page from this link", style: .sun) {
                    Task { await generateFromLink() }
                }
                .opacity(linkText.trimmingCharacters(in: .whitespaces).isEmpty ? 0.5 : 1)
                .disabled(linkText.trimmingCharacters(in: .whitespaces).isEmpty)
                .padding(.top, 10)
                Text("We'll watch it, find every product, and build your shoppable page.")
                    .font(ReelieFont.ui(12)).foregroundStyle(Palette.grey).padding(.top, 8)

                if !connected.isEmpty {
                    SectionLabel(text: "FROM YOUR \(connectedPlatform.uppercased())").padding(.top, 28).padding(.bottom, 10)
                    VStack(spacing: 10) {
                        ForEach(connected) { v in connectedRow(v) }
                    }
                }

                if !videos.isEmpty {
                    SectionLabel(text: "OR PICK A PAST VIDEO").padding(.top, 28).padding(.bottom, 12)
                    LazyVGrid(columns: columns, spacing: 10) {
                        ForEach(videos) { v in tile(v) }
                    }
                    if selected != nil {
                        BigButton(title: "Make this page", style: .ink) { Task { await generate() } }
                            .padding(.top, 14)
                    }
                }
            }
            .padding(.horizontal, 28).padding(.top, 4).padding(.bottom, 24)
        }
    }

    /// One video from a connected account — tap to build a page from its URL.
    private func connectedRow(_ v: ConnectedVideo) -> some View {
        Button { Task { await runGeneration(url: v.url) } } label: {
            HStack(spacing: 12) {
                GradientPoster(colors: [Color(hex: 0xE8E4DA), Color(hex: 0xD8D2C4)], corner: 10)
                    .frame(width: 54, height: 54)
                    .overlay(Image(systemName: "play.fill").font(.system(size: 15)).foregroundStyle(.white.opacity(0.9)))
                VStack(alignment: .leading, spacing: 2) {
                    Text(v.title).font(ReelieFont.ui(14, weight: .medium)).foregroundStyle(Palette.ink)
                        .lineLimit(1)
                    Text(v.published).font(ReelieFont.ui(11.5)).foregroundStyle(Palette.grey)
                }
                Spacer()
                Image(systemName: "wand.and.stars").font(.system(size: 15)).foregroundStyle(Palette.grey)
            }
            .padding(.horizontal, 12).frame(height: 74)
            .hairlineCard(cornerRadius: 14, color: Palette.line)
        }
        .buttonStyle(.plain)
    }

    private func generateFromLink() async {
        await runGeneration(url: linkText.trimmingCharacters(in: .whitespaces))
    }

    /// Shared: extract + build a page from any video URL (pasted or connected).
    private func runGeneration(url: String) async {
        guard !url.isEmpty else { return }
        phase = .generating; stage = "Fetching your video…"
        let slug = await app.generatePage(url: url) { stage = $0 }
        if let slug {
            newTitle = app.catalog.first { $0.handle == app.handle && $0.slug == slug }?.title ?? "Your new page"
            phase = .done
        } else {
            phase = .failed
        }
    }

    private func tile(_ v: AvailableVideo) -> some View {
        Button { selected = v.videoId } label: {
            GradientPoster(colors: [Color(hex: 0xE8E4DA), Color(hex: 0xD8D2C4)], corner: 18)
                .aspectRatio(3.0/4.0, contentMode: .fit)
                .overlay(alignment: .topTrailing) {
                    if selected == v.videoId { SunTick(size: 24).padding(9) }
                }
                .overlay(alignment: .bottom) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(v.title)
                            .font(ReelieFont.ui(12, weight: .bold)).foregroundStyle(.white)
                            .lineLimit(2).multilineTextAlignment(.leading)
                        Text("\(v.numProducts) products found")
                            .font(ReelieFont.ui(10.5)).foregroundStyle(.white.opacity(0.8))
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 10).padding(.top, 26).padding(.bottom, 9)
                    .background(LinearGradient(colors: [.clear, Palette.ink.opacity(0.6)],
                                               startPoint: .top, endPoint: .bottom))
                }
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .strokeBorder(selected == v.videoId ? Palette.ink : .clear, lineWidth: 2.5))
        }
        .buttonStyle(.plain)
    }

    private func generate() async {
        guard let vid = selected else { return }
        phase = .generating; stage = "Starting…"
        let slug = await app.generatePage(videoId: vid) { stage = $0 }
        if let slug {
            newTitle = app.catalog.first { $0.handle == app.handle && $0.slug == slug }?.title ?? "Your new page"
            phase = .done
        } else {
            phase = .failed
        }
    }

    // MARK: states

    private var generatingBody: some View {
        VStack(spacing: 0) {
            Spacer()
            ProgressView().scaleEffect(1.3).tint(Palette.ink)
            Text(stage).displayStyle(24).padding(.top, 20)
            Text("Finding your products, pricing them, and publishing your page.")
                .font(ReelieFont.ui(14)).foregroundStyle(Palette.grey)
                .multilineTextAlignment(.center).frame(maxWidth: 280).lineSpacing(2).padding(.top, 10)
            Spacer(); Spacer()
        }
        .padding(.horizontal, 28)
    }

    private var doneBody: some View {
        VStack(spacing: 0) {
            Spacer()
            SunTick(size: 64)
            Text("Your page is live").displayStyle(28).padding(.top, 18)
            Text(newTitle)
                .font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.grey).padding(.top, 6)
            BigButton(title: "Done", style: .sun) { app.selectedTab = .discover; dismiss() }
                .padding(.top, 30).padding(.horizontal, 28)
            Spacer(); Spacer()
        }
        .padding(.horizontal, 28)
    }

    private var failedBody: some View {
        VStack(spacing: 0) {
            Spacer()
            Text("😕").font(.system(size: 44))
            Text("We had trouble with that one").displayStyle(24).multilineTextAlignment(.center).padding(.top, 14)
            BigButton(title: "Try another video", style: .sun) { phase = .pick }
                .padding(.top, 28).padding(.horizontal, 28)
            Spacer(); Spacer()
        }
        .padding(.horizontal, 28)
    }
}

#Preview {
    NavigationStack { PickVideoView() }
        .environment({ let a = AppState(); a.onboardingComplete = true; a.currentUser.role = .both; return a }())
}
