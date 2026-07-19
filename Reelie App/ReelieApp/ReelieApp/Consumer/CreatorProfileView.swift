import SwiftUI

/// The per-creator index (consumer view). Reached from Discover / recommendations.
struct CreatorProfileView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    let handle: String

    private var creator: Creator? { app.creator(handle) }

    var body: some View {
        VStack(spacing: 0) {
            // Nav bar
            ZStack {
                HStack { BackButton { dismiss() }; Spacer() }
                StepLabel(text: "CREATOR")
            }
            .frame(height: 44).padding(.horizontal, 28)

            if let creator {
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 0) {
                        header(creator)

                        SectionLabel(text: "ROUTINES").padding(.top, 26).padding(.bottom, 12)
                        ForEach(app.routines(for: handle)) { RoutineCard(page: $0, showCreator: false) }

                        RecoRail(title: "SIMILAR CREATORS",
                                 items: app.similarCreators(to: handle))
                            .padding(.top, 14)
                    }
                    .padding(.horizontal, 28).padding(.bottom, 24)
                }
            } else {
                Spacer()
                Text("Creator not found").font(ReelieFont.ui(15)).foregroundStyle(Palette.grey)
                Spacer()
            }
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
    }

    private func header(_ creator: Creator) -> some View {
        VStack(spacing: 0) {
            CreatorAvatar(gradient: creator.avatarGradient, size: 78).padding(.top, 6)
            Text(creator.displayName).displayStyle(26).padding(.top, 12)
            Text("@\(creator.handle) · \(creator.platformLine)")
                .font(ReelieFont.ui(13)).foregroundStyle(Palette.grey).padding(.top, 6)

            Button {
                app.toggleFavorite(creator: handle)
            } label: {
                HStack(spacing: 7) {
                    Image(systemName: app.isFavorite(creator: handle) ? "heart.fill" : "heart")
                        .font(.system(size: 14, weight: .bold))
                    Text(app.isFavorite(creator: handle) ? "Saved" : "Save creator")
                        .font(ReelieFont.ui(14, weight: .bold))
                }
                .foregroundStyle(app.isFavorite(creator: handle) ? Palette.ink : Palette.ink)
                .padding(.horizontal, 20).padding(.vertical, 11)
                .background(app.isFavorite(creator: handle) ? Palette.sun : .white,
                            in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .strokeBorder(Palette.ink, lineWidth: app.isFavorite(creator: handle) ? 0 : 1.5))
            }
            .buttonStyle(PressableStyle())
            .padding(.top, 16)
        }
    }
}

#Preview {
    NavigationStack { CreatorProfileView(handle: "mariskincare") }
        .environment({ let a = AppState(); a.onboardingComplete = true; return a }())
}
