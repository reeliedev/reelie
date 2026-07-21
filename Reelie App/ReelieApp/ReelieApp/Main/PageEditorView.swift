import SwiftUI

/// Edit any text on a creator's own generated page — title, intro, disclosure,
/// custom link, and per-product name / note / narration. Saves an override so
/// edits persist and the page re-renders without re-extraction.
struct PageEditorView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    let pageID: UUID

    private var idx: Int? { app.generatedPages.firstIndex { $0.id == pageID } }

    var body: some View {
        @Bindable var app = app
        if let idx {
            VStack(spacing: 0) {
                ZStack {
                    HStack { BackButton { dismiss() }; Spacer() }
                    StepLabel(text: "EDIT PAGE")
                }
                .frame(height: 44).padding(.horizontal, 28)

                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 0) {
                        field("TITLE", text: $app.generatedPages[idx].title)
                        field("YOUR LINK", text: Binding(
                            get: { app.generatedPages[idx].customSlug ?? app.generatedPages[idx].slug },
                            set: { app.generatedPages[idx].customSlug = $0 }),
                            prefix: "reelie.io/\(app.generatedPages[idx].handle)/", mono: true)
                        editor("INTRO", text: Binding(
                            get: { app.generatedPages[idx].intro },
                            set: { app.generatedPages[idx].intro = $0 }))
                        editor("DISCLOSURE", text: $app.generatedPages[idx].disclosure)

                        SectionLabel(text: "PRODUCTS").padding(.top, 24).padding(.bottom, 4)
                        ForEach(app.generatedPages[idx].products.indices, id: \.self) { i in
                            productEditor(pageIndex: idx, productIndex: i)
                        }
                    }
                    .padding(.horizontal, 28).padding(.top, 8).padding(.bottom, 16)
                }

                VStack(spacing: 0) {
                    Rectangle().fill(Palette.line).frame(height: 1.5)
                    BigButton(title: "Save changes", style: .sun) {
                        let page = app.generatedPages[idx]
                        Task { await app.savePageEdits(page); dismiss() }
                    }
                    .padding(.horizontal, 28).padding(.top, 12)
                }
                .padding(.bottom, 8)
            }
            .background(.white)
            .navigationBarBackButtonHidden(true)
            .toolbar(.hidden, for: .navigationBar)
        } else {
            Text("Page not found").font(ReelieFont.ui(15)).foregroundStyle(Palette.grey)
        }
    }

    // MARK: field builders

    private func field(_ label: String, text: Binding<String>,
                       prefix: String? = nil, mono: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            SectionLabel(text: label)
            HStack(spacing: 2) {
                if let prefix {
                    Text(prefix).font(ReelieFont.ui(13.5, weight: .medium)).foregroundStyle(Palette.grey)
                }
                TextField("", text: text)
                    .font(ReelieFont.ui(14, weight: mono ? .bold : .medium)).foregroundStyle(Palette.ink)
                    .textInputAutocapitalization(mono ? .never : .sentences)
                    .autocorrectionDisabled(mono)
            }
            .padding(.horizontal, 13).padding(.vertical, 12)
            .hairlineCard(cornerRadius: 14)
        }
        .padding(.top, 18)
    }

    private func editor(_ label: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            SectionLabel(text: label)
            TextField("", text: text, axis: .vertical)
                .lineLimit(2...6)
                .font(ReelieFont.ui(14)).foregroundStyle(Palette.ink)
                .padding(.horizontal, 13).padding(.vertical, 12)
                .hairlineCard(cornerRadius: 14)
        }
        .padding(.top, 18)
    }

    private func productEditor(pageIndex: Int, productIndex i: Int) -> some View {
        @Bindable var app = app
        return VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                EmojiThumb(emoji: app.generatedPages[pageIndex].products[i].emoji, size: 34, corner: 9)
                Text(app.generatedPages[pageIndex].products[i].brand.uppercased())
                    .font(ReelieFont.ui(11, weight: .bold)).tracking(0.6).foregroundStyle(Palette.grey)
                Spacer()
            }
            TextField("Product name", text: $app.generatedPages[pageIndex].products[i].name)
                .font(ReelieFont.ui(14, weight: .medium)).foregroundStyle(Palette.ink)
                .padding(.horizontal, 12).padding(.vertical, 10)
                .hairlineCard(cornerRadius: 12)
            TextField("Note (short)", text: optional($app.generatedPages[pageIndex].products[i].note), axis: .vertical)
                .lineLimit(1...3)
                .font(ReelieFont.ui(13)).foregroundStyle(Palette.ink)
                .padding(.horizontal, 12).padding(.vertical, 10)
                .hairlineCard(cornerRadius: 12)
            TextField("Narration (how you use it)", text: optional($app.generatedPages[pageIndex].products[i].guide), axis: .vertical)
                .lineLimit(2...5)
                .font(ReelieFont.ui(13)).foregroundStyle(Palette.ink)
                .padding(.horizontal, 12).padding(.vertical, 10)
                .hairlineCard(cornerRadius: 12)
        }
        .padding(14)
        .hairlineCard(cornerRadius: 16)
        .padding(.bottom, 11)
    }

    /// Bridge an optional String binding to a non-optional TextField binding.
    private func optional(_ b: Binding<String?>) -> Binding<String> {
        Binding(get: { b.wrappedValue ?? "" },
                set: { b.wrappedValue = $0.isEmpty ? nil : $0 })
    }
}

#Preview {
    let a = AppState(); a.onboardingComplete = true
    return NavigationStack {
        if let p = a.generatedPages.first { PageEditorView(pageID: p.id) }
        else { Text("No generated pages") }
    }.environment(a)
}
