<script setup lang="ts">
import { palette, series } from "~/composables/useChartTheme";

const route = useRoute();
const name = computed(() => String(route.params.brand || ""));

// Brand top-line (one row from the filter-aware /brands endpoint).
const { data: rowArr } = useApi<any[]>("/brands", () => ({ brand: name.value }));
const b = computed(() => (rowArr.value || [])[0] || null);

// Per-campaign breakdown for this brand (IFRS-8 segment endpoint, scoped by brand).
const { data: seg, pending: segPending } = useApi<any>("/statements/segments", () => ({ by: "campaign", brand: name.value }));
const camps = computed(() => seg.value?.rows || []);

const bar = computed(() => {
  const list = [...camps.value].sort((a, b) => b.revenue - a.revenue).slice(0, 12);
  return {
    labels: list.map((c) => c.segment),
    datasets: [
      { label: "Revenue", data: list.map((c) => c.revenue), backgroundColor: palette.green },
      { label: "Cost", data: list.map((c) => c.cost), backgroundColor: palette.grey },
    ],
  };
});
const share = computed(() => {
  const list = [...camps.value].sort((a, b) => b.revenue - a.revenue).slice(0, 8);
  return { labels: list.map((c) => c.segment), datasets: [{ data: list.map((c) => c.revenue), backgroundColor: series, borderWidth: 0 }] };
});
</script>

<template>
  <div>
    <NuxtLink to="/brands" class="muted" style="display:inline-block;margin-bottom:10px">← All brands</NuxtLink>
    <h2>{{ name }} <span v-if="b?.client" class="muted" style="font-weight:400">· {{ b.client }}</span></h2>

    <div class="kpis">
      <KpiCard label="Revenue" icon="revenue" variant="dark" :value="irrC(b?.revenue)" />
      <KpiCard label="Cost" icon="cost" :value="irrC(b?.cost)" />
      <KpiCard label="Op. Profit" icon="profit" :value="irrC(b?.profit)" :tone="(b?.profit ?? 0) >= 0 ? 'pos' : 'neg'" />
      <KpiCard label="Margin" icon="margin" :value="pct(b?.margin)" />
      <KpiCard label="Orders" icon="total" :value="String(b?.orders ?? 0)" />
    </div>

    <div class="grid2">
      <div class="panel">
        <h3>Revenue vs Cost by Campaign</h3>
        <Loadable :pending="segPending" :empty="!camps.length" empty-text="No campaigns for this brand.">
          <ChartBar :data="bar" horizontal aria-label="Revenue and cost by campaign" />
        </Loadable>
      </div>
      <div class="panel">
        <h3>Revenue Share</h3>
        <Loadable :pending="segPending" :empty="!camps.length" empty-text="No campaigns for this brand.">
          <ChartDoughnut :data="share" aria-label="Revenue share by campaign" />
        </Loadable>
      </div>
    </div>

    <div class="panel">
      <h3>Campaigns</h3>
      <table>
        <thead><tr>
          <th>Order / Campaign</th><th class="n">Revenue</th><th class="n">Cost</th>
          <th class="n">Op. Profit</th><th class="n">Margin</th><th class="n">Orders</th>
        </tr></thead>
        <tbody>
          <tr v-for="p in camps" :key="p.segment">
            <td>{{ p.segment }}<span v-if="p.label && p.label !== p.segment" class="muted"> · {{ p.label }}</span></td>
            <td class="n">{{ irr(p.revenue) }}</td>
            <td class="n">{{ irr(p.cost) }}</td>
            <td class="n">{{ irr(p.operating_profit) }}</td>
            <td class="n" :class="p.margin >= 0 ? 'pos' : 'neg'">{{ pct(p.margin) }}</td>
            <td class="n">{{ p.orders }}</td>
          </tr>
          <tr v-if="!camps.length && !segPending"><td colspan="6" class="empty">No campaigns.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
