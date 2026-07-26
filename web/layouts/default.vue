<script setup lang="ts">
import { useFilters } from "~/stores/filters";

const filters = useFilters();
const route = useRoute();

// Lucide-style glyphs (stroked paths) so nav is scannable, matching the KPI icons.
const groups = [
  { grp: null, items: [
    { to: "/", label: "Overview", icon: "M3 3h8v9H3zM13 3h8v5h-8zM13 12h8v9h-8zM3 16h8v5H3z" },
    { to: "/invoices", label: "Invoices", icon: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 13h6M9 17h6" },
    { to: "/receivables", label: "Receivables", icon: "M12 3v12M7 10l5 5 5-5M5 21h14" },
    { to: "/payables", label: "Payables", icon: "M12 21V9M7 14l5-5 5 5M5 3h14" },
    { to: "/brands", label: "Brands", icon: "M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8zM7 7h.01" },
    { to: "/financials", label: "Financials (FP&A)", icon: "M3 3v18h18M8 17v-5M13 17V8M18 17v-9" },
  ] },
  { grp: "Manage", items: [
    { to: "/manage/campaigns", label: "Campaigns", icon: "M3 11v2a1 1 0 0 0 1 1h3l4 4V6L7 10H4a1 1 0 0 0-1 1zM15 8a4 4 0 0 1 0 8" },
    { to: "/manage/projects", label: "Projects", icon: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" },
    { to: "/manage/users", label: "Users / Managers", icon: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" },
    { to: "/manage/media", label: "Media", icon: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20M10 8l6 4-6 4z" },
  ] },
  { grp: "Data", items: [
    { to: "/import", label: "Import", icon: "M12 15V3M7 8l5-5 5 5M4 21h16" },
  ] },
];

// Highlight the parent nav item on its detail pages too (exact match only for root).
const isActive = (to: string) => (to === "/" ? route.path === "/" : route.path === to || route.path.startsWith(to + "/"));

// Collapsible rail — reclaim chart width on demand; remembered across visits.
const collapsed = ref(false);
onMounted(() => { collapsed.value = localStorage.getItem("sidebar-collapsed") === "1"; });
function toggleCollapse() {
  collapsed.value = !collapsed.value;
  localStorage.setItem("sidebar-collapsed", collapsed.value ? "1" : "0");
}

// load filter options once
const { data: meta } = await useAsyncData("meta", () =>
  apiFetch("/meta").catch(() => ({ clients: [], services: [], users: [], months: [] })),
);
if (meta.value) filters.meta = meta.value;
</script>

<template>
  <div class="layout" :class="{ collapsed }">
    <aside>
      <div class="brand">
        <span class="mark">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
            stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 6 9 17l-5-5" />
          </svg>
        </span>
        <h1>Creative Lab</h1>
        <button class="collapse-btn" :aria-label="collapsed ? 'Expand sidebar' : 'Collapse sidebar'"
          :aria-pressed="collapsed" @click="toggleCollapse">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
            stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M15 6l-6 6 6 6" />
          </svg>
        </button>
      </div>
      <div class="sub">Finance Dashboard · IRR</div>
      <nav>
        <template v-for="(g, gi) in groups" :key="gi">
          <div v-if="g.grp" class="grp">{{ g.grp }}</div>
          <NuxtLink v-for="l in g.items" :key="l.to" :to="l.to" class="link"
            :class="{ active: isActive(l.to) }" :title="collapsed ? l.label : undefined">
            <svg class="nav-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path :d="l.icon" /></svg>
            <span class="lbl">{{ l.label }}</span>
          </NuxtLink>
        </template>
      </nav>
    </aside>
    <main>
      <div class="bar">
        <label>Client
          <select v-model="filters.client">
            <option value="">All clients</option>
            <option v-for="c in filters.meta.clients" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <label>Service
          <select v-model="filters.service">
            <option value="">All services</option>
            <option v-for="s in filters.meta.services" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>User
          <select v-model="filters.user">
            <option value="">All users</option>
            <option v-for="u in filters.meta.users" :key="u" :value="u">{{ u }}</option>
          </select>
        </label>
        <DateRangePicker />
        <button @click="filters.reset()">Reset</button>
      </div>
      <slot />
    </main>
  </div>
</template>
