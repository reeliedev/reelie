import SwiftUI

// MARK: - Social platforms

enum Platform: String, Identifiable {
    case youtube = "YouTube"
    case instagram = "Instagram"
    case tiktok = "TikTok"

    var id: String { rawValue }

    /// SF Symbol stand-in for the brand mark.
    var symbol: String {
        switch self {
        case .youtube:   return "play.rectangle.fill"
        case .instagram: return "camera.fill"
        case .tiktok:    return "music.note"
        }
    }

    var tint: Color {
        switch self {
        case .youtube:   return Color(hex: 0xFF0000)
        case .instagram: return Color(hex: 0xD6249F)
        case .tiktok:    return Palette.ink
        }
    }

    /// Identifier the backend uses for OAuth (`/me/connect/{key}`). nil = not yet supported.
    var connectKey: String? {
        switch self {
        case .youtube:   return "youtube"
        case .instagram: return "instagram"
        case .tiktok:    return nil
        }
    }
}

enum SocialStatus {
    case connected(handle: String)
    case disconnected
    case expired
    case comingSoon
}

struct SocialAccount: Identifiable {
    let id = UUID()
    let platform: Platform
    var status: SocialStatus
}

// MARK: - Videos (source clips to build a page from)

enum VideoSource: String {
    case reel = "REEL"
    case youtube = "YOUTUBE"
}

struct SourceVideo: Identifiable {
    let id = UUID()
    let title: String
    let meta: String          // "2w ago · 48k views"
    let source: VideoSource
    let gradient: [Color]
    var hasPage: Bool = false
}

// MARK: - Products on a page

enum LinkKind: Equatable {
    case reelie(rate: Int)    // "Reelie link · earns 8%"
    case own(label: String)   // "Your link · LTK"
}

enum ProductStatus {
    case ready          // confirmed, tap to edit
    case needsReview    // shown-only, thumbs up/down
}

enum Evidence: String {
    case spoken = "Spoken"
    case shown = "Shown"
    case both = "Both"
}

struct Product: Identifiable {
    let id = UUID()
    var serverId: String? = nil   // backend product id (for API edits)
    var brand: String
    var name: String
    var emoji: String
    var evidence: Evidence
    var timestamp: String        // "0:12"
    var note: String? = nil      // "which shade?" / "are we right?"
    var guide: String? = nil     // 1-3 sentence narration (editable on generated pages)
    var link: LinkKind
    var status: ProductStatus = .ready

    // page-detail metrics (optional)
    var earned: String? = nil
    var clicks: Int? = nil

    // Pricing (populated for auto-generated pages; nil for hand-authored sample data).
    var priceDisplay: String? = nil   // "$18"
    var retailer: String? = nil       // "Sephora"
    var priceEstimated: Bool = false  // true = approximate LLM/heuristic estimate
}

// MARK: - Pages

enum PageStatus: Equatable {
    case needsReview     // "NEEDS YOUR OK"
    case processing      // "WORKING ON IT"
    case live            // "LIVE"
    case archived        // "ARCHIVED" — hidden from the public site
}

struct Page: Identifiable {
    let id = UUID()
    var title: String
    var emoji: String
    var slug: String             // "morning-skincare"
    var status: PageStatus
    var meta: String             // context line under the title
    var views: String = "0"
    var shopClicks: String = "0"
    var earned: String = "$0.00"
    var products: [Product] = []
}

// MARK: - Earnings

enum SaleState: String {
    case pending = "PENDING"
    case ready = "READY"
}

struct Sale: Identifiable {
    let id = UUID()
    let name: String
    let emoji: String
    let page: String             // "K-beauty night routine · Ulta"
    let value: Double            // numeric commission, for rollups
    let state: SaleState
    var date: Date = Date()      // when the sale landed
    var pageSlug: String = ""    // which page it's attributed to

    /// "$3.20" display, derived from `value`.
    var amount: String { Money.string(value) }
}

// MARK: - Currency formatting

enum Money {
    static func string(_ value: Double) -> String {
        if abs(value - value.rounded()) < 0.005 {
            return "$\(Int(value.rounded()))"
        }
        return String(format: "$%.2f", value)
    }
}

// MARK: - Identity (one account, additive role)

enum Role: Equatable {
    case viewer     // browses creators, saves favorites (default)
    case creator    // also has the creator studio
    case both

    var isCreator: Bool { self == .creator || self == .both }

    static func from(_ s: String) -> Role {
        switch s {
        case "creator": return .creator
        case "both": return .both
        default: return .viewer
        }
    }
}

struct User {
    var id = UUID()
    var email: String = ""
    var displayName: String
    var handle: String
    var avatarGradient: [Color]
    var role: Role = .viewer
}

// MARK: - Creators (the browsable corpus)

struct Creator: Identifiable {
    var id: String { handle }
    let displayName: String
    let handle: String
    let avatarGradient: [Color]
    let platforms: [String]
    var pageIDs: [UUID] = []

    var platformLine: String { platforms.joined(separator: " & ") }
}
