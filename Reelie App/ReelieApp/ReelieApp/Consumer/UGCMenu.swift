import SwiftUI

/// Report / block affordance required for user-generated content (App Store 1.2).
/// Drops an ellipsis menu onto any content surface — a reel, a routine, a creator.
/// Reporting is best-effort to the backend; blocking is device-local and hides the
/// creator's content immediately.
struct UGCMenu: View {
    @Environment(AppState.self) private var app
    let kind: String        // "page" (routine) or "creator"
    let ref: String         // "handle/slug" for a page, "handle" for a creator
    let handle: String      // creator to block
    var tint: Color = Palette.ink
    var onBlock: (() -> Void)? = nil   // e.g. pop the screen after blocking

    @State private var showReport = false
    @State private var confirmBlock = false
    @State private var reported = false

    var body: some View {
        Menu {
            Button { showReport = true } label: { Label("Report", systemImage: "flag") }
            Button(role: .destructive) { confirmBlock = true } label: {
                Label("Block @\(handle)", systemImage: "hand.raised")
            }
        } label: {
            Image(systemName: "ellipsis")
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(tint)
                .frame(width: 34, height: 34)
                .contentShape(Rectangle())
        }
        // Report → pick a reason.
        .confirmationDialog("Report this \(kind == "creator" ? "creator" : "routine")?",
                            isPresented: $showReport, titleVisibility: .visible) {
            ForEach(ReportReason.allCases) { r in
                Button(r.label) {
                    Task { await app.report(kind: kind, ref: ref, reason: r.rawValue) }
                    reported = true
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Our team reviews every report and removes content that breaks the rules.")
        }
        // Block → confirm, then hide their content.
        .confirmationDialog("Block @\(handle)?", isPresented: $confirmBlock, titleVisibility: .visible) {
            Button("Block", role: .destructive) {
                app.blockCreator(handle)
                onBlock?()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("You won't see @\(handle)'s videos or routines. You can undo this in Settings.")
        }
        .alert("Thanks for reporting", isPresented: $reported) {
            Button("OK", role: .cancel) {}
        } message: {
            Text("Our team will take a look.")
        }
    }
}

enum ReportReason: String, CaseIterable, Identifiable {
    case offensive, spam, nudity, violence, hate, ip, other
    var id: String { rawValue }
    var label: String {
        switch self {
        case .offensive: return "Offensive or inappropriate"
        case .spam:      return "Spam or scam"
        case .nudity:    return "Nudity or sexual content"
        case .violence:  return "Violence"
        case .hate:      return "Hate speech"
        case .ip:        return "Copyright / intellectual property"
        case .other:     return "Something else"
        }
    }
}
