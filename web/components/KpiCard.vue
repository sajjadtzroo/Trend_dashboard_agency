<script setup lang="ts">
const props = defineProps<{ label: string; value: string; tone?: "pos" | "neg"; variant?: string;
  icon?: string; delta?: number | null; invert?: boolean }>();

// "good" direction: revenue/profit up = good; cost up (invert) = bad.
const good = computed(() => props.delta == null ? null : (props.invert ? props.delta <= 0 : props.delta >= 0));

// tiny inline Lucide-style glyphs (no emoji, no deps)
const paths: Record<string, string> = {
  revenue: "M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6",
  cost: "M3 3v18h18M7 14l4-4 4 4 5-5",
  profit: "M3 17l6-6 4 4 8-8M21 7v6h-6",
  margin: "M20 12a8 8 0 1 1-8-8v8z",
  ar: "M4 4h16v12H4zM4 20h16",
  ap: "M20 4H4v12h16zM4 20h16",
  total: "M4 6h16M4 12h16M4 18h10",
};
const cls: Record<string, string> = {
  revenue: "ic-green", cost: "ic-coral", profit: "ic-green", margin: "ic-lav", ar: "ic-yellow", ap: "ic-coral", total: "ic-green",
};
</script>

<template>
  <div class="card" :class="variant ? `card--${variant}` : ''">
    <div class="k">
      <span v-if="icon" class="chip-icon" :class="cls[icon] || 'ic-green'">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round"><path :d="paths[icon]" /></svg>
      </span>
      {{ label }}
    </div>
    <div class="v" :class="tone">{{ value }}</div>
    <div v-if="delta != null" class="delta" :class="good ? 'pos' : 'neg'">
      {{ delta >= 0 ? "▲" : "▼" }} {{ Math.abs(delta).toFixed(1) }}%
      <span class="delta-note">vs prior yr</span>
    </div>
  </div>
</template>
