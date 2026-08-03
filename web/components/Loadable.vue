<script setup lang="ts">
// Distinguishes loading from empty so pages never flash "No data" while fetching.
defineProps<{ pending?: boolean; empty?: boolean; emptyText?: string }>();
</script>

<template>
  <div v-if="pending" class="skeleton" aria-busy="true" />
  <div v-else-if="empty" class="empty">
    <svg class="empty-ic" viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor"
      stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M3 3v18h18M8 15l3-3 3 2 4-5" />
    </svg>
    <span>{{ emptyText || "No data yet." }}</span>
  </div>
  <slot v-else />
</template>
