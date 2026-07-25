import Foundation

// MARK: - Generated page model
//
// A page produced by the page-generator backend ("Reelie App/page-generator").
// It's kept distinct from the hand-authored `Page` because a generated page
// carries web-publishing context the app screens need — the creator handle,
// the public URL, and a creator-editable custom link. Product rows reuse the
// existing `Product` model (now with price fields).

struct GeneratedPage: Identifiable {
    // Identity is derived deterministically from the page's stable key ("handle/slug")
    // so that reloading pages (loadMyPages decodes fresh DTOs) keeps the SAME id.
    // A random per-decode UUID would change every refresh, invalidating any
    // navigation value captured mid-interaction — that's what made the Preview
    // button need a second tap.
    var id: UUID { GeneratedPage.stableID(for: key) }
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
    var published: Bool = false      // live on the web vs draft awaiting review
    var faqs: [RoutineFAQ] = []      // auto-generated + custom Q&A (same as web)
    var totals: RoutineTotals? = nil // "shop the whole routine" kit

    /// The slug actually used in the public URL — the creator's custom link wins.
    var pathSlug: String {
        if let c = customSlug?.trimmingCharacters(in: .whitespaces), !c.isEmpty { return c }
        return slug
    }

    /// Display URL for the public page (matches the generator's config domain).
    var publicURL: String { "reelie.io/\(handle)/\(pathSlug)" }

    var platformLine: String { platforms.joined(separator: " & ") }

    /// Stable identity across launches (favorites, overrides) — not the random UUID.
    var key: String { "\(handle)/\(slug)" }

    /// A deterministic UUID for a page key, so the same page always has the same
    /// `id` regardless of when/how often it's decoded. FNV-1a over the key bytes,
    /// run in two directions to fill all 16 UUID bytes.
    static func stableID(for key: String) -> UUID {
        var h1: UInt64 = 0xcbf29ce484222325
        var h2: UInt64 = 0x84222325cbf29ce4
        for b in key.utf8 {
            h1 = (h1 ^ UInt64(b)) &* 0x100000001b3
            h2 = (h2 &+ UInt64(b)) &* 0x100000001b3
        }
        func byte(_ v: UInt64, _ i: Int) -> UInt8 { UInt8((v >> (UInt64(i) * 8)) & 0xff) }
        return UUID(uuid: (
            byte(h1, 0), byte(h1, 1), byte(h1, 2), byte(h1, 3),
            byte(h1, 4), byte(h1, 5), byte(h1, 6), byte(h1, 7),
            byte(h2, 0), byte(h2, 1), byte(h2, 2), byte(h2, 3),
            byte(h2, 4), byte(h2, 5), byte(h2, 6), byte(h2, 7)
        ))
    }
}

// MARK: - Routine FAQ + totals (match the web's Q&A block + kit)

struct RoutineFAQ: Identifiable, Equatable {
    let id = UUID(); var q: String; var a: String
}
struct RoutineTotals: Equatable {
    var count: Int
    var totalDisplay: String   // "$36"
    var rangeDisplay: String   // "$12–$24"
    var anyEstimated: Bool
    var retailers: [String]
}

// MARK: - Decodable DTO (mirrors render/app_json.py output, camelCase)

struct GeneratedPageDTO: Decodable {
    struct FAQDTO: Decodable { let q: String; let a: String }
    struct TotalsDTO: Decodable {
        let count: Int; let totalDisplay: String; let rangeDisplay: String
        let anyEstimated: Bool; let retailers: [String]
    }
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
    let published: Bool?
    let products: [GeneratedProductDTO]
    let faqs: [FAQDTO]?
    let totals: TotalsDTO?

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
        let clipUrl: String?
        let clipPoster: String?
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
            archived: archived ?? false,
            published: published ?? false,
            faqs: (faqs ?? []).map { RoutineFAQ(q: $0.q, a: $0.a) },
            totals: totals.map {
                RoutineTotals(count: $0.count, totalDisplay: $0.totalDisplay,
                              rangeDisplay: $0.rangeDisplay, anyEstimated: $0.anyEstimated,
                              retailers: $0.retailers)
            }
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
            variant: variant,
            evidence: Self.mapEvidence(evidence),
            timestamp: timestamp,
            note: note,
            guide: guide,
            clipUrl: clipUrl,
            clipPoster: clipPoster,
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
