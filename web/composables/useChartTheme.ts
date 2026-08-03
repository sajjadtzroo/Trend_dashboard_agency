// Shared Chart.js theming — pastel/green palette, rounded bars, compact-IRR axes,
// full-IRR tooltips, reduced-motion aware. Pages only build {labels, datasets}.

const full = new Intl.NumberFormat("en-US");

// Compact IRR for axis ticks & big labels: 1.98T / 701.8B / 36M / 12K.
export function irrCompact(n: number | null | undefined): string {
  if (n == null) return "—";
  const a = Math.abs(n), s = n < 0 ? "-" : "";
  if (a >= 1e12) return `${s}${(a / 1e12).toFixed(2)}T`;
  if (a >= 1e9) return `${s}${(a / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${s}${(a / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${s}${(a / 1e3).toFixed(0)}K`;
  return `${s}${a}`;
}
const irrFull = (n: number | null | undefined) => (n == null ? "—" : full.format(Math.round(n)));

// Monochrome + single green accent: green = primary series, everything else a grey ramp.
// (Legacy names mint/coral/yellow/lavender/amber kept so existing pages resolve, now greys.)
export const palette = {
  green: "#2E7D32", accent: "#71717A", grey: "#A1A1AA",
  mint: "#3F3F46", coral: "#A1A1AA", yellow: "#D4D4D8", lavender: "#52525B", amber: "#71717A",
  neg: "#52525B",
};
// Wide luminance steps so adjacent slices/series stay distinguishable (green + 4 spaced greys).
export const series = [palette.green, "#18181B", "#52525B", "#A1A1AA", "#D4D4D8", "#E4E4E7"];

const reduced = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const GRID = "#e6ebed";
const base = () => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: reduced() ? (false as const) : { duration: 500, easing: "easeOutQuart" as const },
  elements: { bar: { borderRadius: 6, borderSkipped: false as const } },
  // Hover anywhere along a category shows every series' value (not just the bar you're on).
  interaction: { mode: "index" as const, intersect: false },
  plugins: {
    legend: { position: "bottom" as const, labels: { usePointStyle: true, boxWidth: 8, padding: 16 } },
    tooltip: {
      backgroundColor: "#263238", padding: 10, cornerRadius: 10, displayColors: true,
      callbacks: {
        label: (ctx: any) => {
          const v = ctx.parsed?.y ?? ctx.parsed?.x ?? ctx.parsed;
          const name = ctx.dataset?.label || ctx.label || "";
          return ` ${name}${name ? ": " : ""}${irrFull(v)}`;
        },
      },
    },
  },
});

const valueAxis = () => ({ beginAtZero: true, grid: { color: GRID, drawBorder: false }, ticks: { callback: (v: any) => irrCompact(v) } });
const catAxis = () => ({ grid: { display: false }, ticks: { autoSkip: true, maxRotation: 0 } });

export function barOptions(opts: { horizontal?: boolean; stacked?: boolean } = {}) {
  const o: any = base();
  o.indexAxis = opts.horizontal ? "y" : "x";
  const vKey = opts.horizontal ? "x" : "y";
  const cKey = opts.horizontal ? "y" : "x";
  o.scales = { [vKey]: { ...valueAxis(), stacked: !!opts.stacked }, [cKey]: { ...catAxis(), stacked: !!opts.stacked } };
  return o;
}

export function lineOptions() {
  const o: any = base();
  o.scales = { y: valueAxis(), x: catAxis() };
  return o;
}

export function doughnutOptions() {
  const o: any = base();
  o.cutout = "62%";
  o.interaction = { mode: "nearest", intersect: true };   // per-slice hover
  o.plugins.legend.position = "right";
  o.plugins.tooltip.callbacks.label = (ctx: any) => ` ${ctx.label}: ${irrFull(ctx.parsed)}`;
  return o;
}

// Sankey flow diagram. `money`=true formats flows as IRR, else as plain counts.
export function sankeyOptions(money = true) {
  const o: any = base();
  o.interaction = { mode: "nearest", intersect: true };   // per-flow hover
  o.plugins.legend.display = false;
  const fmt = (v: number) => (money ? irrFull(v) : String(Math.round(v)));
  o.plugins.tooltip.callbacks.label = (ctx: any) =>
    ` ${ctx.dataset.data[ctx.dataIndex].from} → ${ctx.dataset.data[ctx.dataIndex].to}: ${fmt(ctx.parsed?.flow ?? ctx.raw?.flow ?? 0)}`;
  return o;
}
