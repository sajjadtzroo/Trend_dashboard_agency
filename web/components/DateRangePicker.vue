<script setup lang="ts">
// Jalali month-range picker: a calendar-style popover (years × 12 months) plus
// quick presets. Data is monthly (YYYYMM), so cells are months, not days.
import { useFilters } from "~/stores/filters";
const filters = useFilters();

const open = ref(false);
const pendingStart = ref<number | null>(null); // first click of a new range
const hover = ref<number | null>(null);

const ym = (y: number, m: number) => y * 100 + m;
const fmt = (v: number | null) => (v == null ? "—" : `${Math.floor(v / 100)}/${String(v % 100).padStart(2, "0")}`);

// Months present in the data → available cells + preset anchors.
const present = computed(() =>
  [...new Set((filters.meta.months || []).map((m: any) => m.yyyymm))].sort((a, b) => a - b));
const has = (v: number) => present.value.includes(v);
const years = computed(() =>
  [...new Set(present.value.map((v) => Math.floor(v / 100)))].sort((a, b) => b - a));
const monthName = computed(() => {
  const map: Record<number, string> = {};
  for (const m of filters.meta.months || []) map[m.yyyymm] = m.jalali_month_name_fa;
  return map;
});

const label = computed(() => {
  const { date_from: f, date_to: t } = filters;
  if (f == null && t == null) return "All dates";
  return `${fmt(f)} – ${fmt(t)}`;
});
const active = computed(() => filters.date_from != null || filters.date_to != null);

// Range shading — during selection, the pending start pairs with the hovered cell.
const bounds = computed(() => {
  if (pendingStart.value != null) {
    const other = hover.value ?? pendingStart.value;
    return [Math.min(pendingStart.value, other), Math.max(pendingStart.value, other)];
  }
  if (filters.date_from != null && filters.date_to != null) return [filters.date_from, filters.date_to];
  if (filters.date_from != null) return [filters.date_from, filters.date_from];
  if (filters.date_to != null) return [filters.date_to, filters.date_to];
  return [Infinity, -Infinity];
});
const inRange = (v: number) => v >= bounds.value[0] && v <= bounds.value[1];
const isEnd = (v: number) => v === bounds.value[0] || v === bounds.value[1];

function pick(y: number, m: number) {
  const v = ym(y, m);
  if (pendingStart.value == null) { pendingStart.value = v; return; }
  filters.date_from = Math.min(pendingStart.value, v);
  filters.date_to = Math.max(pendingStart.value, v);
  pendingStart.value = null;
  open.value = false;
}

function preset(kind: string) {
  const pm = present.value, n = pm.length;
  if (!n) return;
  const latest = pm[n - 1], ly = Math.floor(latest / 100);
  const set = (f: number | null, t: number | null) => { filters.date_from = f; filters.date_to = t; };
  if (kind === "all") set(null, null);
  else if (kind === "3m") set(pm[Math.max(0, n - 3)], latest);
  else if (kind === "6m") set(pm[Math.max(0, n - 6)], latest);
  else if (kind === "ytd") set(ly * 100 + 1, latest);
  else if (kind === "ly") set((ly - 1) * 100 + 1, (ly - 1) * 100 + 12);
  pendingStart.value = null;
  open.value = false;
}

function clear() { filters.date_from = null; filters.date_to = null; pendingStart.value = null; }
</script>

<template>
  <div class="daterange">
    <span class="dr-cap">Date range</span>
    <button class="dr-trigger" :class="{ active }" @click="open = !open" aria-haspopup="dialog" :aria-expanded="open">
      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="17" rx="3" /><path d="M3 9h18M8 2v4M16 2v4" />
      </svg>
      <span>{{ label }}</span>
      <span v-if="active" class="dr-clear" role="button" aria-label="Clear date range" @click.stop="clear">✕</span>
    </button>

    <template v-if="open">
      <div class="dr-backdrop" @click="open = false" />
      <div class="dr-pop" role="dialog" aria-label="Pick a month range">
        <div class="dr-presets">
          <button @click="preset('all')">All</button>
          <button @click="preset('3m')">Last 3M</button>
          <button @click="preset('6m')">Last 6M</button>
          <button @click="preset('ytd')">YTD</button>
          <button @click="preset('ly')">Last Year</button>
        </div>
        <p class="dr-hint">{{ pendingStart == null ? "Click a start month" : "Click an end month" }}</p>
        <div class="dr-cal" @mouseleave="hover = null">
          <div v-for="y in years" :key="y" class="dr-year">
            <span class="dr-ylabel">{{ y }}</span>
            <div class="dr-months">
              <button v-for="m in 12" :key="m" class="dr-cell"
                :class="{ 'in-range': has(ym(y, m)) && inRange(ym(y, m)), end: isEnd(ym(y, m)) && inRange(ym(y, m)) }"
                :disabled="!has(ym(y, m))" :title="monthName[ym(y, m)] || ''"
                @click="pick(y, m)" @mouseenter="hover = ym(y, m)">{{ String(m).padStart(2, '0') }}</button>
            </div>
          </div>
          <p v-if="!years.length" class="table-empty">No dated data.</p>
        </div>
      </div>
    </template>
  </div>
</template>
