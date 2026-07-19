import Foundation

// MARK: - Generated page model
//
// A page produced by the page-generator backend ("Reelie App/page-generator").
// It's kept distinct from the hand-authored `Page` because a generated page
// carries web-publishing context the app screens need — the creator handle,
// the public URL, and a creator-editable custom link. Product rows reuse the
// existing `Product` model (now with price fields).

struct GeneratedPage: Identifiable {
    let id = UUID()
    var title: String
    var emoji: String
    var slug: String                 // generated default slug
    var customSlug: String?          // creator's own link; overrides slug when set
    var meta: String
    var intro: String = ""           // guide overview paragraph (editable)
    var handle: String
    var creatorName: String
    var platforms: [String]
    var disclosure: String
    var products: [Product]
    var archived: Bool = false

    /// The slug actually used in the public URL — the creator's custom link wins.
    var pathSlug: String {
        if let c = customSlug?.trimmingCharacters(in: .whitespaces), !c.isEmpty { return c }
        return slug
    }

    /// Display URL for the public page (matches the generator's config domain).
    var publicURL: String { "reelie.shop/\(handle)/\(pathSlug)" }

    var platformLine: String { platforms.joined(separator: " & ") }

    /// Stable identity across launches (favorites, overrides) — not the random UUID.
    var key: String { "\(handle)/\(slug)" }
}

// MARK: - Decodable DTO (mirrors render/app_json.py output, camelCase)

struct GeneratedPageDTO: Decodable {
    let title: String
    let emoji: String
    let slug: String
    let customSlug: String?
    let meta: String
    let intro: String?
    let handle: String
    let creatorName: String
    let platforms: [String]
    let disclosure: String
    let archived: Bool?
    let products: [GeneratedProductDTO]

    struct GeneratedProductDTO: Decodable {
        let id: String?
        let brand: String
        let name: String
        let emoji: String
        let variant: String?
        let evidence: String
        let timestamp: String
        let note: String?
        let guide: String?
        let retailer: String?
        let priceDisplay: String?
        let priceEstimated: Bool?
        let linkKind: String
        let rate: Int?
        let ownLabel: String?
    }
}

// MARK: - DTO -> app model mapping

extension GeneratedPageDTO {
    func toGeneratedPage() -> GeneratedPage {
        GeneratedPage(
            title: title,
            emoji: emoji,
            slug: slug,
            customSlug: customSlug,
            meta: meta,
            intro: intro ?? "",
            handle: handle,
            creatorName: creatorName,
            platforms: platforms,
            disclosure: disclosure,
            products: products.enumerated().map { idx, p in p.toProduct() },
            archived: archived ?? false
        )
    }
}

extension GeneratedPageDTO.GeneratedProductDTO {
    func toProduct() -> Product {
        Product(
            serverId: id,
            brand: brand,
            name: name,
            emoji: emoji,
            evidence: Self.mapEvidence(evidence),
            timestamp: timestamp,
            note: note,
            guide: guide,
            link: mapLink(),
            priceDisplay: priceDisplay,
            retailer: retailer,
            priceEstimated: priceEstimated ?? false
        )
    }

    private func mapLink() -> LinkKind {
        if linkKind == "own" { return .own(label: ownLabel ?? "Link") }
        return .reelie(rate: rate ?? 8)
    }

    static func mapEvidence(_ s: String) -> Evidence {
        switch s {
        case "spoken", "description": return .spoken
        case "both": return .both
        default: return .shown          // "shown", "on-screen-text"
        }
    }
}
