import Foundation

// Persists creator text edits to a generated page (title / intro / disclosure /
// custom link / per-product name·note·narration) so they survive relaunch
// WITHOUT re-running extraction. Applied over the decoded page on load — mirrors
// how the backend's `overrides/<handle>-<slug>.json` layer re-renders edits.

struct ProductOverride: Codable {
    var name: String
    var note: String?
    var guide: String?
}

struct PageOverride: Codable {
    var title: String
    var intro: String
    var disclosure: String
    var customSlug: String?
    var products: [ProductOverride]   // aligned to the page's products by index
}

enum OverridesStore {
    private static var fileURL: URL? {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first?
            .appendingPathComponent("page-overrides.json")
    }

    static func loadAll() -> [String: PageOverride] {
        guard let url = fileURL, let data = try? Data(contentsOf: url),
              let dict = try? JSONDecoder().decode([String: PageOverride].self, from: data)
        else { return [:] }
        return dict
    }

    static func save(_ page: GeneratedPage) {
        guard let url = fileURL else { return }
        var dict = loadAll()
        dict[page.key] = PageOverride(
            title: page.title, intro: page.intro, disclosure: page.disclosure,
            customSlug: page.customSlug,
            products: page.products.map { ProductOverride(name: $0.name, note: $0.note, guide: $0.guide) }
        )
        if let data = try? JSONEncoder().encode(dict) {
            try? data.write(to: url)
        }
    }

    /// Merge any stored edits onto a freshly-decoded page.
    static func apply(to page: GeneratedPage, all: [String: PageOverride]) -> GeneratedPage {
        guard let o = all[page.key] else { return page }
        var p = page
        p.title = o.title
        p.intro = o.intro
        p.disclosure = o.disclosure
        p.customSlug = o.customSlug
        for i in p.products.indices where i < o.products.count {
            p.products[i].name = o.products[i].name
            p.products[i].note = o.products[i].note
            p.products[i].guide = o.products[i].guide
        }
        return p
    }
}
