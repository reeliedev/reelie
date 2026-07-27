import SwiftUI

/// Consumer search over creators + routines (GET /search). Reached from the
/// Discover feed's search button.
struct SearchView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss

    @State private var query = ""
    @State private var creators: [Creator] = []
    @State private var routines: [GeneratedPage] = []
    @State private var searching = false
    @State private var didSearch = false
    @State private var searchTask: Task<Void, Never>?
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 0) {
            searchBar
            content
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .onAppear { focused = true }
        .onChange(of: query) { _, _ in scheduleSearch() }
    }

    private var searchBar: some View {
        HStack(spacing: 12) {
            BackButton { dismiss() }
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass").font(.system(size: 15)).foregroundStyle(Palette.grey)
                TextField("Search creators, brands, products…", text: $query)
                    .font(ReelieFont.ui(15)).foregroundStyle(Palette.ink)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                    .focused($focused).submitLabel(.search)
                if !query.isEmpty {
                    Button { query = "" } label: {
                        Image(systemName: "xmark.circle.fill").font(.system(size: 15)).foregroundStyle(Palette.faint)
                    }.buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 12).padding(.vertical, 11)
            .hairlineCard(cornerRadius: 12, color: focused ? Palette.ink : Palette.line)
        }
        .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 8)
    }

    @ViewBuilder private var content: some View {
        if searching && creators.isEmpty && routines.isEmpty {
            Spacer(); ProgressView().tint(Palette.ink); Spacer()
        } else if didSearch && creators.isEmpty && routines.isEmpty {
            emptyState("💭", "No results", "Try a creator name, a brand, or a product.")
        } else if !didSearch {
            emptyState("🔍", "Search Reelie", "Find creators, routines, and the products they use.")
        } else {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 0) {
                    if !creators.isEmpty {
                        SectionLabel(text: "CREATORS").padding(.top, 12).padding(.bottom, 12)
                        ForEach(creators) { creatorRow($0) }
                    }
                    if !routines.isEmpty {
                        SectionLabel(text: "ROUTINES").padding(.top, 18).padding(.bottom, 12)
                        ForEach(routines) { RoutineCard(page: $0) }
                    }
                }
                .padding(.horizontal, 28).padding(.bottom, 24)
            }
        }
    }

    private func creatorRow(_ c: Creator) -> some View {
        NavigationLink(value: ConsumerRoute.creatorProfile(handle: c.handle)) {
            HStack(spacing: 13) {
                CreatorAvatar(gradient: c.avatarGradient, size: 46)
                VStack(alignment: .leading, spacing: 2) {
                    Text(c.displayName).font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.ink)
                    Text("@\(c.handle)").font(ReelieFont.ui(12.5)).foregroundStyle(Palette.grey)
                }
                Spacer()
                Image(systemName: "chevron.right").font(.system(size: 15, weight: .bold)).foregroundStyle(Color(hex: 0xD5D5D5))
            }
            .padding(14).hairlineCard().padding(.bottom, 10)
        }
        .buttonStyle(.plain)
    }

    private func emptyState(_ emoji: String, _ title: String, _ subtitle: String) -> some View {
        VStack(spacing: 0) {
            Spacer()
            Text(emoji).font(.system(size: 40))
            Text(title).displayStyle(22).padding(.top, 12)
            Text(subtitle).font(ReelieFont.ui(14)).foregroundStyle(Palette.grey)
                .multilineTextAlignment(.center).frame(maxWidth: 260).lineSpacing(2).padding(.top, 8)
            Spacer(); Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    /// Debounced search: 300ms after the last keystroke, min 2 chars.
    private func scheduleSearch() {
        searchTask?.cancel()
        let q = query.trimmingCharacters(in: .whitespaces)
        guard q.count >= 2 else { creators = []; routines = []; searching = false; didSearch = false; return }
        searching = true
        searchTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 300_000_000)
            if Task.isCancelled { return }
            let r = await app.search(q)
            if Task.isCancelled { return }
            creators = r.creators; routines = r.routines
            searching = false; didSearch = true
        }
    }
}

#Preview {
    NavigationStack { SearchView() }
        .environment({ let a = AppState(); a.onboardingComplete = true; return a }())
}
