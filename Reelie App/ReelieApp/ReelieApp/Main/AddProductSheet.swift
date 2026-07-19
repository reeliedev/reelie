import SwiftUI

/// Screen 08 — Add a product (bottom sheet with search).
struct AddProductSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var query = "laneige lip"
    @State private var added: Set<String> = ["Lip Sleeping Mask — Berry"]

    private let results: [SearchResult] = [
        SearchResult(brand: "Laneige", name: "Lip Sleeping Mask — Berry", emoji: "💤", rate: "earns 6%"),
        SearchResult(brand: "Laneige", name: "Lip Glowy Balm — Peach", emoji: "💄", rate: "earns 6%"),
        SearchResult(brand: "Laneige", name: "Lip Treatment Balm", emoji: "✨", rate: "earns 6%"),
    ]
    private let fromCaption = SearchResult(brand: "Peripera", name: "Ink Velvet Lip Tint — #8",
                                           emoji: "🌸", rate: "mentioned in your caption · earns 7%")

    var body: some View {
        VStack(spacing: 0) {
            // Grabber + title.
            Capsule().fill(Color(hex: 0xE0E0E0)).frame(width: 40, height: 5).padding(.top, 10)

            ZStack {
                Text("Add a product").displayStyle(22)
                HStack {
                    Spacer()
                    Button { dismiss() } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 12, weight: .bold)).foregroundStyle(Palette.grey)
                            .frame(width: 30, height: 30)
                            .background(Palette.soft, in: Circle())
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.vertical, 16)

            // Search field.
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass").foregroundStyle(Palette.grey)
                TextField("Search products", text: $query)
                    .font(ReelieFont.ui(15, weight: .medium)).foregroundStyle(Palette.ink)
                    .tint(Palette.ink)
            }
            .padding(.horizontal, 14).padding(.vertical, 13)
            .background(Palette.soft, in: RoundedRectangle(cornerRadius: 14, style: .continuous))

            // Results.
            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {
                    SectionLabel(text: "RESULTS").padding(.top, 14).padding(.bottom, 9)
                    ForEach(results) { result in
                        ResultRow(result: result, added: added.contains(result.name)) { toggle(result.name) }
                        Rectangle().fill(Color(hex: 0xF5F5F5)).frame(height: 1.5)
                    }

                    SectionLabel(text: "FROM YOUR CAPTION").padding(.top, 14).padding(.bottom, 9)
                    ResultRow(result: fromCaption, added: added.contains(fromCaption.name)) { toggle(fromCaption.name) }
                }
            }

            (
                Text("Can't find it? ")
                    .foregroundStyle(Palette.fainter)
                + Text("Add it manually").foregroundStyle(Palette.ink).fontWeight(.bold)
            )
            .font(ReelieFont.ui(13))
            .padding(.vertical, 14)
        }
        .padding(.horizontal, 24)
        .presentationDetents([.fraction(0.78)])
        .presentationDragIndicator(.hidden)
        .presentationCornerRadius(30)
    }

    private func toggle(_ name: String) {
        if added.contains(name) { added.remove(name) } else { added.insert(name) }
    }
}

private struct SearchResult: Identifiable {
    let id = UUID()
    let brand: String
    let name: String
    let emoji: String
    let rate: String
}

private struct ResultRow: View {
    let result: SearchResult
    let added: Bool
    let onTap: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            EmojiThumb(emoji: result.emoji, size: 42, corner: 11)
            VStack(alignment: .leading, spacing: 2) {
                Text(result.brand.uppercased())
                    .font(ReelieFont.ui(11, weight: .bold)).tracking(0.6).foregroundStyle(Palette.grey)
                Text(result.name)
                    .font(ReelieFont.ui(14, weight: .medium)).foregroundStyle(Palette.ink).lineLimit(1)
                Text(result.rate).font(ReelieFont.ui(11, weight: .bold)).foregroundStyle(Palette.grey)
            }
            Spacer(minLength: 4)
            Button(action: onTap) {
                Text(added ? "Added ✓" : "Add")
                    .font(ReelieFont.ui(13, weight: .bold)).foregroundStyle(Palette.ink)
                    .padding(.horizontal, 15).padding(.vertical, 8)
                    .background(added ? Palette.sun : .white,
                                in: RoundedRectangle(cornerRadius: 11, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 11)
                        .strokeBorder(added ? Palette.sun : Palette.ink, lineWidth: 1.5))
            }
            .buttonStyle(PressableStyle())
        }
        .padding(.vertical, 10)
    }
}

#Preview {
    Color.white.sheet(isPresented: .constant(true)) { AddProductSheet() }
}
