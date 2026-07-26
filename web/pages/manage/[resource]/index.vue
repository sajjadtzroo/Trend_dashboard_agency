<script setup lang="ts">
const route = useRoute();
const resource = computed(() => route.params.resource as string);
const titles: Record<string, string> = {
  campaigns: "Campaigns", projects: "Projects", users: "Users / Managers", media: "Media",
};

const { data: rows, refresh } = useApi<any[]>(() => `/manage/${resource.value}`);

const MONEY = new Set(["revenue", "cost", "profit", "total", "balance", "paid", "receivable", "final_amount", "amount"]);
const HIDE = new Set(["id"]);
const columns = computed(() => {
  const first = rows.value?.[0];
  return first ? Object.keys(first).filter((k) => !HIDE.has(k)) : [];
});
const isNum = (k: string) => MONEY.has(k) || k === "margin" || k === "rows" || k === "campaigns";
const fmt = (k: string, v: any) => (v == null ? "—" : k === "margin" ? pct(v) : MONEY.has(k) ? irr(v) : v);
// campaigns/users/projects/media all support a drill-in detail page
const drillable = computed(() => ["campaigns", "users", "projects", "media"].includes(resource.value));

const { q, view, sortBy, arrow, count } = useGrid(rows, { sort: "name", dir: 1, keys: ["name"] });

async function rename(row: any) {
  const name = prompt("New name:", row.name);
  if (!name || name === row.name) return;
  await apiFetch(`/manage/${resource.value}/${row.id}`, { method: "PATCH", body: { name } });
  refresh();
}
async function remove(row: any) {
  if (!confirm(`Delete "${row.name}"? (soft-deletes if referenced by transactions)`)) return;
  const r = await apiFetch<any>(`/manage/${resource.value}/${row.id}`, { method: "DELETE" });
  alert(`${r.mode}-deleted (${r.references} references)`);
  refresh();
}
</script>

<template>
  <div>
    <h2>{{ titles[resource] || resource }}</h2>
    <p class="muted">CRUD on the dimension. Click a name to drill in. Delete soft-removes referenced rows.</p>
    <div class="panel">
      <div class="grid-toolbar">
        <input v-model="q" class="search" type="search" placeholder="Search name…" aria-label="Search" />
        <span class="count">{{ count }} of {{ rows?.length || 0 }}</span>
      </div>
      <table class="grid pin">
        <thead><tr>
          <th v-for="c in columns" :key="c" class="s" :class="{ n: isNum(c) }" @click="sortBy(c)">{{ c }}{{ arrow(c) }}</th>
          <th></th>
        </tr></thead>
        <tbody>
          <tr v-for="row in view" :key="row.id">
            <td v-for="c in columns" :key="c" :class="{ n: isNum(c) }">
              <NuxtLink v-if="c === 'name' && drillable" :to="`/manage/${resource}/${row.id}`"
                style="color: var(--primary); font-weight: 600">{{ row[c] }}</NuxtLink>
              <template v-else>{{ fmt(c, row[c]) }}</template>
            </td>
            <td class="n" style="white-space: nowrap">
              <button class="btn" @click="rename(row)">Edit</button>
              <button class="btn danger" @click="remove(row)">Delete</button>
            </td>
          </tr>
          <tr v-if="!view.length"><td :colspan="columns.length + 1" class="table-empty">No rows match “{{ q }}”.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
