<script setup lang="ts">
import { palette } from "~/composables/useChartTheme";

const { data: funnel, pending } = useApi<any[]>("/funnel");
const money = ref(true);                       // true = Revenue (IRR), false = Deal count

// per-status value (revenue or count) keyed by the raw source label
const V = (label: string) => {
  const r = (funnel.value || []).find((x) => x.order_status === label);
  return r ? (money.value ? Number(r.revenue || 0) : Number(r.count || 0)) : 0;
};
const vals = computed(() => ({
  O: V("Opportuinity"), P: V("Proposal"), C: V("Confirm"),
  I: V("Invoice"), S: V("Suspend"), D: V("Decline"),
}));

// stage totals (cumulative funnel) for KPIs + the narrowing bar
const stages = computed(() => {
  const { O, P, C, I, S, D } = vals.value;
  return { opportunity: O + P + C + I + S + D, proposal: P + C + I + S, confirm: C + I + S, invoice: I, suspend: S, decline: D };
});
const winRate = computed(() => {
  const t = stages.value.opportunity;
  return t ? (vals.value.I / (money.value ? t : t)) * 100 : null;   // Invoice value / total pipeline
});

function nodeColor(n: string) {
  if (n === "Invoice") return palette.green;          // won
  if (n === "Decline") return "#C62828";              // lost
  if (n === "Suspend") return "#B58A12";              // paused
  if (n.startsWith("Open")) return "#A1A1AA";         // stalled
  return "#43A047";                                    // advancing stages
}

const sankey = computed(() => {
  const { O, P, C, I, S, D } = vals.value;
  const flows = [
    ["Opportunity", "Decline", D],
    ["Opportunity", "Open · Opportunity", O],
    ["Opportunity", "Proposal", P + C + I + S],
    ["Proposal", "Open · Proposal", P],
    ["Proposal", "Confirm", C + I + S],
    ["Confirm", "Open · Confirm", C],
    ["Confirm", "Suspend", S],
    ["Confirm", "Invoice", I],
  ].filter(([, , v]) => (v as number) > 0).map(([from, to, flow]) => ({ from, to, flow }));

  // ponytail: intermediate nodes must balance (inflow == outflow) or the model drifted
  const inn: any = {}, out: any = {};
  flows.forEach((f: any) => { out[f.from] = (out[f.from] || 0) + f.flow; inn[f.to] = (inn[f.to] || 0) + f.flow; });
  for (const n of ["Proposal", "Confirm"])
    if (Math.abs((inn[n] || 0) - (out[n] || 0)) > 1) console.warn("sankey unbalanced at", n, inn[n], out[n]);

  return {
    datasets: [{
      data: flows,
      colorFrom: (c: any) => nodeColor(c.dataset.data[c.dataIndex].from),
      colorTo: (c: any) => nodeColor(c.dataset.data[c.dataIndex].to),
      colorMode: "gradient",
      borderWidth: 0,
      column: { "Opportunity": 0, "Decline": 1, "Open · Opportunity": 1, "Proposal": 1,
                "Open · Proposal": 2, "Confirm": 2, "Open · Confirm": 3, "Suspend": 3, "Invoice": 3 },
    }],
  };
});

// narrowing funnel bar (advancing stages only)
const funnelBar = computed(() => {
  const s = stages.value;
  return { labels: ["Opportunity", "Proposal", "Confirm", "Invoice"],
    datasets: [{ label: money.value ? "Revenue" : "Deals", data: [s.opportunity, s.proposal, s.confirm, s.invoice], backgroundColor: palette.green }] };
});

// ---- per-stage breakdown by account / client / service ----
const stage = ref("Invoice");                  // raw status label
const by = ref<"account" | "client" | "service">("account");
const { data: bd } = useApi<any[]>("/funnel-breakdown", () => ({ by: by.value }));
const STAGES = [["Opportuinity", "Opportunity"], ["Proposal", "Proposal"], ["Confirm", "Confirm"],
                ["Invoice", "Invoice"], ["Suspend", "Suspend"], ["Decline", "Decline"]];

const stageRows = computed(() => {
  const rows = (bd.value || []).filter((r) => r.order_status === stage.value);
  const tot = rows.reduce((s, r) => s + Number(r.revenue || 0), 0);
  return rows.map((r) => ({ ...r, share: tot ? (Number(r.revenue) / tot) * 100 : 0 }))
             .sort((a, b) => b.revenue - a.revenue);
});
const grid = useGrid(stageRows, { sort: "revenue", keys: ["dim"] });
const bdBar = computed(() => {
  const top = stageRows.value.slice(0, 10);
  return { labels: top.map((r) => r.dim),
    datasets: [{ label: money.value ? "Revenue" : "Deals", data: top.map((r) => money.value ? r.revenue : r.count), backgroundColor: palette.green }] };
});

