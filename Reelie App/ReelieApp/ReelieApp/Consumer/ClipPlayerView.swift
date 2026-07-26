import SwiftUI
import AVKit

/// An autoplaying, muted, looping clip for a routine step — the same treatment as
/// the web page's `<video muted loop playsinline>` with tap-to-unmute. Plays only
/// while on screen (paused on disappear). The clip is shown WHOLE (aspect-fit,
/// like Instagram reels), over a blurred fill so off-ratio clips have no black
/// bands — a phone-shot vertical clip is never cropped or zoomed off the edges.
struct ClipPlayerView: View {
    let url: URL
    var posterURL: URL? = nil
    @State private var player = AVPlayer()
    @State private var muted = true
    @State private var loopObserver: NSObjectProtocol?

    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            Color.black
            // Ambient blurred fill from the poster (cheap one-time blur).
            if let purl = posterURL {
                AsyncImage(url: purl) { img in
                    img.resizable().aspectRatio(contentMode: .fill)
                } placeholder: { Color.black }
                    .blur(radius: 26).opacity(0.5).allowsHitTesting(false)
            }
            // The whole clip, never cropped.
            PlayerLayerView(player: player, gravity: .resizeAspect)
            Button {
                muted.toggle()
                player.isMuted = muted
            } label: {
                Image(systemName: muted ? "speaker.slash.fill" : "speaker.wave.2.fill")
                    .font(.system(size: 12, weight: .bold)).foregroundStyle(.white)
                    .frame(width: 30, height: 30)
                    .background(.black.opacity(0.45), in: Circle())
            }
            .padding(8)
        }
        .onAppear { start() }
        .onDisappear { player.pause() }
    }

    private func start() {
        if player.currentItem == nil {
            let item = AVPlayerItem(url: url)
            player.replaceCurrentItem(with: item)
            player.isMuted = muted
            player.actionAtItemEnd = .none
            // Loop.
            loopObserver = NotificationCenter.default.addObserver(
                forName: .AVPlayerItemDidPlayToEndTime, object: item, queue: .main) { _ in
                    player.seek(to: .zero)
                    player.play()
                }
        }
        player.play()
    }
}
