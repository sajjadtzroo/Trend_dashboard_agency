<script setup lang="ts">
import { palette } from "~/composables/useChartTheme";

const { data: brands } = useApi<any[]>("/brands");
const bMargin = computed(() => { const r = sumBy(brands.value, "revenue"); return r ? (sumBy(brands.value, "profit") / r) * 100 : null; });

// selected brands to compare (default: top 3 by revenue)
const selected = ref<string[]>([]);
watch(brands, (list) => {
  if (list && selected.value.length === 0) selected.value = list.slice(0, 3).map((b) => b.brand);
}, { immediate: true });

function toggle(name: string) {
  selected.value = selected.value.includes(name)
    ? selected.value.filter((n) => n !== name)
    : [...selected.value, name];
}

const picked = computed(() => (brands.value || []).filter((b) => selected.value.includes(b.brand)));

// Search/sort like the other grids. Clicking a brand navigates to /brands/<name>.
const { q, view, sortBy, arrow, count } = useGrid(brands, { sort: "revenue", keys: ["brand", "client"] });

const compareData = computed(() => ({
  labels: picked.value.map((b) => b.brand),
  datasets: [
    { label: "Revenue", data: picked.value.map((b) => b.revenue), backgroundColor: palette.green },
    { label: "Cost", data: picked.value.map((b) => b.cost), backgroundColor: palette.grey },
    { label: "Profit", data: picked.value.map((b) => b.profit), backgroundColor: palette.accent },
  ],
}));
</script>

<template>
  <div>
    <h2>Brands — Compare &amp; Check</h2>

    <div class="kpis">
      <KpiCard label="Total Revenue" icon="revenue" variant="dark" :value="irrC(sumBy(brands, 'revenue'))" />
      <KpiCard label="Total Cost" icon="cost" :value="irrC(sumBy(brands, 'cost'))" />
      <KpiCard label="Total Profit" icon="profit" :value="irrC(sumBy(brands, 'profit'))" />
      <KpiCard label="Avg Margin" icon="margin" :value="pct(bMargin)" />
      <KpiCard label="Brands" icon="total" :value="String(brands?.length || 0)" />
    </div>

    <div v-if="picked.length" class="panel">
      <h3>Comparison — {{ picked.length }} brand(s) selected</h3>
      <ChartBar :data="compareData" />
      <table class="mt-panel">
        <thead><tr>
          <th>Metric</th><th v-for="b in picked" :key="b.brand" class="n">{{ b.brand }}</th>
        </tr></thead>
        <tbody>
          <tr><td>Client</td><td v-for="b in picked" :key="b.brand" class="n">{{ b.client || "—" }}</td></tr>
          <tr><td>Revenue</td><td v-for="b in picked" :key="b.brand" class="n">{{ irr(b.revenue) }}</td></tr>
          <tr><td>Cost</td><td v-for="b in picked" :key="b.brand" class="n">{{ irr(b.cost) }}</td></tr>
          <tr><td>Op. Profit</td><td v-for="b in picked" :key="b.brand" class="n">{{ irr(b.profit) }}</td></tr>
          <tr><td>Margin</td>
            <td v-for="b in picked" :key="b.brand" class="n" :class="b.margin >= 0 ? 'pos' : 'neg'">{{ pct(b.margin) }}</td></tr>
          <tr><td>Orders</td><td v-for="b in picked" :key="b.brand" class="n">{{ b.orders }}</td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h3>All Brands — click a brand for detail, tick to compare</h3>
      <div class="grid-toolbar">
        <input v-model="q" class="search" type="search" placeholder="Search brand, client…" aria-label="Search brands" />
        <span class="count">{{ count }} of {{ brands?.length || 0 }} brands</span>
      </div>
      <table>
        <thead><tr>
          <th></th>
          <th class="s" @click="sortBy('brand')">Brand{{ arrow('brand') }}</th>
          <th class="s" @click="sortBy('client')">Client{{ arrow('client') }}</th>
          <th class="s n" @click="sortBy('revenue')">Revenue{{ arrow('revenue') }}</th>
          <th class="s n" @click="sortBy('cost')">Cost{{ arrow('cost') }}</th>
          <th class="s n" @click="sortBy('profit')">Profit{{ arrow('profit') }}</th>
          <th class="s n" @click="sortBy('margin')">Margin{{ arrow('margin') }}</th>
          <th class="s n" @click="sortBy('orders')">Orders{{ arrow('orders') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="b in view" :key="b.brand">
            <td><input type="checkbox" :checked="selected.includes(b.brand)" @change="toggle(b.brand)" /></td>
            <td><NuxtLink class="link" :to="`/brands/${encodeURIComponent(b.brand)}`">{{ b.brand }} ›</NuxtLink></td>
            <td>{{ b.client || "—" }}</td>
            <td class="n">{{ irr(b.revenue) }}</td>
            <td class="n">{{ irr(b.cost) }}</td>
            <td class="n">{{ irr(b.profit) }}</td>
            <td class="n" :class="b.margin >= 0 ? 'pos' : 'neg'">{{ pct(b.margin) }}</td>
            <td class="n">{{ b.orders }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
