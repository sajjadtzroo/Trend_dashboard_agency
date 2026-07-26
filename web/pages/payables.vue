<script setup lang="ts">
import { palette, series } from "~/composables/useChartTheme";
const { data: rows, pending } = useApi<any[]>("/payables");
const { data: aging, pending: agingPending } = useApi<any[]>("/payables-aging");
const total = computed(() => sumBy(rows.value, "balance"));
const { q, view, sortBy, arrow, count } = useGrid(rows, { sort: "balance", keys: ["supplier"] });

const N = 12;
const top = computed(() => [...(rows.value || [])].sort((a, b) => b.balance - a.balance).slice(0, N));
const chart = computed(() => ({
  labels: top.value.map((r) => r.supplier),
  datasets: [
    { label: "Paid", data: top.value.map((r) => r.paid), backgroundColor: palette.green },
    { label: "Balance", data: top.value.map((r) => r.balance), backgroundColor: palette.coral },
  ],
}));

// Ageing buckets — fixed order so the axis stays stable when a bucket is empty.
const BUCKETS = ["0-30", "31-60", "61-90", "90+"];
const agingChart = computed(() => {
  const by = Object.fromEntries((aging.value || []).map((r) => [r.bucket, Number(r.balance || 0)]));
  return { labels: BUCKETS.map((b) => `${b} days`),
    datasets: [{ label: "Outstanding", data: BUCKETS.map((b) => by[b] || 0), backgroundColor: palette.green }] };
});

// Outstanding share by supplier — top 8 + Other.
const share = computed(() => {
  const list = [...(rows.value || [])].filter((r) => r.balance > 0).sort((a, b) => b.balance - a.balance);
  const head = list.slice(0, 8), other = sumBy(list.slice(8), "balance");
  const labels = head.map((r) => r.supplier), data = head.map((r) => r.balance);
  if (other > 0) { labels.push("Other"); data.push(other); }
  return { labels, datasets: [{ data, backgroundColor: series, borderWidth: 0 }] };
});
</script>

<template>
  <div>
    <h2>Payables (AP)</h2>

    <div class="kpis">
      <KpiCard label="Outstanding Balance" icon="ap" variant="dark" :value="irrC(total)" />
      <KpiCard label="Total Billed" icon="cost" :value="irrC(sumBy(rows, 'total'))" />
      <KpiCard label="Paid" icon="profit" :value="irrC(sumBy(rows, 'paid'))" />
      <KpiCard label="Suppliers" icon="total" :value="String(rows?.length || 0)" />
    </div>

    <div class="grid2">
      <div class="panel">
        <h3>Outstanding by Age</h3>
        <Loadable :pending="agingPending" :empty="!aging?.length" empty-text="No payables yet.">
          <ChartBar :data="agingChart" aria-label="Outstanding payable balance by age bucket" />
        </Loadable>
      </div>
      <div class="panel">
        <h3>Outstanding Share by Supplier</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No payables yet.">
          <ChartDoughnut :data="share" aria-label="Outstanding balance share by supplier" />
        </Loadable>
      </div>
    </div>

    <div class="panel">
      <h3>Paid vs Outstanding — Top {{ N }} Suppliers by Balance</h3>
      <Loadable :pending="pending" :empty="!rows?.length" empty-text="No payables yet.">
        <ChartBar :data="chart" horizontal stacked aria-label="Paid versus outstanding balance by supplier" />
      </Loadable>
      <p v-if="(rows?.length || 0) > N" class="note">Showing top {{ N }} of {{ rows?.length }} suppliers by outstanding balance; full list below.</p>
    </div>

    <div class="panel">
      <div class="grid-toolbar">
        <input v-model="q" class="search" type="search" placeholder="Search supplier…" aria-label="Search suppliers" />
        <span class="count">{{ count }} of {{ rows?.length || 0 }} suppliers</span>
      </div>
      <table class="grid pin">
        <thead><tr>
          <th class="s" @click="sortBy('supplier')">Supplier{{ arrow('supplier') }}</th>
          <th class="s n" @click="sortBy('total')">Total{{ arrow('total') }}</th>
          <th class="s n" @click="sortBy('paid')">Paid{{ arrow('paid') }}</th>
          <th class="s n" @click="sortBy('balance')">Balance{{ arrow('balance') }}</th>
          <th class="s n" @click="sortBy('bills')">Bills{{ arrow('bills') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in view" :key="r.supplier">
            <td>{{ r.supplier }}</td>
            <td class="n">{{ irr(r.total) }}</td>
            <td class="n">{{ irr(r.paid) }}</td>
            <td class="n" :class="r.balance < 0 ? 'neg' : ''">{{ irr(r.balance) }}</td>
            <td class="n">{{ r.bills }}</td>
          </tr>
          <tr v-if="!view.length"><td colspan="5" class="table-empty">No suppliers match “{{ q }}”.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
