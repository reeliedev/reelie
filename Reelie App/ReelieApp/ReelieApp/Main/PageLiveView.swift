import SwiftUI

/// Screen 09 — Your page is live.
struct PageLiveView: View {
    @Environment(AppState.self) private var app
    let slug: String
    let title: String

    @State private var showShare = false

    var body: some View {
        VStack(spacing: 0) {
            // Nav: "Done" pops to Home root.
            HStack {
                Spacer()
                Button("Done") { app.homePath.removeAll() }
                    .font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.ink)
                    .buttonStyle(.plain)
            }
            .frame(height: 44)

            VStack(spacing: 0) {
                SunTick(size: 56).padding(.bottom, 18)
                Text("Your page is live").displayStyle(30)
                Text("Now put the link where your viewers will look for it.")
                    .font(ReelieFont.ui(15)).foregroundStyle(Palette.grey)
                    .multilineTextAlignment(.center).frame(maxWidth: 270).lineSpacing(2)
                    .padding(.top, 10)

                // URL pill.
                HStack(spacing: 10) {
                    (
                        Text(app.baseURL).foregroundStyle(Palette.grey).fontWeight(.medium)
                        + Text("\(app.handle)/\(slug)").foregroundStyle(Palette.ink).fontWeight(.bold)
                    )
                    .font(ReelieFont.ui(14.5)).lineLimit(1)
                    Spacer(minLength: 4)
                    PillButton(title: "Copy", style: .ink) {
                        UIPasteboard.general.string = app.fullURL(for: slug)
                    }
                }
                .padding(.horizontal, 16).padding(.vertical, 14)
                .background(Palette.soft, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                .padding(.top, 22)
            }
            .padding(.top, 14)

            Spacer()

            // Distribution snippets.
            VStack(spacing: 12) {
                SectionLabel(text: "ADD IT TO YOUR POST").frame(maxWidth: .infinity, alignment: .center)
                SnippetRow(icon: "pin.fill", title: "Pinned comment",
                           desc: "\"everything's linked here ↓ reelie.com/\(app.handle)/…\"", cta: "Copy")
                SnippetRow(icon: "doc.text.fill", title: "Video description",
                           desc: "\"Full routine with every product: reelie.com/…\"", cta: "Copy")
                SnippetRow(icon: "bubble.left.fill", title: "Comment keyword",
                           desc: "Auto-DM the page when someone comments \"ROUTINE\"", cta: "Set up")
            }

            Spacer()

            VStack(spacing: 14) {
                BigButton(title: "Share page", style: .sun) { showShare = true }
                Button("View my page") { app.homePath.removeAll() }
                    .font(ReelieFont.ui(14, weight: .medium)).foregroundStyle(Palette.grey)
                    .buttonStyle(.plain)
            }
            .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .sheet(isPresented: $showShare) {
            ShareLink(item: URL(string: "https://\(app.fullURL(for: slug))")!) { Text("Share link") }
        }
    }
}

private struct SnippetRow: View {
    let icon: String
    let title: String
    let desc: String
    let cta: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon).font(.system(size: 17)).foregroundStyle(Palette.ink).frame(width: 22)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(ReelieFont.ui(14, weight: .bold)).foregroundStyle(Palette.ink)
                Text(desc).font(ReelieFont.ui(12)).foregroundStyle(Palette.grey).lineLimit(1)
            }
            Spacer(minLength: 4)
            Text(cta)
                .font(ReelieFont.ui(12.5, weight: .bold)).foregroundStyle(Palette.ink)
                .padding(.horizontal, 12).padding(.vertical, 7)
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Palette.line, lineWidth: 1.5))
        }
        .padding(.horizontal, 15).padding(.vertical, 13)
        .hairlineCard(cornerRadius: 16)
    }
}

#Preview {
    NavigationStack { PageLiveView(slug: "morning-skincare", title: "Morning skincare") }
        .environment({ let a = AppState(); a.onboardingComplete = true; return a }())
}
