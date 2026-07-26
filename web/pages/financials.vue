<script setup lang="ts">
import { palette } from "~/composables/useChartTheme";
const tab = ref<"income" | "balance" | "cashflow" | "segments">("income");
const { data: income } = useApi<any>("/statements/income");
const { data: balance } = useApi<any>("/statements/balance");
const { data: cashflow } = useApi<any>("/statements/cashflow");
const { data: kpi } = useApi<any>("/kpis");

const isTotal = (l: any) => !l.indent;

// --- Segments (P&L) — IFRS 8 operating segments from SALE actuals ---
const segBy = ref<"campaign" | "brand" | "client" | "service">("campaign");
const { data: seg } = useApi<any>("/statements/segments", () => ({ by: segBy.value }));

const sortKey = ref("revenue");
const sortDir = ref(-1);
function sortBy(k: string) {
  if (sortKey.value === k) sortDir.value *= -1;
  else { sortKey.value = k; sortDir.value = -1; }
}
const segRows = computed(() => {
  const r = [...(seg.value?.rows || [])];
  return r.sort((a, b) => {
    const x = a[sortKey.value], y = b[sortKey.value];
    if (typeof x === "number" && typeof y === "number") return (x - y) * sortDir.value;
    return String(x ?? "").localeCompare(String(y ?? "")) * sortDir.value;
  });
});
// Grouped bar for the top segments by revenue — the table's shape at a glance.
const segChart = computed(() => {
  const top = [...segRows.value].sort((a, b) => b.revenue - a.revenue).slice(0, 10);
  return {
    labels: top.map((s) => s.segment),
    datasets: [
      { label: "Revenue", data: top.map((s) => s.revenue), backgroundColor: palette.green },
      { label: "Cost", data: top.map((s) => s.cost), backgroundColor: palette.grey },
      { label: "Op. Profit", data: top.map((s) => s.operating_profit), backgroundColor: palette.accent },
    ],
  };
});

// One bar chart per statement, colored by sign; balance shows the accounting equation.
const stmtChart = computed(() => {
  if (tab.value === "balance") {
    const b = balance.value; if (!b) return null;
    const assets = (b.assets || []).find((l: any) => /total assets/i.test(l.label))?.current ?? 0;
    const li = b.liabilities || [];
    const liTotal = li.find((l: any) => /^total/i.test(l.label))?.current
      ?? li.reduce((s: number, l: any) => s + (l.indent ? Number(l.current || 0) : 0), 0);
    const equity = b.equity?.current ?? 0;
    return {
      labels: ["Total Assets", "Liabilities + Equity"],
      datasets: [{ label: "IRR", data: [assets, liTotal + equity], backgroundColor: [palette.green, palette.mint] }],
    };
  }
  const stmt = tab.value === "income" ? income.value : cashflow.value;
  if (!stmt) return null;
  const lines = tab.value === "income" ? (stmt.lines || []).filter((l: any) => !l.indent) : (stmt.lines || []);
  return {
    labels: lines.map((l: any) => l.label),
    datasets: [{ label: "IRR", data: lines.map((l: any) => l.current),
      backgroundColor: lines.map((l: any) => (Number(l.current) >= 0 ? palette.green : palette.coral)) }],
  };
});
</script>

