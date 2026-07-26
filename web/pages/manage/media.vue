<script setup lang="ts">
import { palette, series } from "~/composables/useChartTheme";
const { data: rows, pending } = useApi<any[]>("/manage/media");
const prof = computed(() => sumBy(rows.value, "profit"));
const { q, view, sortBy, arrow, count } = useGrid(rows, { sort: "revenue", keys: ["name"] });
const bar = computed(() => {
  const list = rows.value || [];
  return {
    labels: list.map((r) => r.name),
    datasets: [
      { label: "Revenue", data: list.map((r) => r.revenue), backgroundColor: palette.green },
      { label: "Cost", data: list.map((r) => r.cost), backgroundColor: palette.grey },
    ],
  };
});
const share = computed(() => {
  const list = rows.value || [];
  return { labels: list.map((r) => r.name), datasets: [{ data: list.map((r) => r.revenue), backgroundColor: series, borderWidth: 0 }] };
});
// Absolute profit per channel — which media actually earns, not just turns over.
const profitBar = computed(() => {
  const list = [...(rows.value || [])].sort((a, b) => b.profit - a.profit);
  return { labels: list.map((r) => r.name),
    datasets: [{ label: "Profit", data: list.map((r) => r.profit), backgroundColor: palette.green }] };
});
// Margin % per channel — efficiency independent of size.
const marginBar = computed(() => {
  const list = [...(rows.value || [])].map((r) => ({ name: r.name, m: r.revenue ? (r.profit / r.revenue) * 100 : 0 }))
    .sort((a, b) => b.m - a.m);
  return { labels: list.map((r) => r.name),
    datasets: [{ label: "Margin %", data: list.map((r) => Math.round(r.m * 10) / 10), backgroundColor: palette.accent }] };
});
</script>

<template>
  <div>
    <h2>Media Channels</h2>
    <div class="kpis">
      <KpiCard label="Total Revenue" icon="revenue" variant="dark" :value="irrC(sumBy(rows, 'revenue'))" />
      <KpiCard label="Total Cost" icon="cost" :value="irrC(sumBy(rows, 'cost'))" />
      <KpiCard label="Total Profit" icon="profit" :value="irrC(prof)" :tone="prof >= 0 ? 'pos' : 'neg'" />
      <KpiCard label="Channels" icon="total" :value="String(rows?.length || 0)" />
    </div>
    <div class="grid2">
      <div class="panel">
        <h3>Revenue vs Cost by Media</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No media yet.">
          <ChartBar :data="bar" aria-label="Revenue and cost by media channel" />
        </Loadable>
      </div>
      <div class="panel">
        <h3>Revenue Share</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No media yet.">
          <ChartDoughnut :data="share" name="media-revenue-share" aria-label="Revenue share by media channel" />
        </Loadable>
      </div>
    </div>
    <div class="grid2">
      <div class="panel">
        <h3>Profit by Media</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No media yet.">
          <ChartBar :data="profitBar" horizontal name="media-profit" aria-label="Operating profit by media channel" />
        </Loadable>
      </div>
      <div class="panel">
        <h3>Margin by Media</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No media yet.">
          <ChartBar :data="marginBar" horizontal name="media-margin" aria-label="Profit margin percent by media channel" />
        </Loadable>
      </div>
    </div>
    <div class="panel">
      <div class="grid-toolbar">
        <input v-model="q" class="search" type="search" placeholder="Search media…" aria-label="Search media" />
        <span class="count">{{ count }} of {{ rows?.length || 0 }} media</span>
        <GridExport :rows="view" name="media" title="Media" />
      </div>
      <table class="grid pin">
        <thead><tr>
          <th class="s" @click="sortBy('name')">Media{{ arrow('name') }}</th>
          <th class="s n" @click="sortBy('revenue')">Revenue{{ arrow('revenue') }}</th>
          <th class="s n" @click="sortBy('cost')">Cost{{ arrow('cost') }}</th>
          <th class="s n" @click="sortBy('profit')">Profit{{ arrow('profit') }}</th>
          <th class="s n" @click="sortBy('rows')">Rows{{ arrow('rows') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in view" :key="r.id">
            <td>{{ r.name }}</td>
            <td class="n">{{ irr(r.revenue) }}</td><td class="n">{{ irr(r.cost) }}</td>
            <td class="n">{{ irr(r.profit) }}</td><td class="n">{{ r.rows }}</td>
          </tr>
          <tr v-if="!view.length"><td colspan="5" class="table-empty">No media match “{{ q }}”.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
