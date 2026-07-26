import { useFilters } from "~/stores/filters";

// Reactive GET that re-fetches when the path or shared filter params change.
export function useApi<T = any>(path: string | (() => string), extra: () => Record<string, any> = () => ({})) {
  const cfg = useRuntimeConfig();
  const filters = useFilters();
  const resolve = typeof path === "function" ? path : () => path;
  return useFetch<T>(() => `${cfg.public.apiBase}${resolve()}`, {
    query: computed(() => ({ ...filters.params, ...extra() })),
    watch: [() => filters.params, extra],
  });
}

// One-off imperative call (mutations, meta).
export function apiFetch<T = any>(path: string, opts: any = {}) {
  const cfg = useRuntimeConfig();
  return $fetch<T>(`${cfg.public.apiBase}${path}`, opts);
}

export const irr = (n: number | null | undefined) =>
  n == null ? "—" : new Intl.NumberFormat("en-US").format(Math.round(n));
// Compact form for KPI cards: 1.67B, 112B, 4.84B — B/M/K suffixes.
export const irrC = (n: number | null | undefined) =>
  n == null ? "—" : new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(n);
export const pct = (n: number | null | undefined) => (n == null ? "—" : n.toFixed(1) + "%");
// Sum a numeric field across a fetched array (for client-side KPI summary rows).
export const sumBy = (arr: any[] | null | undefined, k: string) =>
  (arr || []).reduce((s, r) => s + Number(r[k] || 0), 0);
