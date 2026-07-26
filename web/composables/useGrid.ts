// Client-side grid behaviour shared by every list table: text search, click-to-sort,
// and a live row count. Pages keep their own cell markup — this only owns the logic.
import { ref, computed, unref, type Ref } from "vue";

type Src<T> = Ref<T[] | null | undefined> | (() => T[] | null | undefined);

export function useGrid<T extends Record<string, any>>(
  source: Src<T>,
  opts: { sort?: string; dir?: 1 | -1; keys?: string[] } = {},
) {
  const q = ref("");
  const sortKey = ref(opts.sort || "");
  const sortDir = ref<1 | -1>(opts.dir ?? -1); // -1 = desc (biggest first, the useful default)

  const rows = computed<T[]>(() => (typeof source === "function" ? source() : unref(source)) || []);

  function sortBy(k: string) {
    if (sortKey.value === k) sortDir.value = (sortDir.value * -1) as 1 | -1;
    else { sortKey.value = k; sortDir.value = -1; }
  }
  // ▼ desc / ▲ asc on the active column, blank otherwise
  const arrow = (k: string) => (sortKey.value !== k ? "" : sortDir.value === 1 ? " ▲" : " ▼");

  const view = computed<T[]>(() => {
    let r = rows.value;
    const term = q.value.trim().toLowerCase();
    if (term) {
      r = r.filter((row) => {
        const vals = opts.keys ? opts.keys.map((k) => row[k]) : Object.values(row);
        return vals.some((v) => v != null && String(v).toLowerCase().includes(term));
      });
    }
    if (sortKey.value) {
      const k = sortKey.value, d = sortDir.value;
      r = [...r].sort((a, b) => {
        const x = a[k], y = b[k];
        if (typeof x === "number" && typeof y === "number") return (x - y) * d;
        return String(x ?? "").localeCompare(String(y ?? "")) * d;
      });
    }
    return r;
  });

  return { q, view, sortBy, arrow, sortKey, sortDir, count: computed(() => view.value.length) };
}