<template>
  <div>
    <h2>Financial Statements — IRR</h2>

    <div class="kpis">
      <KpiCard label="Revenue" icon="revenue" variant="dark" :value="irrC(kpi?.revenue)" :delta="kpi?.delta?.revenue" />
      <KpiCard label="Operational Profit" icon="profit" :value="irrC(kpi?.op_profit)" :tone="kpi?.op_profit >= 0 ? 'pos' : 'neg'" :delta="kpi?.delta?.op_profit" />
      <KpiCard label="AR Outstanding" icon="ar" :value="irrC(kpi?.ar_outstanding)" />
      <KpiCard label="AP Outstanding" icon="ap" :value="irrC(kpi?.ap_outstanding)" />
    </div>

    <div class="tabs">
      <button :class="{ active: tab === 'income' }" @click="tab = 'income'">Income Statement</button>
      <button :class="{ active: tab === 'balance' }" @click="tab = 'balance'">Balance Sheet</button>
      <button :class="{ active: tab === 'cashflow' }" @click="tab = 'cashflow'">Cash Flow</button>
      <button :class="{ active: tab === 'segments' }" @click="tab = 'segments'">Segments (P&amp;L)</button>
    </div>

    <div v-if="tab !== 'segments'" class="panel">
      <h3>{{ tab === 'income' ? 'Profit or Loss' : tab === 'balance' ? 'Assets vs Liabilities + Equity' : 'Cash Flow Bridge' }}</h3>
      <ChartBar v-if="stmtChart" :data="stmtChart" horizontal aria-label="Financial statement chart" />
      <div v-else class="empty">No statement data for this period.</div>
    </div>

    <!-- Income / Cash Flow: flat line list -->
    <div v-if="tab === 'income' || tab === 'cashflow'" class="panel">
      <template v-for="stmt in [tab === 'income' ? income : cashflow]" :key="tab">
        <table class="stmt">
          <thead><tr><th>{{ stmt?.title }} ({{ stmt?.standard }})</th><th class="n">Current</th><th class="n">Prior</th></tr></thead>
          <tbody>
            <tr v-for="l in stmt?.lines" :key="l.label" :class="{ total: isTotal(l) }">
              <td :class="{ indent: l.indent }">{{ l.label }}<span v-if="l.standard" class="muted"> · {{ l.standard }}</span></td>
              <td class="n">{{ irr(l.current) }}</td>
              <td class="n muted">{{ l.prior == null ? "—" : irr(l.prior) }}</td>
            </tr>
          </tbody>
        </table>
        <div class="note">
          {{ stmt?.title }} — {{ stmt?.standard }}. Prior-period comparative shown when a from/to range is set
          (compared against the same window one Jalali year earlier). Revenue disaggregated by service (IFRS 15);
          ageing (IFRS 7) on Receivables/Payables.
        </div>
      </template>
    </div>

    <!-- Segments (P&L): IFRS 8 operating segments -->
    <div v-if="tab === 'segments'" class="panel">
      <div class="tabs">
        <button v-for="b in ['campaign','brand','client','service']" :key="b"
                :class="{ active: segBy === b }" @click="segBy = b as any">{{ b[0].toUpperCase() + b.slice(1) }}</button>
        <GridExport :rows="segRows" :name="`segments-${segBy}`" title="Operating Segments"
                    style="margin-inline-start:auto" />
      </div>
      <ChartBar v-if="segRows.length" :data="segChart" class="mt-panel" :name="`segments-${segBy}`" aria-label="Revenue, cost and operating profit by segment" />
      <table class="stmt" style="margin-top: 12px">
        <thead><tr>
          <th @click="sortBy('segment')" style="cursor:pointer">Segment</th>
          <th class="n" @click="sortBy('revenue')" style="cursor:pointer">Revenue</th>
          <th class="n" @click="sortBy('cost')" style="cursor:pointer">Cost</th>
          <th class="n" @click="sortBy('gross_profit')" style="cursor:pointer">Gross Profit</th>
          <th class="n" @click="sortBy('operating_profit')" style="cursor:pointer">Op. Profit</th>
          <th class="n" @click="sortBy('margin')" style="cursor:pointer">Margin</th>
          <th class="n" @click="sortBy('orders')" style="cursor:pointer">Orders</th>
        </tr></thead>
        <tbody>
          <tr v-for="s in segRows" :key="s.segment">
            <td>{{ s.segment }}<span v-if="s.label && s.label !== s.segment" class="muted"> · {{ s.label }}</span></td>
            <td class="n">{{ irr(s.revenue) }}</td>
            <td class="n">{{ irr(s.cost) }}</td>
            <td class="n">{{ irr(s.gross_profit) }}</td>
            <td class="n">{{ irr(s.operating_profit) }}</td>
            <td class="n" :class="s.margin >= 0 ? 'pos' : 'neg'">{{ pct(s.margin) }}</td>
            <td class="n">{{ s.orders }}</td>
          </tr>
          <tr v-if="!segRows.length"><td colspan="7" class="table-empty">No segment data for this period.</td></tr>
        </tbody>
      </table>
      <div class="note">Operating segments — IFRS 8, from SALE actuals. Filter-aware; click a header to sort.</div>
    </div>

    <!-- Balance sheet: 3 sections -->
    <div v-if="tab === 'balance'" class="panel">
      <table class="stmt">
        <thead><tr><th>{{ balance?.title }} ({{ balance?.standard }})</th><th class="n">Amount</th><th class="n"></th></tr></thead>
        <tbody>
          <tr class="total"><td>Assets</td><td></td><td></td></tr>
          <tr v-for="l in balance?.assets" :key="l.label" :class="{ total: isTotal(l) }">
            <td :class="{ indent: l.indent }">{{ l.label }}<span v-if="l.standard" class="muted"> · {{ l.standard }}</span></td>
            <td class="n">{{ irr(l.current) }}</td><td></td>
          </tr>
          <tr class="total"><td>Liabilities</td><td></td><td></td></tr>
          <tr v-for="l in balance?.liabilities" :key="l.label" :class="{ total: isTotal(l) }">
            <td :class="{ indent: l.indent }">{{ l.label }}<span v-if="l.standard" class="muted"> · {{ l.standard }}</span></td>
            <td class="n">{{ irr(l.current) }}</td><td></td>
          </tr>
          <tr class="total"><td>Equity</td><td></td><td></td></tr>
          <tr v-for="l in balance?.equity_lines" :key="l.label" :class="{ total: isTotal(l) }">
            <td :class="{ indent: l.indent }">{{ l.label }}<span v-if="l.standard" class="muted"> · {{ l.standard }}</span></td>
            <td class="n">{{ irr(l.current) }}</td><td></td>
          </tr>
          <tr class="total" style="border-top:2px solid var(--ink)">
            <td>{{ balance?.check?.label }}
              <span class="chip" :class="balance?.balances ? 'Paid' : 'Partial'">{{ balance?.balances ? "A = L + E ✓" : "out of balance" }}</span>
            </td>
            <td class="n">{{ irr(balance?.check?.current) }}</td>
            <td class="n muted">= {{ irr(balance?.assets?.find(a => a.label === 'Total Assets')?.current) }}</td>
          </tr>
        </tbody>
      </table>
      <div class="note">
        Statement of Financial Position — IAS 1. Accounting equation <strong>A = L + E</strong> (CFA L1).
        Retained Earnings articulates with the Income Statement's Net Profit; with no cash/GL ledger, opening
        contributed capital is shown as the implied balancing figure rather than plugged silently into equity.
      </div>
    </div>
  </div>
</template>
