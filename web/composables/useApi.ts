import { useFilters } from "~/stores/filters";

// One shared in-flight /auth/refresh, so N parallel 401s trigger ONE rotation
// (five concurrent refreshes would invalidate each other).
let inflight: Promise<any> | null = null;
function refreshOnce() {
  const base = useRuntimeConfig().public.apiBase;
  if (!inflight) {
    inflight = $fetch(`${base}/auth/refresh`, { method: "POST", credentials: "include" })
      .finally(() => { inflight = null; });
  }
  return inflight;
}

// On a 401 for a data request, silently refresh once (ofetch then retries via
// retryStatusCodes); if refresh fails, the session is gone → go to /login.
// Auth endpoints are skipped so login/refresh/me never loop or double-count.
async function onAuthError(ctx: any) {
  const url = String(ctx.request || "");
  if (ctx.response?.status !== 401 || url.includes("/auth/")) return;
  try {
    await refreshOnce();
  } catch {
    if (import.meta.client) {
      useAuthStore().user = null;
      await navigateTo(`/login?redirect=${encodeURIComponent(useRoute().fullPath)}`);
    }
  }
}

// Reactive GET that re-fetches when the path or shared filter params change.
export function useApi<T = any>(path: string | (() => string), extra: () => Record<string, any> = () => ({})) {
  const cfg = useRuntimeConfig();
  const filters = useFilters();
  const resolve = typeof path === "function" ? path : () => path;
  return useFetch<T>(() => `${cfg.public.apiBase}${resolve()}`, {
    query: computed(() => ({ ...filters.params, ...extra() })),
    watch: [() => filters.params, extra],
    credentials: "include",
    retry: 1, retryStatusCodes: [401],
    onResponseError: onAuthError,
  });
}

// One-off imperative call (mutations, meta, auth). Auth calls skip the retry so a
// failed login isn't attempted twice (and double-charged against the rate limit).
export function apiFetch<T = any>(path: string, opts: any = {}) {
  const cfg = useRuntimeConfig();
  const isAuth = path.startsWith("/auth");
  return $fetch<T>(`${cfg.public.apiBase}${path}`, {
    credentials: "include",
    retry: isAuth ? 0 : 1, retryStatusCodes: [401],
    onResponseError: onAuthError,
    ...opts,
  });
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
// Tidy source-data typos in order-status labels for display (data itself is untouched).
export const statusLabel = (s: string | null | undefined) =>
  s === "Opportuinity" ? "Opportunity" : (s || "—");
