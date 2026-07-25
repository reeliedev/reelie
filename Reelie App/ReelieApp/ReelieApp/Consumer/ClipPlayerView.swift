import SwiftUI
import AVKit

/// An autoplaying, muted, looping clip for a routine step — the same treatment as
/// the web page's `<video muted loop playsinline>` with tap-to-unmute. Plays only
/// while on screen (paused on disappear). Reuses PlayerLayerView (aspect-fill)
/// from the reels feed.
struct ClipPlayerView: View {
    let url: URL
    @State private var player = AVPlayer()
    @State private var muted = true
    @State private var loopObserver: NSObjectProtocol?

    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            Color.black
            PlayerLayerView(player: player)
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
