import SwiftUI
import UniformTypeIdentifiers
import PhotosUI
import AVFoundation

/// A video picked from the Photos library, copied into our sandbox as a temp file.
struct PickedMovie: Transferable {
    let url: URL
    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(contentType: .movie) { SentTransferredFile($0.url) }
        importing: { received in
            let dst = FileManager.default.temporaryDirectory
                .appendingPathComponent("upload-\(UUID().uuidString).mov")
            try? FileManager.default.removeItem(at: dst)
            try FileManager.default.copyItem(at: received.file, to: dst)
            return PickedMovie(url: dst)
        }
    }
}

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
    @State private var showFilePicker = false
    @State private var photoItem: PhotosPickerItem?

    // Live-analysis state — mirrors the web: the video plays while products are
    // detected and revealed one-by-one, then it lands on the editable draft.
    @State private var genPhase = ""                    // upload/analyzing/found/building/done
    @State private var preview: [GenPreviewItem] = []   // products detected so far
    @State private var revealed = 0                     // how many are shown in the list
    @State private var localVideoURL: URL?              // the uploaded clip, shown while analyzing
    @State private var revealTask: Task<Void, Never>?

    enum Phase { case pick, generating, done, failed }

    /// Single progress sink passed to `generatePage`: updates the stage label and,
    /// once products arrive, kicks off the staggered reveal (one every 0.8s).
    private func onProgress(_ stage: String, _ phase: String?, _ newPreview: [GenPreviewItem]) {
        self.stage = stage
        if let phase { self.genPhase = phase }
        if preview.isEmpty, !newPreview.isEmpty {
            preview = newPreview
            startReveal()
        }
    }

    private func startReveal() {
        revealTask?.cancel()
        revealTask = Task {
            while revealed < preview.count {
                try? await Task.sleep(nanoseconds: 800_000_000)
                if Task.isCancelled { return }
                if revealed < preview.count { revealed += 1 }
            }
        }
    }

    /// Generation finished. Reveal any remaining products, then land on the
    /// editable draft page (the app twin of the web's review/edit screen) — not a
    /// "your page is live" screen, since generated pages start as drafts.
    private func finish(slug: String?) {
        revealTask?.cancel()
        revealed = preview.count
        guard let slug, let page = app.generatedPages.first(where: { $0.slug == slug }) else {
            newTitle = "Your new page"; phase = .done; return
        }
        newTitle = page.title
        // Small beat so the last product lands before the transition.
        Task {
            try? await Task.sleep(nanoseconds: 500_000_000)
            app.selectedTab = .pages
            app.homePath = [.generatedPage(pageID: page.id)]
        }
    }

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
        .fileImporter(isPresented: $showFilePicker,
                      allowedContentTypes: [.movie, .mpeg4Movie, .quickTimeMovie],
                      allowsMultipleSelection: false) { result in
            if case .success(let urls) = result, let picked = urls.first {
                Task { await runUpload(picked) }
            }
        }
        .onChange(of: photoItem) { _, item in
            guard let item else { return }
            Task { await uploadFromPhotos(item) }
        }
    }

    /// Load the picked camera-roll video, normalize it to a standard H.264 MP4
    /// (camera-roll videos are often HEVC/HDR, which the pipeline can't process),
    /// then upload + generate — so it works just like a computer upload.
    private func uploadFromPhotos(_ item: PhotosPickerItem) async {
        defer { photoItem = nil }
        phase = .generating; stage = "Preparing your video…"; genPhase = "upload"
        preview = []; revealed = 0; localVideoURL = nil
        guard let movie = try? await item.loadTransferable(type: PickedMovie.self) else { phase = .failed; return }
        let toUpload = await exportToMP4(movie.url) ?? movie.url   // fall back to original if export fails
        localVideoURL = toUpload                                    // play it while we analyze
        let slug = await app.generatePage(uploadFileURL: toUpload, onProgress: onProgress)
        if movie.url != toUpload { try? FileManager.default.removeItem(at: movie.url) }
        if slug != nil { finish(slug: slug) } else { phase = .failed }
    }

    /// Re-encode to H.264/AAC MP4. The resolution presets output H.264 (not HEVC),
    /// so an iPhone HEVC/HDR clip becomes a standard MP4 the backend can process.
    private func exportToMP4(_ src: URL) async -> URL? {
        let asset = AVURLAsset(url: src)
        let dst = FileManager.default.temporaryDirectory
            .appendingPathComponent("export-\(UUID().uuidString).mp4")
        try? FileManager.default.removeItem(at: dst)
        let preset = AVAssetExportPreset1920x1080
        guard AVAssetExportSession.exportPresets(compatibleWith: asset).contains(preset),
              let export = AVAssetExportSession(asset: asset, presetName: preset) else { return nil }
        export.outputURL = dst
        export.outputFileType = .mp4
        export.shouldOptimizeForNetworkUse = true
        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            export.exportAsynchronously { cont.resume() }
        }
        return export.status == .completed ? dst : nil
    }

    /// Copy the picked file into our sandbox (security-scoped access ends when the
    /// importer closes), then upload + generate.
    private func runUpload(_ picked: URL) async {
        let scoped = picked.startAccessingSecurityScopedResource()
        defer { if scoped { picked.stopAccessingSecurityScopedResource() } }
        let dst = FileManager.default.temporaryDirectory
            .appendingPathComponent(picked.lastPathComponent)
        try? FileManager.default.removeItem(at: dst)
        do { try FileManager.default.copyItem(at: picked, to: dst) }
        catch { phase = .failed; return }
        phase = .generating; stage = "Uploading your video…"; genPhase = "upload"
        preview = []; revealed = 0; localVideoURL = dst
        let slug = await app.generatePage(uploadFileURL: dst, onProgress: onProgress)
        if slug != nil { finish(slug: slug) } else { phase = .failed }
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

                // Upload your own video — camera roll is the default (where creators'
                // videos live); a file picker is the alternative.
                SectionLabel(text: "OR UPLOAD YOUR VIDEO").padding(.top, 28).padding(.bottom, 10)
                PhotosPicker(selection: $photoItem, matching: .videos, photoLibrary: .shared()) {
                    HStack(spacing: 10) {
                        Image(systemName: "photo.on.rectangle.angled").font(.system(size: 18)).foregroundStyle(Palette.ink)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Choose from Camera Roll").font(ReelieFont.ui(14, weight: .semibold)).foregroundStyle(Palette.ink)
                            Text("Pick a video you've filmed or posted — best quality").font(ReelieFont.ui(11.5)).foregroundStyle(Palette.grey)
                        }
                        Spacer()
                        Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(Palette.grey)
                    }
                    .padding(.horizontal, 14).frame(height: 62)
                    .hairlineCard(cornerRadius: 14, color: Palette.ink)   // emphasized (default)
                }
                .buttonStyle(.plain)

                Button { showFilePicker = true } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "folder").font(.system(size: 15)).foregroundStyle(Palette.grey)
                        Text("Upload a file (MP4 or MOV)").font(ReelieFont.ui(13.5, weight: .medium)).foregroundStyle(Palette.grey)
                        Spacer()
                        Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(Palette.faint)
                    }
                    .padding(.horizontal, 14).frame(height: 52)
                    .hairlineCard(cornerRadius: 12, color: Palette.line)
                }
                .buttonStyle(.plain).padding(.top, 10)

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
        phase = .generating; stage = "Fetching your video…"; genPhase = ""
        preview = []; revealed = 0; localVideoURL = nil
        let slug = await app.generatePage(url: url, onProgress: onProgress)
        if slug != nil { finish(slug: slug) } else { phase = .failed }
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
        phase = .generating; stage = "Starting…"; genPhase = ""
        preview = []; revealed = 0; localVideoURL = nil
        let slug = await app.generatePage(videoId: vid, onProgress: onProgress)
        if slug != nil { finish(slug: slug) } else { phase = .failed }
    }

    // MARK: states

    // Live analysis — the video plays and scans while detected products drop into
    // the list one-by-one, exactly like the web analyzer.
    private var generatingBody: some View {
        VStack(spacing: 0) {
            VStack(spacing: 5) {
                Text(analyzingTitle).displayStyle(23).multilineTextAlignment(.center)
                Text(analyzingSub)
                    .font(ReelieFont.ui(13)).foregroundStyle(Palette.grey)
                    .multilineTextAlignment(.center)
            }
            .padding(.top, 6).padding(.bottom, 16).padding(.horizontal, 20)

            AnalyzingStage(videoURL: localVideoURL, ping: revealed)
                .frame(height: 280)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .padding(.horizontal, 28)

            HStack(spacing: 8) {
                if revealed > 0 {
                    Text("\(revealed) product\(revealed == 1 ? "" : "s") found")
                        .font(ReelieFont.ui(13.5, weight: .bold)).foregroundStyle(Palette.ink)
                } else {
                    ProgressView().scaleEffect(0.8).tint(Palette.ink)
                    Text("Looking for products…")
                        .font(ReelieFont.ui(13.5, weight: .semibold)).foregroundStyle(Palette.grey)
                }
                Spacer()
            }
            .padding(.horizontal, 28).padding(.top, 16).padding(.bottom, 6)

            ScrollView(showsIndicators: false) {
                VStack(spacing: 8) {
                    ForEach(revealedItems) { item in analyzedRow(item) }
                }
                .padding(.horizontal, 28).padding(.top, 4).padding(.bottom, 20)
            }
            .animation(.spring(response: 0.35, dampingFraction: 0.82), value: revealed)
        }
        .onDisappear { revealTask?.cancel() }
    }

    private var analyzingTitle: String {
        switch genPhase {
        case "building": return "Pricing & building your page"
        case "done":     return "Draft ready to review"
        default:         return "Analyzing your video"
        }
    }
    private var analyzingSub: String {
        switch genPhase {
        case "upload":   return "Uploading your video…"
        case "building": return stage
        case "done":     return "Check it over, then publish."
        default:         return preview.isEmpty
            ? "Watching every second to find the products…"
            : "Products detected in the video ✨"
        }
    }
    private var revealedItems: [GenPreviewItem] { Array(preview.prefix(revealed)).reversed() }

    private func analyzedRow(_ item: GenPreviewItem) -> some View {
        HStack(spacing: 12) {
            Text("🔎").font(.system(size: 17))
                .frame(width: 40, height: 40)
                .background(Palette.soft, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                (Text(item.label).font(ReelieFont.ui(14.5, weight: .semibold)).foregroundStyle(Palette.ink)
                 + (item.variant.map { Text("  \($0)").font(ReelieFont.ui(12)).foregroundStyle(Palette.grey) } ?? Text("")))
                    .lineLimit(1)
                Text("found at \(item.foundAt)")
                    .font(ReelieFont.ui(11.5)).foregroundStyle(Palette.faint)
            }
            Spacer(minLength: 4)
            Image(systemName: "checkmark.circle.fill").font(.system(size: 16)).foregroundStyle(Palette.sun)
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
        .hairlineCard(cornerRadius: 14)
        .transition(.asymmetric(insertion: .move(edge: .top).combined(with: .opacity),
                                removal: .opacity))
    }

    private var doneBody: some View {
        VStack(spacing: 0) {
            Spacer()
            SunTick(size: 64)
            Text("Draft ready to review").displayStyle(28).multilineTextAlignment(.center).padding(.top, 18)
            Text(newTitle)
                .font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.grey).padding(.top, 6)
            BigButton(title: "Review & publish", style: .sun) {
                if let page = app.generatedPages.first(where: { $0.title == newTitle }) {
                    app.selectedTab = .pages
                    app.homePath = [.generatedPage(pageID: page.id)]
                } else { dismiss() }
            }
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

// MARK: - Analyzing stage (the video being scanned)

/// The uploaded clip playing (muted, looping) under a sweeping scan line — or a
/// branded placeholder for link/past-video sources that have no local file. The
/// border flashes each time a new product is detected. Mirrors the web `.az-stage`.
private struct AnalyzingStage: View {
    let videoURL: URL?
    var ping: Int
    @State private var player = AVPlayer()
    @State private var scan = false
    @State private var flash = false
    @State private var loopObserver: NSObjectProtocol?

    var body: some View {
        ZStack {
            if let url = videoURL {
                PlayerLayerView(player: player)
                    .onAppear { start(url) }
                    .onDisappear { player.pause() }
            } else {
                LinearGradient(colors: [Color(hex: 0xE8E4DA), Color(hex: 0xD8D2C4)],
                               startPoint: .top, endPoint: .bottom)
                Text("🎬").font(.system(size: 54))
            }
            GeometryReader { geo in
                Rectangle()
                    .fill(LinearGradient(colors: [.clear, Palette.sun.opacity(0.95), .clear],
                                         startPoint: .leading, endPoint: .trailing))
                    .frame(height: 3)
                    .shadow(color: Palette.sun.opacity(0.9), radius: 8)
                    .offset(y: scan ? geo.size.height - 3 : 0)
                    .animation(.easeInOut(duration: 2.1).repeatForever(autoreverses: true), value: scan)
            }
            Color.black.opacity(0.10)
        }
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .strokeBorder(Palette.sun, lineWidth: 3)
                .opacity(flash ? 0.9 : 0)
        )
        .onAppear { scan = true }
        .onChange(of: ping) { _, _ in
            withAnimation(.easeIn(duration: 0.12)) { flash = true }
            withAnimation(.easeOut(duration: 0.6).delay(0.12)) { flash = false }
        }
    }

    private func start(_ url: URL) {
        if player.currentItem == nil {
            let item = AVPlayerItem(url: url)
            player.replaceCurrentItem(with: item)
            player.isMuted = true
            player.actionAtItemEnd = .none
            loopObserver = NotificationCenter.default.addObserver(
                forName: .AVPlayerItemDidPlayToEndTime, object: item, queue: .main) { _ in
                    player.seek(to: .zero); player.play()
                }
        }
        player.play()
    }
}

#Preview {
    NavigationStack { PickVideoView() }
        .environment({ let a = AppState(); a.onboardingComplete = true; a.currentUser.role = .both; return a }())
}
