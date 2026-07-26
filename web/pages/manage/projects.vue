<script setup lang="ts">
import { palette } from "~/composables/useChartTheme";
const { data: rows, pending } = useApi<any[]>("/manage/projects");
const N = 12;
const top = computed(() => [...(rows.value || [])].sort((a, b) => b.revenue - a.revenue).slice(0, N));
const rev = computed(() => sumBy(rows.value, "revenue"));
const prof = computed(() => sumBy(rows.value, "profit"));
const { q, view, sortBy, arrow, count } = useGrid(rows, { sort: "revenue", keys: ["name", "title", "client"] });
const chart = computed(() => ({
  labels: top.value.map((r) => r.name),
  datasets: [
    { label: "Revenue", data: top.value.map((r) => r.revenue), backgroundColor: palette.green },
    { label: "Cost", data: top.value.map((r) => r.cost), backgroundColor: palette.grey },
  ],
}));
// Profit by top project — where margin actually lands, not just top-line revenue.
const profitChart = computed(() => {
  const list = [...(rows.value || [])].sort((a, b) => b.profit - a.profit).slice(0, N);
  return { labels: list.map((r) => r.name),
    datasets: [{ label: "Profit", data: list.map((r) => r.profit), backgroundColor: palette.green }] };
});
</script>

<template>
  <div>
    <h2>Projects</h2>
    <div class="kpis">
      <KpiCard label="Total Revenue" icon="revenue" variant="dark" :value="irrC(rev)" />
      <KpiCard label="Total Cost" icon="cost" :value="irrC(sumBy(rows, 'cost'))" />
      <KpiCard label="Total Profit" icon="profit" :value="irrC(prof)" :tone="prof >= 0 ? 'pos' : 'neg'" />
      <KpiCard label="Avg Margin" icon="margin" :value="pct(rev ? (prof / rev) * 100 : null)" />
      <KpiCard label="Projects" icon="total" :value="String(rows?.length || 0)" />
    </div>
    <div class="grid2">
      <div class="panel">
        <h3>Top {{ N }} Projects by Revenue</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No projects yet.">
          <ChartBar :data="chart" horizontal aria-label="Revenue and cost by project" />
        </Loadable>
      </div>
      <div class="panel">
        <h3>Top {{ N }} Projects by Profit</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No projects yet.">
          <ChartBar :data="profitChart" horizontal aria-label="Operating profit by project" />
        </Loadable>
      </div>
    </div>
    <div class="panel">
      <div class="grid-toolbar">
        <input v-model="q" class="search" type="search" placeholder="Search code, title, client…" aria-label="Search projects" />
        <span class="count">{{ count }} of {{ rows?.length || 0 }} projects</span>
      </div>
      <table class="grid pin">
        <thead><tr>
          <th class="s" @click="sortBy('name')">Code{{ arrow('name') }}</th>
          <th class="s" @click="sortBy('title')">Title{{ arrow('title') }}</th>
          <th class="s" @click="sortBy('client')">Client{{ arrow('client') }}</th>
          <th class="s n" @click="sortBy('revenue')">Revenue{{ arrow('revenue') }}</th>
          <th class="s n" @click="sortBy('cost')">Cost{{ arrow('cost') }}</th>
          <th class="s n" @click="sortBy('profit')">Profit{{ arrow('profit') }}</th>
          <th class="s n" @click="sortBy('campaigns')">Campaigns{{ arrow('campaigns') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in view" :key="r.id">
            <td>{{ r.name }}</td><td>{{ r.title || "—" }}</td><td>{{ r.client || "—" }}</td>
            <td class="n">{{ irr(r.revenue) }}</td><td class="n">{{ irr(r.cost) }}</td>
            <td class="n">{{ irr(r.profit) }}</td><td class="n">{{ r.campaigns }}</td>
          </tr>
          <tr v-if="!view.length"><td colspan="7" class="table-empty">No projects match “{{ q }}”.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
