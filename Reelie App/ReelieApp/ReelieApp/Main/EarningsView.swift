import SwiftUI

/// Screen 12 — Earnings tab. Uses live backend earnings when the account is a
/// creator and the API is reachable; otherwise local mock rollups.
struct EarningsView: View {
    @Environment(AppState.self) private var app
    @State private var period: Period = .month

    enum Period: String, CaseIterable {
        case week = "This week"
        case month = "This month"
        case lifetime = "Lifetime"
        func value(_ app: AppState) -> Double {
            switch self {
            case .week: return app.earningsThisWeek
            case .month: return app.earningsThisMonth
            case .lifetime: return app.lifetimeEarnings
            }
        }
    }

    // Prefer the live summary; fall back to local mock values.
    private var s: EarningsSummary? { app.earningsSummary }
    private var readyToPayout: String { s.map { Money.string($0.readyToPayout) } ?? app.readyToPayout }
    private var pending: String { s.map { Money.string($0.pending) } ?? app.pending }
    private var ready: String { s.map { Money.string($0.ready) } ?? app.ready }
    private var paidSoFar: String { s.map { Money.string($0.paidSoFar) } ?? app.paidSoFar }

    private func periodValue() -> String {
        if let s {
            switch period {
            case .week: return Money.string(s.thisWeek)
            case .month: return Money.string(s.thisMonth)
            case .lifetime: return Money.string(s.lifetime)
            }
        }
        return Money.string(period.value(app))
    }

    private var byPage: [(slug: String, title: String, total: Double)] {
        if let s { return s.byPage.map { ($0.slug, $0.title, $0.total) } }
        return app.earningsByPage
    }

    private var recentRows: [(emoji: String, name: String, page: String, amount: String, isReady: Bool)] {
        if let s { return s.recentSales.map { ($0.emoji, $0.name, $0.page, Money.string($0.value), $0.state == "ready") } }
        return app.sales.map { ($0.emoji, $0.name, $0.page, $0.amount, $0.state == .ready) }
    }

    var body: some View {
        @Bindable var app = app
        VStack(spacing: 0) {
            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {
                    // Balance.
                    VStack(spacing: 0) {
                        Text("READY TO PAY OUT")
                            .font(ReelieFont.ui(11.5, weight: .bold)).tracking(1.5).foregroundStyle(Palette.faint)
                        Text(readyToPayout).displayStyle(52).padding(.top, 8)
                        HStack(spacing: 6) {
                            Circle().fill(Palette.sun).frame(width: 7, height: 7)
                            Text("Pays out Aug 1 · to your bank")
                                .font(ReelieFont.ui(12.5, weight: .bold)).foregroundStyle(Palette.ink)
                        }
                        .padding(.horizontal, 14).padding(.vertical, 7)
                        .background(Palette.soft, in: Capsule())
                        .padding(.top, 10)

                        if let p = app.payoutsSummary, p.ready > 0 {
                            Button {
                                cashingOut = true
                                Task { await app.cashOut(); cashingOut = false }
                            } label: {
                                Text(cashingOut ? "…" : "Cash out \(Money.string(p.ready))")
                                    .font(ReelieFont.ui(15, weight: .bold)).foregroundStyle(Palette.ink)
                                    .frame(maxWidth: .infinity).frame(height: 48)
                                    .background(Palette.sun, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                            }
                            .buttonStyle(PressableStyle())
                            .padding(.top, 14).padding(.horizontal, 40)
                        }
                    }
                    .padding(.top, 10)

                    // State trio.
                    HStack(spacing: 10) {
                        state(pending, "PENDING")
                        state(ready, "READY")
                        state(paidSoFar, "PAID SO FAR")
                    }
                    .padding(.top, 20)

                    (
                        Text("Pending").foregroundStyle(Palette.grey).fontWeight(.medium)
                        + Text(" means the retailer is confirming the order — it moves to ")
                        + Text("Ready").foregroundStyle(Palette.grey).fontWeight(.medium)
                        + Text(" once returns can't happen anymore, usually 30–60 days.")
                    )
                    .font(ReelieFont.ui(11.5)).foregroundStyle(Palette.faint)
                    .multilineTextAlignment(.center).lineSpacing(1)
                    .padding(.horizontal, 6).padding(.top, 10)

                    // Period breakdown.
                    periodBlock.padding(.top, 24)

                    // Earnings by page (per-video rollup).
                    if !byPage.isEmpty {
                        SectionLabel(text: "EARNINGS BY PAGE").padding(.top, 24).padding(.bottom, 10)
                        VStack(spacing: 0) {
                            ForEach(byPage, id: \.slug) { row in
                                HStack(spacing: 12) {
                                    Text(row.title).font(ReelieFont.ui(13.5, weight: .medium))
                                        .foregroundStyle(Palette.ink).lineLimit(1)
                                    Spacer(minLength: 8)
                                    Text(Money.string(row.total))
                                        .font(ReelieFont.ui(13.5, weight: .bold)).foregroundStyle(Palette.ink)
                                }
                                .padding(.vertical, 12)
                                if row.slug != byPage.last?.slug {
                                    Rectangle().fill(Color(hex: 0xF5F5F5)).frame(height: 1.5)
                                }
                            }
                        }
                        .padding(.horizontal, 15)
                        .hairlineCard(cornerRadius: 16)
                    }

                    if let p = app.payoutsSummary, !p.history.isEmpty {
                        SectionLabel(text: "PAYOUTS").padding(.top, 24).padding(.bottom, 10)
                        VStack(spacing: 0) {
                            ForEach(p.history) { po in
                                HStack(spacing: 12) {
                                    Text("🏦").font(.system(size: 16))
                                    Text(String(po.date.prefix(10)))
                                        .font(ReelieFont.ui(13, weight: .medium)).foregroundStyle(Palette.ink)
                                    Spacer()
                                    Text(Money.string(po.amount)).font(ReelieFont.ui(13.5, weight: .bold)).foregroundStyle(Palette.ink)
                                    Text(po.status.uppercased())
                                        .font(ReelieFont.ui(10, weight: .bold)).tracking(0.4).foregroundStyle(Palette.ok)
                                }
                                .padding(.vertical, 11)
                                if po.id != p.history.last?.id {
                                    Rectangle().fill(Color(hex: 0xF5F5F5)).frame(height: 1.5)
                                }
                            }
                        }
                        .padding(.horizontal, 15).hairlineCard(cornerRadius: 16)
                    }

                    SectionLabel(text: "RECENT SALES").padding(.top, 24).padding(.bottom, 4)
                    ForEach(Array(recentRows.enumerated()), id: \.offset) { _, r in
                        SaleRow(emoji: r.emoji, name: r.name, page: r.page, amount: r.amount, isReady: r.isReady)
                        Rectangle().fill(Color(hex: 0xF5F5F5)).frame(height: 1.5)
                    }

                    // Payout method.
                    HStack(spacing: 12) {
                        Text("🏦").font(.system(size: 18))
                        VStack(alignment: .leading, spacing: 1) {
                            Text("Payouts to •••• 4821").font(ReelieFont.ui(13.5, weight: .bold)).foregroundStyle(Palette.ink)
                            Text("Monthly, on the 1st · via Stripe").font(ReelieFont.ui(11.5)).foregroundStyle(Palette.grey)
                        }
                        Spacer()
                        Image(systemName: "chevron.right").font(.system(size: 14, weight: .bold)).foregroundStyle(Color(hex: 0xD5D5D5))
                    }
                    .padding(.horizontal, 15).padding(.vertical, 13)
                    .hairlineCard(cornerRadius: 16)
                    .padding(.top, 20)
                }
                .padding(.horizontal, 28)
                .padding(.top, 14).padding(.bottom, 16)
            }

            ReelieTabBar(selection: $app.selectedTab, showsCreator: app.isCreator)
        }
        .background(.white)
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .task { await app.loadEarnings(); await app.loadPayouts() }
    }

