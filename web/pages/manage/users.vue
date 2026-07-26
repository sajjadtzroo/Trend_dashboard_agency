<script setup lang="ts">
import { palette, series } from "~/composables/useChartTheme";
const { data: rows, pending } = useApi<any[]>("/manage/users");
const rev = computed(() => sumBy(rows.value, "revenue"));
const prof = computed(() => sumBy(rows.value, "profit"));
const { q, view, sortBy, arrow, count } = useGrid(rows, { sort: "revenue", keys: ["name", "role"] });
const chart = computed(() => {
  const list = rows.value || [];
  return {
    labels: list.map((r) => r.name),
    datasets: [
      { label: "Revenue", data: list.map((r) => r.revenue), backgroundColor: palette.green },
      { label: "Profit", data: list.map((r) => r.profit), backgroundColor: palette.mint },
    ],
  };
});
// Revenue share by account — who carries the book.
const share = computed(() => {
  const list = [...(rows.value || [])].sort((a, b) => b.revenue - a.revenue);
  return { labels: list.map((r) => r.name),
    datasets: [{ data: list.map((r) => r.revenue), backgroundColor: series, borderWidth: 0 }] };
});
// Margin % per account — efficiency, not just volume.
const marginBar = computed(() => {
  const list = [...(rows.value || [])].filter((r) => r.margin != null).sort((a, b) => b.margin - a.margin);
  return { labels: list.map((r) => r.name),
    datasets: [{ label: "Margin %", data: list.map((r) => r.margin), backgroundColor: palette.accent }] };
});
// Activity — transaction rows handled per account (workload).
const activityBar = computed(() => {
  const list = [...(rows.value || [])].sort((a, b) => b.rows - a.rows);
  return { labels: list.map((r) => r.name),
    datasets: [{ label: "Transactions", data: list.map((r) => r.rows), backgroundColor: palette.grey }] };
});
</script>

<template>
  <div>
    <h2>Users / Managers</h2>
    <div class="kpis">
      <KpiCard label="Total Revenue" icon="revenue" variant="dark" :value="irrC(rev)" />
      <KpiCard label="Total Profit" icon="profit" :value="irrC(prof)" :tone="prof >= 0 ? 'pos' : 'neg'" />
      <KpiCard label="Avg Margin" icon="margin" :value="pct(rev ? (prof / rev) * 100 : null)" />
      <KpiCard label="Team Members" icon="total" :value="String(rows?.length || 0)" />
    </div>
    <div class="grid2">
      <div class="panel">
        <h3>Revenue &amp; Profit by Account</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No users yet.">
          <ChartBar :data="chart" aria-label="Revenue and profit by user" />
        </Loadable>
      </div>
      <div class="panel">
        <h3>Revenue Share</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No users yet.">
          <ChartDoughnut :data="share" name="users-revenue-share" aria-label="Revenue share by account" />
        </Loadable>
      </div>
    </div>
    <div class="grid2">
      <div class="panel">
        <h3>Margin by Account</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No users yet.">
          <ChartBar :data="marginBar" horizontal name="users-margin" aria-label="Profit margin percent by account" />
        </Loadable>
      </div>
      <div class="panel">
        <h3>Activity by Account</h3>
        <Loadable :pending="pending" :empty="!rows?.length" empty-text="No users yet.">
          <ChartBar :data="activityBar" horizontal name="users-activity" aria-label="Transaction count by account" />
        </Loadable>
      </div>
    </div>
    <div class="panel">
      <div class="grid-toolbar">
        <input v-model="q" class="search" type="search" placeholder="Search account, role…" aria-label="Search users" />
        <span class="count">{{ count }} of {{ rows?.length || 0 }} users</span>
        <GridExport :rows="view" name="users" title="Users / Managers" />
      </div>
      <table class="grid pin">
        <thead><tr>
          <th class="s" @click="sortBy('name')">Account{{ arrow('name') }}</th>
          <th class="s" @click="sortBy('role')">Role{{ arrow('role') }}</th>
          <th class="s n" @click="sortBy('revenue')">Revenue{{ arrow('revenue') }}</th>
          <th class="s n" @click="sortBy('profit')">Profit{{ arrow('profit') }}</th>
          <th class="s n" @click="sortBy('margin')">Margin{{ arrow('margin') }}</th>
          <th class="s n" @click="sortBy('rows')">Rows{{ arrow('rows') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in view" :key="r.id">
            <td>{{ r.name }}</td><td>{{ r.role || "—" }}</td>
            <td class="n">{{ irr(r.revenue) }}</td><td class="n">{{ irr(r.profit) }}</td>
            <td class="n" :class="r.margin >= 0 ? 'pos' : 'neg'">{{ pct(r.margin) }}</td>
            <td class="n">{{ r.rows }}</td>
          </tr>
          <tr v-if="!view.length"><td colspan="6" class="table-empty">No users match “{{ q }}”.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
