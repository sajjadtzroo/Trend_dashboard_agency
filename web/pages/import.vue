<script setup lang="ts">
const result = ref<any>(null);
const busy = ref(false);
const error = ref("");
const gbusy = ref(false);

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

// Live pull from the configured Google Sheet (Sales-Funnel tab).
async function syncSheet() {
  gbusy.value = true; error.value = ""; result.value = null;
  try {
    result.value = await apiFetch("/import/gsheet", { method: "POST" });
  } catch (e: any) {
    error.value = e?.data?.detail || String(e);
  } finally {
    gbusy.value = false;
  }
}
</script>

<template>
  <div>
    <h2>Import Data</h2>

    <div class="panel gsync">
      <span class="chip-icon ic-green" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round">
          <rect x="4" y="3" width="16" height="18" rx="2" /><path d="M4 9h16M4 15h16M10 3v18" />
        </svg>
      </span>
      <div class="gsync-txt">
        <strong>Google Sheet — live sync</strong>
        <p class="muted">Pull the latest “1405 Sales Funnel” tab and refresh the dashboard.</p>
      </div>
      <button class="btn gsync-btn" :disabled="gbusy" @click="syncSheet">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="{ spin: gbusy }">
          <path d="M21 12a9 9 0 1 1-3-6.7M21 4v4h-4" />
        </svg>
        {{ gbusy ? "Syncing…" : "Update from Google Sheet" }}
      </button>
    </div>

    <h3 style="margin:0 0 10px">Or upload a workbook</h3>
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
