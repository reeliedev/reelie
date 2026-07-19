import Foundation

// Loads generated pages emitted by the page-generator backend. Reads bundled
// sample JSON first (so the app demos standalone), then any pages dropped into
// the app's Documents directory (e.g. synced from the backend at runtime).

enum GeneratedPageStore {

    /// All generated pages available to the app, bundle + Documents, with any
    /// creator text edits (OverridesStore) re-applied.
    static func loadAll() -> [GeneratedPage] {
        var pages: [GeneratedPage] = []
        pages.append(contentsOf: bundledPages())
        pages.append(contentsOf: documentsPages())
        let overrides = OverridesStore.loadAll()
        return pages.map { OverridesStore.apply(to: $0, all: overrides) }
    }

    // Bundled samples: every "*generated-page*.json" copied into the app bundle.
    private static func bundledPages() -> [GeneratedPage] {
        let urls = Bundle.main.urls(forResourcesWithExtension: "json", subdirectory: nil) ?? []
        return urls
            .filter { $0.lastPathComponent.contains("generated-page") }
            .compactMap(decode)
    }

    // Runtime pages: <Documents>/generated-pages/*.json
    private static func documentsPages() -> [GeneratedPage] {
        guard let docs = FileManager.default.urls(for: .documentDirectory,
                                                  in: .userDomainMask).first else { return [] }
        let dir = docs.appendingPathComponent("generated-pages", isDirectory: true)
        guard let urls = try? FileManager.default.contentsOfDirectory(
            at: dir, includingPropertiesForKeys: nil) else { return [] }
        return urls.filter { $0.pathExtension == "json" }.compactMap(decode)
    }

    private static func decode(_ url: URL) -> GeneratedPage? {
        guard let data = try? Data(contentsOf: url),
              let dto = try? JSONDecoder().decode(GeneratedPageDTO.self, from: data)
        else { return nil }
        return dto.toGeneratedPage()
    }
}
