import SwiftUI

// MARK: - Seeded browsable corpus
//
// A mock, multi-creator catalogue so the consumer surface (Discover / creator
// profiles / recommendations) has real signal. Brands are deliberately shared
// across creators so "similar creators" and "creators using this product"
// return non-empty results. Replace with a real backend later.

enum Catalog {

    /// Compact product builder for seed routines.
    private static func p(_ brand: String, _ name: String, _ emoji: String,
                          _ price: String, _ retailer: String, rate: Int = 8) -> Product {
        Product(brand: brand, name: name, emoji: emoji, evidence: .both,
                timestamp: "0:00", link: .reelie(rate: rate),
                priceDisplay: price, retailer: retailer)
    }

    private static func page(_ handle: String, _ creator: String, _ platforms: [String],
                             _ title: String, _ emoji: String, _ slug: String,
                             _ products: [Product]) -> GeneratedPage {
        GeneratedPage(
            title: title, emoji: emoji, slug: slug, customSlug: nil,
            meta: "\(products.count) products",
            handle: handle, creatorName: creator, platforms: platforms,
            disclosure: "Some links earn \(creator.split(separator: " ").first.map(String.init) ?? creator) a commission — it never changes what you pay.",
            products: products
        )
    }

    // Avatar gradients per creator.
    static let creators: [Creator] = [
        Creator(displayName: "Jess Tan", handle: "glowbyjess",
                avatarGradient: [Color(hex: 0xE8E4DA), Color(hex: 0xD8D2C4)],
                platforms: ["YouTube", "Instagram"]),
        Creator(displayName: "Maria Lopez", handle: "mariskincare",
                avatarGradient: [Color(hex: 0xDCE4E8), Color(hex: 0xC4D2D8)],
                platforms: ["Instagram", "TikTok"]),
        Creator(displayName: "Priya Shah", handle: "thefacefiles",
                avatarGradient: [Color(hex: 0xE8E0DC), Color(hex: 0xD8CFC4)],
                platforms: ["YouTube"]),
        Creator(displayName: "Kay Kim", handle: "kbeautykay",
                avatarGradient: [Color(hex: 0xE4E8DC), Color(hex: 0xD2D8C4)],
                platforms: ["TikTok"]),
        Creator(displayName: "Amira Hassan", handle: "everydayamira",
                avatarGradient: [Color(hex: 0xE8DCE4), Color(hex: 0xD8C4D2)],
                platforms: ["Instagram", "YouTube"]),
    ]

    static let routines: [GeneratedPage] = [
        // glowbyjess
        page("glowbyjess", "Jess Tan", ["YouTube", "Instagram"],
             "My everyday routine", "💄", "everyday-routine", [
                p("Rare Beauty", "Soft Pinch Liquid Blush", "🌸", "$23", "Sephora", rate: 7),
                p("Armani Beauty", "Luminous Silk Concealer", "🪞", "$34", "Sephora"),
                p("Laneige", "Lip Sleeping Mask", "💤", "$24", "Sephora", rate: 6),
                p("Charlotte Tilbury", "Flawless Filter", "✨", "$49", "Sephora"),
             ]),
        page("glowbyjess", "Jess Tan", ["YouTube", "Instagram"],
             "Summer glow", "🌞", "summer-glow", [
                p("Beauty of Joseon", "Relief Sun SPF 50+", "🌞", "$18", "Amazon"),
                p("Iconic London", "Illuminator Drops", "🌟", "$36", "Sephora", rate: 7),
                p("Johnson's", "Baby Oil", "💧", "$7", "Walmart", rate: 6),
             ]),
        // mariskincare
        page("mariskincare", "Maria Lopez", ["Instagram", "TikTok"],
             "My 8-step night routine", "🌙", "night-routine", [
                p("Banila Co", "Clean It Zero Balm", "🧼", "$20", "Amazon", rate: 7),
                p("COSRX", "Snail 96 Mucin Essence", "💧", "$25", "Amazon"),
                p("Beauty of Joseon", "Glow Deep Serum", "🌙", "$17", "YesStyle"),
                p("Laneige", "Water Sleeping Mask", "💤", "$29", "Sephora", rate: 6),
                p("Anua", "Heartleaf 77% Toner", "🧴", "$22", "Amazon"),
             ]),
        page("mariskincare", "Maria Lopez", ["Instagram", "TikTok"],
             "Barrier repair basics", "🧴", "barrier-repair", [
                p("CeraVe", "Moisturizing Cream", "🧴", "$16", "Ulta", rate: 6),
                p("COSRX", "Snail 96 Mucin Essence", "💧", "$25", "Amazon"),
                p("Beauty of Joseon", "Relief Sun SPF 50+", "🌞", "$18", "Amazon"),
             ]),
        // thefacefiles
        page("thefacefiles", "Priya Shah", ["YouTube"],
             "Soft glam in 10 minutes", "✨", "soft-glam", [
                p("Rare Beauty", "Soft Pinch Liquid Blush", "🌸", "$23", "Sephora", rate: 7),
                p("Armani Beauty", "Luminous Silk Concealer", "🪞", "$34", "Sephora"),
                p("Charlotte Tilbury", "Flawless Filter", "✨", "$49", "Sephora"),
                p("Laneige", "Lip Sleeping Mask", "💤", "$24", "Sephora", rate: 6),
             ]),
        // kbeautykay
        page("kbeautykay", "Kay Kim", ["TikTok"],
             "K-beauty glass skin", "🧴", "glass-skin", [
                p("COSRX", "Snail 96 Mucin Essence", "💧", "$25", "Amazon"),
                p("Anua", "Heartleaf 77% Toner", "🧴", "$22", "Amazon"),
                p("Beauty of Joseon", "Glow Deep Serum", "🌙", "$17", "YesStyle"),
                p("Banila Co", "Clean It Zero Balm", "🧼", "$20", "Amazon", rate: 7),
             ]),
        page("kbeautykay", "Kay Kim", ["TikTok"],
             "My cleansing routine", "🧼", "cleansing", [
                p("Banila Co", "Clean It Zero Balm", "🧼", "$20", "Amazon", rate: 7),
                p("CeraVe", "Foaming Facial Cleanser", "🧼", "$14", "Ulta", rate: 6),
                p("Anua", "Heartleaf 77% Toner", "🧴", "$22", "Amazon"),
             ]),
        // everydayamira
        page("everydayamira", "Amira Hassan", ["Instagram", "YouTube"],
             "No-makeup makeup", "💄", "no-makeup", [
                p("The Ordinary", "Niacinamide 10% + Zinc", "💧", "$6", "Ulta", rate: 6),
                p("CeraVe", "Moisturizing Cream", "🧴", "$16", "Ulta", rate: 6),
                p("Maybelline", "Fit Me Foundation", "🪞", "$9", "Walmart", rate: 6),
                p("Beauty of Joseon", "Relief Sun SPF 50+", "🌞", "$18", "Amazon"),
             ]),
        page("everydayamira", "Amira Hassan", ["Instagram", "YouTube"],
             "Drugstore heroes", "🛍️", "drugstore-heroes", [
                p("CeraVe", "Foaming Facial Cleanser", "🧼", "$14", "Ulta", rate: 6),
                p("The Ordinary", "Niacinamide 10% + Zinc", "💧", "$6", "Ulta", rate: 6),
                p("Maybelline", "Fit Me Foundation", "🪞", "$9", "Walmart", rate: 6),
             ]),
    ]
}
