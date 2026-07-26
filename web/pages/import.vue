<script setup lang="ts">
const result = ref<any>(null);
const busy = ref(false);
const error = ref("");

async function upload(files: FileList | null) {
  if (!files || !files.length) return;
  busy.value = true; error.value = ""; result.value = null;
  const form = new FormData();
  form.append("file", files[0]);
  try {
    result.value = await apiFetch("/import/xlsx", { method: "POST", body: form });
  } catch (e: any) {
    error.value = e?.data?.detail || String(e);
  } finally {
    busy.value = false;
  }
}
function onDrop(e: DragEvent) { e.preventDefault(); upload(e.dataTransfer?.files || null); }
</script>

<template>
  <div>
    <h2>Import Workbook</h2>
    <div class="drop" @dragover.prevent @drop="onDrop">
      <p><strong>Drag & drop</strong> import_template.xlsx here, or</p>
      <input type="file" accept=".xlsx" @change="upload(($event.target as HTMLInputElement).files)" />
      <p v-if="busy" class="muted">Importing…</p>
    </div>

    <p v-if="error" class="neg">{{ error }}</p>

    <div v-if="result" class="panel" style="margin-top: 22px">
      <h3>Import Result</h3>
      <div class="kpis">
        <KpiCard label="Sales (SALE)" :value="String(result.inserted.SALE)" />
        <KpiCard label="Invoices (RECEIVABLE)" :value="String(result.inserted.RECEIVABLE)" />
        <KpiCard label="Suppliers (PAYABLE)" :value="String(result.inserted.PAYABLE)" />
        <KpiCard label="Total rows" :value="String(result.total)" />
      </div>
      <p class="muted">Job {{ result.job_id }} — {{ result.status }}</p>
      <div v-if="result.notes?.length">
        <h3>Notes</h3>
        <ul><li v-for="(n, i) in result.notes" :key="i" class="muted">{{ n }}</li></ul>
      </div>
    </div>
  </div>
</template>
