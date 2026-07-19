import Foundation

// Persists consumer favorites (saved routines + saved creators) across launches.
// Simple UserDefaults-backed string sets — no backend. Keys are stable
// ("handle/slug" for pages, "handle" for creators).

enum FavoritesStore {
    private static let pagesKey = "reelie.favorites.pages"
    private static let creatorsKey = "reelie.favorites.creators"

    static func loadPages() -> Set<String> {
        Set(UserDefaults.standard.stringArray(forKey: pagesKey) ?? [])
    }
    static func savePages(_ set: Set<String>) {
        UserDefaults.standard.set(Array(set), forKey: pagesKey)
    }
    static func loadCreators() -> Set<String> {
        Set(UserDefaults.standard.stringArray(forKey: creatorsKey) ?? [])
    }
    static func saveCreators(_ set: Set<String>) {
        UserDefaults.standard.set(Array(set), forKey: creatorsKey)
    }
}
