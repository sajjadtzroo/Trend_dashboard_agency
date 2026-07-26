<script setup lang="ts">
import { palette, series } from "~/composables/useChartTheme";
const GREEN = palette.green, GREY = palette.grey, ACCENT = palette.accent;

const { data: kpis } = useApi<any>("/kpis");
const { data: funnel } = useApi<any[]>("/funnel");
const { data: svc } = useApi<any[]>("/revenue-by-service");
const { data: trend } = useApi<any[]>("/revenue-trend");
const { data: topClients } = useApi<any[]>("/top-clients");
const { data: topCampaigns } = useApi<any[]>("/top-campaigns");
const { data: fulfil } = useApi<any[]>("/fulfillment-trend");

const clients = useGrid(topClients, { sort: "revenue" });
const camps = useGrid(topCampaigns, { sort: "revenue" });

const funnelData = computed(() => ({
  labels: (funnel.value || []).map((r) => r.order_status),
  datasets: [{ label: "Count", data: (funnel.value || []).map((r) => r.count), backgroundColor: GREEN }],
}));
const svcData = computed(() => ({
  labels: (svc.value || []).map((r) => r.service),
  datasets: [
    { label: "Revenue", data: (svc.value || []).map((r) => r.revenue), backgroundColor: GREEN },
    { label: "Cost", data: (svc.value || []).map((r) => r.cost), backgroundColor: GREY },
  ],
}));
const trendData = computed(() => ({
  labels: (trend.value || []).map((r) => `${r.jalali_year}/${String(r.jalali_month).padStart(2, "0")}`),
  datasets: [
    { label: "Revenue", data: (trend.value || []).map((r) => r.revenue), borderColor: GREEN,
      backgroundColor: "rgba(46,125,50,.1)", fill: true, tension: 0.3 },
    { label: "Cost", data: (trend.value || []).map((r) => r.cost), borderColor: ACCENT, tension: 0.3 },
    { label: "Op. Profit", data: (trend.value || []).map((r) => Number(r.revenue || 0) - Number(r.cost || 0)),
      borderColor: GREY, borderDash: [5, 4], tension: 0.3 },
  ],
}));
// Delivery/fulfilment health over time (avg % of SALE lines fulfilled).
const fulfilData = computed(() => ({
  labels: (fulfil.value || []).map((r) => `${r.jalali_year}/${String(r.jalali_month).padStart(2, "0")}`),
  datasets: [{ label: "Fulfilment %", data: (fulfil.value || []).map((r) => r.fulfillment), borderColor: GREEN,
    backgroundColor: "rgba(46,125,50,.1)", fill: true, tension: 0.3 }],
}));

// Revenue share by client — top 6 + Other (donut ≤ ~7 slices)
const clientShare = computed(() => {
  const list = [...(topClients.value || [])].sort((a, b) => b.revenue - a.revenue);
  const top = list.slice(0, 6);
  const other = list.slice(6).reduce((s, r) => s + Number(r.revenue || 0), 0);
  const labels = top.map((r) => r.client);
  const data = top.map((r) => r.revenue);
  if (other > 0) { labels.push("Other"); data.push(other); }
  return { labels, datasets: [{ data, backgroundColor: series, borderWidth: 0 }] };
});
const campaignsBar = computed(() => {
  const list = (topCampaigns.value || []).slice(0, 8);
  return { labels: list.map((r) => r.campaign), datasets: [{ label: "Revenue", data: list.map((r) => r.revenue), backgroundColor: GREEN }] };
});
</script>

<template>
  <div>
    <div class="kpis">
      <KpiCard label="Total Revenue" icon="revenue" variant="dark" :value="irrC(kpis?.revenue)" :delta="kpis?.delta?.revenue" />
      <KpiCard label="Total Cost" icon="cost" :value="irrC(kpis?.cost)" :delta="kpis?.delta?.cost" invert />
      <KpiCard label="Operational Profit" icon="profit" :value="irrC(kpis?.op_profit)" :tone="kpis?.op_profit >= 0 ? 'pos' : 'neg'" :delta="kpis?.delta?.op_profit" />
      <KpiCard label="Avg Profit Margin" icon="margin" :value="pct(kpis?.avg_margin)" />
      <KpiCard label="AR Outstanding" icon="ar" :value="irrC(kpis?.ar_outstanding)" />
      <KpiCard label="AP Outstanding" icon="ap" :value="irrC(kpis?.ap_outstanding)" />
    </div>

    <div class="grid2">
      <div class="panel"><h3>Order Funnel</h3><ChartBar :data="funnelData" horizontal /></div>
      <div class="panel"><h3>Revenue by Service</h3><ChartBar :data="svcData" /></div>
    </div>

    <div class="grid2">
      <div class="panel"><h3>Revenue, Cost &amp; Op. Profit — Monthly (Jalali)</h3><ChartLine :data="trendData" /></div>
      <div class="panel">
        <h3>Delivery / Fulfilment — Monthly</h3>
        <ChartLine v-if="fulfil?.length" :data="fulfilData" aria-label="Average fulfilment percent by month" />
        <div v-else class="empty">No fulfilment data.</div>
      </div>
    </div>

    <div class="grid2">
      <div class="panel">
        <h3>Top Clients</h3>
        <ChartDoughnut v-if="topClients?.length" :data="clientShare" aria-label="Revenue share by client" />
        <table class="mt-panel grid">
          <thead><tr>
            <th class="s" @click="clients.sortBy('client')">Client{{ clients.arrow('client') }}</th>
            <th class="s n" @click="clients.sortBy('revenue')">Revenue{{ clients.arrow('revenue') }}</th>
            <th class="s n" @click="clients.sortBy('margin')">Margin{{ clients.arrow('margin') }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in clients.view.value" :key="r.client">
              <td>{{ r.client }}</td><td class="n">{{ irr(r.revenue) }}</td>
              <td class="n" :class="r.margin >= 0 ? 'pos' : 'neg'">{{ pct(r.margin) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="panel">
        <h3>Top Campaigns</h3>
        <ChartBar v-if="topCampaigns?.length" :data="campaignsBar" horizontal aria-label="Top campaigns by revenue" />
        <table class="mt-panel grid">
          <thead><tr>
            <th class="s" @click="camps.sortBy('campaign')">Campaign{{ camps.arrow('campaign') }}</th>
            <th class="s n" @click="camps.sortBy('revenue')">Revenue{{ camps.arrow('revenue') }}</th>
            <th class="s n" @click="camps.sortBy('margin')">Margin{{ camps.arrow('margin') }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in camps.view.value" :key="r.campaign">
              <td>{{ r.campaign }}</td><td class="n">{{ irr(r.revenue) }}</td>
              <td class="n" :class="r.margin >= 0 ? 'pos' : 'neg'">{{ pct(r.margin) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