// win-rate by account (invoiced ÷ all their deals)
const winByAccount = computed(() => {
  const acc: Record<string, { inv: number; all: number }> = {};
  for (const r of bd.value || []) {
    if (by.value !== "account") break;
    const a = r.dim; acc[a] = acc[a] || { inv: 0, all: 0 };
    acc[a].all += Number(r.count || 0);
    if (r.order_status === "Invoice") acc[a].inv += Number(r.count || 0);
  }
  const list = Object.entries(acc).map(([a, v]) => ({ a, rate: v.all ? (v.inv / v.all) * 100 : 0 })).sort((x, y) => y.rate - x.rate);
  return { labels: list.map((x) => x.a), datasets: [{ label: "Win rate %", data: list.map((x) => Math.round(x.rate * 10) / 10), backgroundColor: palette.accent }] };
});
</script>

<template>
  <div>
    <h2>Sales Funnel</h2>

    <div class="kpis">
      <KpiCard label="Pipeline (Opportunity)" icon="total" variant="dark" :value="money ? irrC(stages.opportunity) : String(stages.opportunity)" />
      <KpiCard label="Confirmed" icon="profit" :value="money ? irrC(stages.confirm) : String(stages.confirm)" />
      <KpiCard label="Invoiced (won)" icon="revenue" :value="money ? irrC(stages.invoice) : String(stages.invoice)" />
      <KpiCard label="Win rate" icon="margin" :value="pct(winRate)" />
    </div>

    <div class="panel">
      <h3 class="h3-row">Funnel Flow
        <span class="seg">
          <button :class="{ on: money }" @click="money = true">Revenue</button>
          <button :class="{ on: !money }" @click="money = false">Count</button>
        </span>
      </h3>
      <Loadable :pending="pending" :empty="!funnel?.length" empty-text="No funnel data.">
        <ChartSankey :data="sankey" :money="money" name="sales-funnel" aria-label="Sales funnel flow" />
      </Loadable>
    </div>

    <div class="grid2">
      <div class="panel">
        <h3>Funnel Stages ({{ money ? "Revenue" : "Deals" }})</h3>
        <Loadable :pending="pending" :empty="!funnel?.length" empty-text="No funnel data.">
          <ChartBar :data="funnelBar" horizontal name="funnel-stages" aria-label="Funnel stage totals" />
        </Loadable>
      </div>
      <div class="panel">
        <h3>Win Rate by Account</h3>
        <Loadable :pending="!bd" :empty="by !== 'account' || !bd?.length" empty-text="Switch a breakdown to Account to see win rates.">
          <ChartBar :data="winByAccount" horizontal name="win-rate" aria-label="Win rate by account" />
        </Loadable>
      </div>
    </div>

    <div class="panel">
      <h3 class="h3-row">Stage Breakdown</h3>
      <div class="tabs">
        <button v-for="[raw, label] in STAGES" :key="raw" :class="{ active: stage === raw }" @click="stage = raw">{{ label }}</button>
      </div>
      <div class="tabs">
        <button v-for="d in (['account','client','service'] as const)" :key="d" :class="{ active: by === d }" @click="by = d">
          {{ d[0].toUpperCase() + d.slice(1) }}
        </button>
      </div>

      <ChartBar v-if="stageRows.length" :data="bdBar" horizontal class="mt-panel" name="stage-breakdown" aria-label="Stage breakdown" />

      <div class="grid-toolbar mt-panel">
        <input v-model="grid.q.value" class="search" type="search" :placeholder="`Search ${by}…`" aria-label="Search breakdown" />
        <span class="count">{{ grid.count.value }} rows</span>
      </div>
      <table class="grid pin">
        <thead><tr>
          <th class="s" @click="grid.sortBy('dim')">{{ by[0].toUpperCase() + by.slice(1) }}{{ grid.arrow('dim') }}</th>
          <th class="s n" @click="grid.sortBy('count')">Deals{{ grid.arrow('count') }}</th>
          <th class="s n" @click="grid.sortBy('revenue')">Revenue{{ grid.arrow('revenue') }}</th>
          <th class="s n" @click="grid.sortBy('share')">% of stage{{ grid.arrow('share') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in grid.view.value" :key="r.dim">
            <td>{{ r.dim }}</td>
            <td class="n">{{ r.count }}</td>
            <td class="n">{{ irr(r.revenue) }}</td>
            <td class="n">{{ pct(r.share) }}</td>
          </tr>
          <tr v-if="!grid.view.value.length"><td colspan="4" class="table-empty">No {{ by }} rows for this stage.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.seg{display:inline-flex;gap:0;border:1px solid var(--border);border-radius:999px;overflow:hidden;margin-inline-start:auto}
.seg button{border:none;background:#fff;color:var(--muted);padding:5px 14px;cursor:pointer;font-size:12px}
.seg button.on{background:var(--primary);color:#fff;font-weight:600}
</style>
