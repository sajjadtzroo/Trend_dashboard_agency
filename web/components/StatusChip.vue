<script setup lang="ts">
defineProps<{ status: string }>();
</script>

<template>
  <span class="chip" :class="status">{{ status }}</span>
</template>