    @State private var cashingOut = false

    private var periodBlock: some View {
        VStack(spacing: 14) {
            HStack(spacing: 8) {
                ForEach(Period.allCases, id: \.self) { p in
                    Button { period = p } label: {
                        Text(p.rawValue)
                            .font(ReelieFont.ui(12.5, weight: .bold))
                            .foregroundStyle(period == p ? Palette.ink : Palette.grey)
                            .frame(maxWidth: .infinity).padding(.vertical, 9)
                            .background(period == p ? Palette.sun : Palette.soft,
                                        in: RoundedRectangle(cornerRadius: 11, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
            }
            Text(periodValue()).displayStyle(40)
            if let s {
                Text("\(s.clicks) shop clicks · \(s.conversions) sales")
                    .font(ReelieFont.ui(12)).foregroundStyle(Palette.grey)
            }
        }
    }

    private func state(_ num: String, _ label: String) -> some View {
        VStack(spacing: 3) {
            Text(num).font(ReelieFont.ui(16, weight: .bold)).foregroundStyle(Palette.ink)
            Text(label).font(ReelieFont.ui(10.5, weight: .bold)).tracking(0.6).foregroundStyle(Palette.faint)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12).padding(.horizontal, 8)
        .hairlineCard(cornerRadius: 16)
    }
}

private struct SaleRow: View {
    let emoji: String
    let name: String
    let page: String
    let amount: String
    let isReady: Bool
    var body: some View {
        HStack(spacing: 12) {
            EmojiThumb(emoji: emoji, size: 40, corner: 11)
            VStack(alignment: .leading, spacing: 2) {
                Text(name).font(ReelieFont.ui(13.5, weight: .medium)).foregroundStyle(Palette.ink).lineLimit(1)
                Text(page).font(ReelieFont.ui(11.5)).foregroundStyle(Palette.grey).lineLimit(1)
            }
            Spacer(minLength: 4)
            VStack(alignment: .trailing, spacing: 3) {
                Text(amount).font(ReelieFont.ui(13.5, weight: .bold)).foregroundStyle(Palette.ink)
                HStack(spacing: 4) {
                    if isReady { Circle().fill(Palette.sun).frame(width: 6, height: 6) }
                    Text(isReady ? "READY" : "PENDING")
                        .font(ReelieFont.ui(10, weight: .bold)).tracking(0.4)
                        .foregroundStyle(isReady ? Palette.ink : Palette.faint)
                }
            }
        }
        .padding(.vertical, 11)
    }
}

#Preview {
    NavigationStack { EarningsView() }
        .environment({ let a = AppState(); a.onboardingComplete = true; a.currentUser.role = .both; a.selectedTab = .earnings; return a }())
}
