<script setup lang="ts">
// Distinguishes loading from empty so pages never flash "No data" while fetching.
defineProps<{ pending?: boolean; empty?: boolean; emptyText?: string }>();
</script>

<template>
  <div v-if="pending" class="skeleton" aria-busy="true" />
  <div v-else-if="empty" class="empty">{{ emptyText || "No data yet." }}</div>
  <slot v-else />
</template>
