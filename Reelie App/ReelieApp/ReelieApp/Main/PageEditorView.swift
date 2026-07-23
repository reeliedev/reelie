import SwiftUI

/// Edit any text on a creator's own generated page — title, intro, disclosure,
/// custom link, and per-product name / note / narration. Saves an override so
/// edits persist and the page re-renders without re-extraction.
struct PageEditorView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    let pageID: UUID

    struct EditableFAQ: Identifiable { let id = UUID(); var q: String; var a: String }
    @State private var faqs: [EditableFAQ] = []
    @State private var faqsLoaded = false

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

                        faqSection
                    }
                    .padding(.horizontal, 28).padding(.top, 8).padding(.bottom, 16)
                }

                VStack(spacing: 0) {
                    Rectangle().fill(Palette.line).frame(height: 1.5)
                    BigButton(title: "Save changes", style: .sun) {
                        let page = app.generatedPages[idx]
                        // Only send FAQs once loaded, so we never wipe existing ones.
                        let faqPayload: [[String: String]]? = faqsLoaded
                            ? faqs.filter { !$0.q.trimmingCharacters(in: .whitespaces).isEmpty }
                                  .map { ["q": $0.q, "a": $0.a] }
                            : nil
                        Task { await app.savePageEdits(page, customFaqs: faqPayload); dismiss() }
                    }
                    .padding(.horizontal, 28).padding(.top, 12)
                }
                .padding(.bottom, 8)
            }
            .background(.white)
            .navigationBarBackButtonHidden(true)
            .toolbar(.hidden, for: .navigationBar)
            .task {
                guard !faqsLoaded else { return }
                faqs = (await app.loadCustomFaqs(slug: app.generatedPages[idx].slug))
                    .map { EditableFAQ(q: $0.q, a: $0.a) }
                faqsLoaded = true
            }
        } else {
            Text("Page not found").font(ReelieFont.ui(15)).foregroundStyle(Palette.grey)
        }
    }

    // MARK: custom FAQ builder

    @ViewBuilder private var faqSection: some View {
        SectionLabel(text: "QUESTIONS & ANSWERS").padding(.top, 24).padding(.bottom, 4)
        Text("Add your own Q&A — great for AI answer engines and shoppers.")
            .font(ReelieFont.ui(11.5)).foregroundStyle(Palette.faint).padding(.bottom, 10)

        ForEach($faqs) { $faq in
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("QUESTION").font(ReelieFont.ui(10, weight: .bold)).tracking(0.6).foregroundStyle(Palette.grey)
                    Spacer()
                    Button {
                        faqs.removeAll { $0.id == faq.id }
                    } label: {
                        Image(systemName: "trash").font(.system(size: 13, weight: .bold)).foregroundStyle(Palette.grey)
                    }
                    .buttonStyle(.plain)
                }
                TextField("e.g. Is this good for oily skin?", text: $faq.q, axis: .vertical)
                    .lineLimit(1...3).font(ReelieFont.ui(14, weight: .medium)).foregroundStyle(Palette.ink)
                    .padding(.horizontal, 12).padding(.vertical, 10).hairlineCard(cornerRadius: 12)
                TextField("Your answer", text: $faq.a, axis: .vertical)
                    .lineLimit(2...5).font(ReelieFont.ui(13)).foregroundStyle(Palette.ink)
                    .padding(.horizontal, 12).padding(.vertical, 10).hairlineCard(cornerRadius: 12)
            }
            .padding(14).hairlineCard(cornerRadius: 16).padding(.bottom, 11)
        }

        Button {
            faqs.append(EditableFAQ(q: "", a: ""))
        } label: {
            HStack(spacing: 6) {
                Image(systemName: "plus").font(.system(size: 13, weight: .bold))
                Text("Add a question").font(ReelieFont.ui(13.5, weight: .bold))
            }
            .foregroundStyle(Palette.ink)
            .frame(maxWidth: .infinity).padding(.vertical, 13)
            .hairlineCard(cornerRadius: 14, color: Palette.line)
        }
        .buttonStyle(.plain)
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
