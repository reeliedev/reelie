import SwiftUI

/// Screen 03 — Claim your page.
struct ClaimPageView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    var onContinue: () -> Void

    @State private var handle: String = ""

    var body: some View {
        VStack(spacing: 0) {
            OnboardingNav(step: "STEP 2 OF 2", onBack: { dismiss() })

            VStack(spacing: 12) {
                Text("Claim your page").displayStyle(30)
                Text("This is the link you'll say in your videos, so keep it easy to type.")
                    .font(ReelieFont.ui(15))
                    .foregroundStyle(Palette.grey)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 280)
                    .lineSpacing(2)
            }
            .padding(.top, 26)

            Spacer()

            VStack(spacing: 12) {
                // Editable handle field with the reelie.com/ prefix.
                HStack(spacing: 2) {
                    Text(app.baseURL)
                        .font(ReelieFont.ui(16, weight: .medium))
                        .foregroundStyle(Palette.grey)
                    TextField("", text: $handle)
                        .font(ReelieFont.ui(16, weight: .bold))
                        .foregroundStyle(Palette.ink)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                        .tint(Palette.ink)
                }
                .padding(.horizontal, 16)
                .frame(height: 58)
                .overlay(
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .strokeBorder(Palette.ink, lineWidth: 1.5)
                )

                if isAvailable {
                    HStack(spacing: 7) {
                        SunTick(size: 18)
                        Text("It's yours").font(ReelieFont.ui(13.5, weight: .bold)).foregroundStyle(Palette.ink)
                    }
                }

                (
                    Text("We matched it to your YouTube handle, ")
                    + Text("@\(app.handle)").foregroundStyle(Palette.grey).fontWeight(.medium)
                    + Text(" — keeping them the same makes it easier for viewers to find you.")
                )
                .font(ReelieFont.ui(12.5))
                .foregroundStyle(Palette.faint)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 270)
                .lineSpacing(2)
                .padding(.top, 14)
            }

            Spacer()

            BigButton(title: claimTitle, style: .sun) {
                app.handle = handle.isEmpty ? app.handle : handle
                onContinue()
            }
            .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .onAppear { if handle.isEmpty { handle = app.handle } }
    }

    private var isAvailable: Bool { handle.count >= 3 }
    private var claimTitle: String {
        "Claim \(app.baseURL)\(handle.isEmpty ? app.handle : handle)"
    }
}

#Preview {
    NavigationStack { ClaimPageView(onContinue: {}) }.environment(AppState())
}
