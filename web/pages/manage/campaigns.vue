<script setup lang="ts">
import { palette, series } from "~/composables/useChartTheme";
const { data: rows, pending } = useApi<any[]>("/manage/campaigns");
const N = 12;
const top = computed(() => [...(rows.value || [])].sort((a, b) => b.revenue - a.revenue).slice(0, N));
const rev = computed(() => sumBy(rows.value, "revenue"));
const prof = computed(() => sumBy(rows.value, "profit"));
const { q, view, sortBy, arrow, count } = useGrid(rows, { sort: "revenue", keys: ["name", "client"] });
const chart = computed(() => ({
  labels: top.value.map((r) => r.name),
  datasets: [
    { label: "Revenue", data: top.value.map((r) => r.revenue), backgroundColor: palette.green },
    { label: "Cost", data: top.value.map((r) => r.cost), backgroundColor: palette.grey },
  ],
}));
// Revenue share: top 8 + "Other" (donut stays legible ≤ ~9 slices).
const share = computed(() => {
  const list = [...(rows.value || [])].sort((a, b) => b.revenue - a.revenue);
  const head = list.slice(0, 8), other = sumBy(list.slice(8), "revenue");
  const labels = head.map((r) => r.name), data = head.map((r) => r.revenue);
  if (other > 0) { labels.push("Other"); data.push(other); }
  return { labels, datasets: [{ data, backgroundColor: series, borderWidth: 0 }] };
});
</script>

<template>
  <div>
    <h2>Campaigns</h2>
    <div class="kpis">
      <KpiCard label="Total Revenue" icon="revenue" variant="dark" :value="irrC(rev)" />
      <KpiCard label="Total Cost" icon="cost" :value="irrC(sumBy(rows, 'cost'))" />
      <KpiCard label="Total Profit" icon="profit" :value="irrC(prof)" :tone="prof >= 0 ? 'pos' : 'neg'" />
      <KpiCard label="Avg Margin" icon="margin" :value="pct(rev ? (prof / rev) * 100 : null)" />
      <KpiCard label="Campaigns" icon="total" :value="String(rows?.length || 0)" />
    </div>
    <div class="grid2">
      <div class="panel">
        <h3>Top {{ N }} Campaigns by Revenue</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No campaigns yet.">
          <ChartBar :data="chart" horizontal aria-label="Revenue and cost by campaign" />
        </Loadable>
      </div>
      <div class="panel">
        <h3>Revenue Share</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No campaigns yet.">
          <ChartDoughnut :data="share" aria-label="Revenue share by campaign" />
        </Loadable>
      </div>
    </div>
    <div class="panel">
      <div class="grid-toolbar">
        <input v-model="q" class="search" type="search" placeholder="Search campaign, client…" aria-label="Search campaigns" />
        <span class="count">{{ count }} of {{ rows?.length || 0 }} campaigns</span>
      </div>
      <table class="grid pin">
        <thead><tr>
          <th class="s" @click="sortBy('name')">Campaign{{ arrow('name') }}</th>
          <th class="s" @click="sortBy('client')">Client{{ arrow('client') }}</th>
          <th class="s n" @click="sortBy('revenue')">Revenue{{ arrow('revenue') }}</th>
          <th class="s n" @click="sortBy('cost')">Cost{{ arrow('cost') }}</th>
          <th class="s n" @click="sortBy('profit')">Profit{{ arrow('profit') }}</th>
          <th class="s n" @click="sortBy('margin')">Margin{{ arrow('margin') }}</th>
          <th class="s n" @click="sortBy('rows')">Rows{{ arrow('rows') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in view" :key="r.id">
            <td>{{ r.name }}</td><td>{{ r.client || "—" }}</td>
            <td class="n">{{ irr(r.revenue) }}</td><td class="n">{{ irr(r.cost) }}</td>
            <td class="n">{{ irr(r.profit) }}</td>
            <td class="n" :class="r.margin >= 0 ? 'pos' : 'neg'">{{ pct(r.margin) }}</td>
            <td class="n">{{ r.rows }}</td>
          </tr>
          <tr v-if="!view.length"><td colspan="7" class="table-empty">No campaigns match “{{ q }}”.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
