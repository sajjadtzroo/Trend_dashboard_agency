<script setup lang="ts">
import { palette, series } from "~/composables/useChartTheme";
const { data: rows, pending } = useApi<any[]>("/receivables");
const { data: aging, pending: agingPending } = useApi<any[]>("/receivables-aging");
const total = computed(() => sumBy(rows.value, "balance"));
const { q, view, sortBy, arrow, count } = useGrid(rows, { sort: "balance", keys: ["client"] });

const chart = computed(() => {
  const list = [...(rows.value || [])].sort((a, b) => b.balance - a.balance).slice(0, 12);
  return {
    labels: list.map((r) => r.client),
    datasets: [
      { label: "Paid", data: list.map((r) => r.paid), backgroundColor: palette.green },
      { label: "Balance", data: list.map((r) => r.balance), backgroundColor: palette.amber },
    ],
  };
});

// Ageing buckets (IFRS 7) — fixed order so the axis is stable even when a bucket is empty.
const BUCKETS = ["0-30", "31-60", "61-90", "90+"];
const agingChart = computed(() => {
  const by = Object.fromEntries((aging.value || []).map((r) => [r.bucket, Number(r.balance || 0)]));
  return { labels: BUCKETS.map((b) => `${b} days`),
    datasets: [{ label: "Outstanding", data: BUCKETS.map((b) => by[b] || 0), backgroundColor: palette.green }] };
});

// Outstanding share by client — top 8 + Other.
const share = computed(() => {
  const list = [...(rows.value || [])].filter((r) => r.balance > 0).sort((a, b) => b.balance - a.balance);
  const head = list.slice(0, 8), other = sumBy(list.slice(8), "balance");
  const labels = head.map((r) => r.client), data = head.map((r) => r.balance);
  if (other > 0) { labels.push("Other"); data.push(other); }
  return { labels, datasets: [{ data, backgroundColor: series, borderWidth: 0 }] };
});
</script>

<template>
  <div>
    <h2>Receivables (AR)</h2>

    <div class="kpis">
      <KpiCard label="Outstanding Balance" icon="ar" variant="dark" :value="irrC(total)" />
      <KpiCard label="Total Receivable" icon="ar" :value="irrC(sumBy(rows, 'receivable'))" />
      <KpiCard label="Collected" icon="profit" :value="irrC(sumBy(rows, 'paid'))" />
      <KpiCard label="Invoices" icon="total" :value="String(sumBy(rows, 'invoices'))" />
    </div>

    <div class="grid2">
      <div class="panel">
        <h3>Outstanding by Age</h3>
        <Loadable :pending="agingPending" :empty="!aging?.length" empty-text="No receivables yet.">
          <ChartBar :data="agingChart" aria-label="Outstanding receivable balance by age bucket" />
        </Loadable>
      </div>
      <div class="panel">
        <h3>Outstanding Share by Client</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No receivables yet.">
          <ChartDoughnut :data="share" aria-label="Outstanding balance share by client" />
        </Loadable>
      </div>
    </div>

    <div class="panel">
      <h3>Paid vs Outstanding by Client</h3>
      <Loadable :pending="pending" :empty="!rows?.length" empty-text="No receivables yet.">
        <ChartBar :data="chart" horizontal stacked aria-label="Paid versus outstanding balance by client" />
      </Loadable>
    </div>

    <div class="panel">
      <div class="grid-toolbar">
        <input v-model="q" class="search" type="search" placeholder="Search client…" aria-label="Search clients" />
        <span class="count">{{ count }} of {{ rows?.length || 0 }} clients</span>
        <GridExport :rows="view" name="receivables" title="Receivables" />
      </div>
      <table class="grid pin">
        <thead><tr>
          <th class="s" @click="sortBy('client')">Client{{ arrow('client') }}</th>
          <th class="s n" @click="sortBy('final_amount')">Final{{ arrow('final_amount') }}</th>
          <th class="s n" @click="sortBy('receivable')">Receivable{{ arrow('receivable') }}</th>
          <th class="s n" @click="sortBy('paid')">Paid{{ arrow('paid') }}</th>
          <th class="s n" @click="sortBy('balance')">Balance{{ arrow('balance') }}</th>
          <th class="s n" @click="sortBy('invoices')">Invoices{{ arrow('invoices') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in view" :key="r.client">
            <td>{{ r.client }}</td>
            <td class="n">{{ irr(r.final_amount) }}</td>
            <td class="n">{{ irr(r.receivable) }}</td>
            <td class="n">{{ irr(r.paid) }}</td>
            <td class="n" :class="r.balance < 0 ? 'neg' : ''">{{ irr(r.balance) }}</td>
            <td class="n">{{ r.invoices }}</td>
          </tr>
          <tr v-if="!view.length"><td colspan="6" class="table-empty">No clients match “{{ q }}”.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
