<script setup lang="ts">
import { columnsFor, exportCSV, exportXLSX, exportPDF, type Col } from "~/composables/useExport";

const props = defineProps<{
  rows: any[];
  name: string;
  columns?: Col[];
  title?: string;
}>();

const open = ref(false);
const cols = computed(() => props.columns?.length ? props.columns : columnsFor(props.rows || []));

function run(fmt: "csv" | "xlsx" | "pdf") {
  open.value = false;
  const rows = props.rows || [];
  if (!rows.length) return;
  if (fmt === "csv") exportCSV(rows, cols.value, props.name);
  else if (fmt === "xlsx") exportXLSX(rows, cols.value, props.name);
  else exportPDF(rows, cols.value, props.name, props.title || props.name);
}
</script>

<template>
  <div class="export" @focusout="open = false">
    <button class="btn" :disabled="!rows?.length" @click="open = !open" aria-haspopup="true" :aria-expanded="open">
      Export ▾
    </button>
    <div v-if="open" class="export-menu" role="menu">
      <button @mousedown.prevent="run('csv')">CSV</button>
      <button @mousedown.prevent="run('xlsx')">XLSX</button>
      <button @mousedown.prevent="run('pdf')">PDF</button>
    </div>
  </div>
</template>

<style scoped>
.export { position: relative; display: inline-block; }
.export-menu {
  position: absolute; right: 0; top: calc(100% + 4px); z-index: 30;
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  box-shadow: var(--shadow-md); padding: 4px; min-width: 120px; display: flex; flex-direction: column;
}
.export-menu button {
  text-align: start; padding: 8px 12px; border: none; background: none; cursor: pointer;
  border-radius: 8px; color: var(--text); font: inherit;
}
.export-menu button:hover { background: var(--surface); }
</style>
