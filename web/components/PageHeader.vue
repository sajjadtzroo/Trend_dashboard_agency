<script setup lang="ts">
// Consistent page title zone: optional breadcrumb (for drill-ins) + right-aligned actions slot.
defineProps<{ title: string; breadcrumb?: { label: string; to?: string }[] }>();
</script>

<template>
  <div class="page-head">
    <div class="page-head-main">
      <nav v-if="breadcrumb?.length" class="crumbs" aria-label="Breadcrumb">
        <template v-for="(c, i) in breadcrumb" :key="i">
          <NuxtLink v-if="c.to" :to="c.to">{{ c.label }}</NuxtLink>
          <span v-else>{{ c.label }}</span>
          <span v-if="i < breadcrumb.length - 1" class="sep">›</span>
        </template>
      </nav>
      <h2>{{ title }}</h2>
    </div>
    <div v-if="$slots.actions" class="head-actions"><slot name="actions" /></div>
  </div>
</template>

<style scoped>
.page-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:20px}
.page-head-main h2{margin:0}
.crumbs{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);margin-bottom:6px}
.crumbs a{color:var(--muted)}
.crumbs a:hover{color:var(--primary)}
.crumbs .sep{color:var(--grey-300)}
.head-actions{display:flex;gap:8px;align-items:center}
</style>
