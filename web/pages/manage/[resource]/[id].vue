<script setup lang="ts">
import { palette } from "~/composables/useChartTheme";
const GREEN = palette.green, ACCENT = palette.accent, GREY = palette.grey;
const route = useRoute();
const resource = computed(() => route.params.resource as string);
const id = computed(() => route.params.id as string);
const singular: Record<string, string> = { campaigns: "Campaign", users: "User / Manager", projects: "Project", media: "Media" };

const { data, error } = useApi<any>(() => `/manage/${resource.value}/${id.value}`);

const name = computed(() => {
  const it = data.value?.item || {};
  return it.order_name || it.account || it.project_code || it.media_name || it.project_name || `#${id.value}`;
});
const txns = computed<any[]>(() => data.value?.transactions || []);
// revenue = invoiced only, consistent with every other card/chart in the app
const sales = computed(() => txns.value.filter((t) => t.transaction_type === "SALE" && t.order_status === "Invoice"));
const sum = (a: any[], k: string) => a.reduce((s, r) => s + Number(r[k] || 0), 0);

const kpi = computed(() => {
  const rev = sum(sales.value, "revenue"), cost = sum(sales.value, "cost");
  const prof = sum(sales.value, "operational_profit");
  return { rev, cost, prof, margin: rev ? (prof / rev) * 100 : null, orders: sales.value.length };
});

// monthly revenue vs cost trend
const trend = computed(() => {
  const m: Record<string, any> = {};
  for (const t of sales.value) {
    if (!t.jalali_month) continue;
    const key = `${t.jalali_year}/${String(t.jalali_month).padStart(2, "0")}`;
    m[key] = m[key] || { revenue: 0, cost: 0 };
    m[key].revenue += Number(t.revenue || 0);
    m[key].cost += Number(t.cost || 0);
  }
  const labels = Object.keys(m).sort();
  return {
    labels,
    datasets: [
      { label: "Revenue", data: labels.map((k) => m[k].revenue), borderColor: GREEN,
        backgroundColor: "rgba(46,125,50,.1)", fill: true, tension: 0.3 },
      { label: "Cost", data: labels.map((k) => m[k].cost), borderColor: ACCENT, tension: 0.3 },
    ],
  };
});

// revenue by service breakdown
const byService = computed(() => {
  const m: Record<string, number> = {};
  for (const t of sales.value) if (t.service) m[t.service] = (m[t.service] || 0) + Number(t.revenue || 0);
  const labels = Object.keys(m);
  return { labels, datasets: [{ label: "Revenue", data: labels.map((k) => m[k]), backgroundColor: GREEN }] };
});
const hasService = computed(() => byService.value.labels.length > 0);

const { q, view, sortBy, arrow, count } = useGrid(txns, {
  sort: "jalali_date",
  keys: ["jalali_date", "transaction_type", "client", "brand", "service", "order_status", "source_row"],
});
</script>

<template>
  <div>
    <PageHeader :title="name"
      :breadcrumb="[{ label: (singular[resource] || resource) + 's', to: `/manage/${resource}` }, { label: name }]" />
    <p v-if="error" class="neg">Failed to load. Is the API running?</p>

    <div class="kpis">
      <KpiCard label="Revenue" icon="revenue" :value="irrC(kpi.rev)" />
      <KpiCard label="Cost" icon="cost" :value="irrC(kpi.cost)" />
      <KpiCard label="Op. Profit" icon="profit" :value="irrC(kpi.prof)" :tone="kpi.prof >= 0 ? 'pos' : 'neg'" />
      <KpiCard label="Margin" :value="pct(kpi.margin)" />
      <KpiCard label="Orders" :value="String(kpi.orders)" />
    </div>

    <div class="grid2">
      <div class="panel"><h3>Revenue vs Cost — Monthly</h3><ChartLine :data="trend" /></div>
      <div v-if="hasService" class="panel"><h3>Revenue by Service</h3><ChartBar :data="byService" /></div>
    </div>

    <div class="panel">
      <h3>Transactions ({{ txns.length }})</h3>
      <div class="grid-toolbar">
        <input v-model="q" class="search" type="search" placeholder="Search date, client, brand, service…" aria-label="Search transactions" />
        <span class="count">{{ count }} of {{ txns.length }} rows</span>
        <GridExport :rows="view" :name="`${resource}-${id}-transactions`" title="Transactions" />
      </div>
      <table class="grid pin">
        <thead><tr>
          <th class="s" @click="sortBy('jalali_date')">Date{{ arrow('jalali_date') }}</th>
          <th class="s" @click="sortBy('transaction_type')">Type{{ arrow('transaction_type') }}</th>
          <th class="s" @click="sortBy('client')">Client{{ arrow('client') }}</th>
          <th class="s" @click="sortBy('brand')">Brand{{ arrow('brand') }}</th>
          <th class="s" @click="sortBy('service')">Service{{ arrow('service') }}</th>
          <th class="s" @click="sortBy('order_status')">Status{{ arrow('order_status') }}</th>
          <th class="s n" @click="sortBy('revenue')">Revenue{{ arrow('revenue') }}</th>
          <th class="s n" @click="sortBy('cost')">Cost{{ arrow('cost') }}</th>
          <th class="s n" @click="sortBy('balance')">Balance{{ arrow('balance') }}</th>
          <th class="s" @click="sortBy('source_row')">Row{{ arrow('source_row') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="(t, i) in view" :key="i">
            <td>{{ t.jalali_date || "—" }}</td>
            <td>{{ t.transaction_type }}</td>
            <td>{{ t.client || "—" }}</td>
            <td>{{ t.brand || "—" }}</td>
            <td>{{ t.service || "—" }}</td>
            <td>{{ statusLabel(t.order_status) }}</td>
            <td class="n">{{ irr(t.revenue) }}</td>
            <td class="n">{{ irr(t.cost) }}</td>
            <td class="n">{{ irr(t.balance) }}</td>
            <td class="muted">{{ t.source_row }}</td>
          </tr>
          <tr v-if="!view.length"><td colspan="10" class="table-empty">No transactions match “{{ q }}”.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
