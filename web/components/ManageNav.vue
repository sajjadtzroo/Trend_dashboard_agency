<script setup lang="ts">
// Secondary nav for the Manage section — gives context + one-click switching.
const route = useRoute();
const items = [
  { to: "/manage/campaigns", label: "Campaigns" },
  { to: "/manage/projects", label: "Projects" },
  { to: "/manage/users", label: "Users" },
  { to: "/manage/media", label: "Media" },
];
</script>

<template>
  <nav class="tabs manage-nav" aria-label="Manage sections">
    <NuxtLink v-for="i in items" :key="i.to" :to="i.to" :class="{ active: route.path === i.to }">{{ i.label }}</NuxtLink>
  </nav>
</template>

<style scoped>
.manage-nav a{
  padding:8px 18px;border:1px solid var(--border);background:#fff;border-radius:var(--radius-sm);
  color:var(--muted);cursor:pointer;transition:background .15s ease,color .15s ease;text-decoration:none;
}
.manage-nav a:hover{background:var(--surface);color:var(--ink)}
.manage-nav a.active{background:var(--ink);color:#fff;border-color:var(--ink);box-shadow:var(--shadow-sm)}
</style>
