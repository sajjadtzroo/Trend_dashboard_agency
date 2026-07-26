<script setup lang="ts">
const route = useRoute();
const id = computed(() => route.params.id as string);
const { data, error, refresh: refreshInv } = useApi<any>(() => `/invoices/${id.value}`);
const { data: ledger, refresh: refreshLedger } = useApi<any>(() => `/invoices/${id.value}/payments`);
const { data: related } = useApi<any>(() => `/invoices/${id.value}/related`);

const inv = computed<any>(() => data.value || {});
const rate = (r: number | null | undefined) => (r == null ? "—" : pct(Number(r) * 100));

// [label, value] rows grouped into sections.
const identity = computed(() => [
  ["Invoice Number", inv.value.invoice_number || "—"],
  ["PO Number", inv.value.po_number || "—"],
  ["Clearance Certificate", inv.value.clearance_certificate || "—"],
  ["Status", inv.value.status || "—"],
  ["Source Row", inv.value.source_row || "—"],
]);
const party = computed(() => [
  ["Client", inv.value.client || "—"],
  ["National Code", inv.value.national_code || "—"],
  ["Category", inv.value.category || "—"],
  ["Brand", inv.value.brand || "—"],
  ["Project", [inv.value.project_code, inv.value.project_name].filter(Boolean).join(" — ") || "—"],
  ["Account", inv.value.account || "—"],
]);
const dates = computed(() => [
  ["Date (Jalali)", inv.value.jalali_date || "—"],
  ["Month", inv.value.jalali_month_name_fa || "—"],
  ["Date (Gregorian)", inv.value.gregorian_date || "—"],
]);
const money = computed(() => [
  ["Amount (Price)", irr(inv.value.amount)],
  ["VAT Rate", rate(inv.value.vat_rate)],
  ["VAT Amount", irr(inv.value.vat_amount)],
  ["Final Amount", irr(inv.value.final_amount)],
  ["Insurance Rate", rate(inv.value.insurance_rate)],
  ["Insurance Amount", irr(inv.value.insurance_amount)],
  ["Receivable", irr(inv.value.receivable)],
  ["Paid", irr(inv.value.amount_paid)],
  ["Balance", irr(inv.value.balance)],
]);

// ---- record a payment ----
const METHODS = ["Bank Transfer", "Cash", "Cheque", "POS", "Unknown"]; // dim_payment_method seed
const today = new Date().toISOString().slice(0, 10);
const form = reactive({ amount: null as number | null, paid_on: today, method: METHODS[0], note: "" });
const busy = ref(false);
const formErr = ref("");
const cfg = useRuntimeConfig();

const outstanding = computed(() => Number(ledger.value?.balance ?? inv.value.balance ?? 0));

async function submit() {
  formErr.value = "";
  if (!form.amount || form.amount <= 0) { formErr.value = "Enter a positive amount."; return; }
  busy.value = true;
  try {
    await apiFetch(`/invoices/${id.value}/payments`, { method: "POST", body: { ...form } });
    form.amount = null; form.note = "";
    await Promise.all([refreshLedger(), refreshInv()]);
  } catch (e: any) {
    formErr.value = e?.data?.detail || "Failed to record payment.";
  } finally {
    busy.value = false;
  }
}

async function removePayment(pid: number) {
  await apiFetch(`/invoices/${id.value}/payments/${pid}`, { method: "DELETE" });
  await Promise.all([refreshLedger(), refreshInv()]);
}
</script>

<template>
  <div>
    <p><NuxtLink to="/invoices" class="muted">← Invoices</NuxtLink></p>
    <h2>
      Invoice {{ inv.invoice_number || "#" + id }}
      <StatusChip v-if="inv.status" :status="inv.status" />
    </h2>
    <p v-if="error" class="neg">Failed to load. Is the API running?</p>

    <div class="grid2">
      <div class="panel">
        <h3>Identity</h3>
        <table><tbody>
          <tr v-for="[k, v] in identity" :key="k"><td class="muted">{{ k }}</td><td>{{ v }}</td></tr>
        </tbody></table>
      </div>
      <div class="panel">
        <h3>Party</h3>
        <table><tbody>
          <tr v-for="[k, v] in party" :key="k"><td class="muted">{{ k }}</td><td>{{ v }}</td></tr>
        </tbody></table>
      </div>
      <div class="panel">
        <h3>Date</h3>
        <table><tbody>
          <tr v-for="[k, v] in dates" :key="k"><td class="muted">{{ k }}</td><td>{{ v }}</td></tr>
        </tbody></table>
      </div>
      <div class="panel">
        <h3>Amounts</h3>
        <table><tbody>
          <tr v-for="[k, v] in money" :key="k"><td class="muted">{{ k }}</td><td class="n">{{ v }}</td></tr>
        </tbody></table>
      </div>
    </div>

    <!-- Payments ledger + record form -->
    <div class="panel">
      <h3>Payments</h3>
      <table>
        <thead><tr>
          <th style="text-align:left">Date</th><th style="text-align:left">Method</th>
          <th class="n">Amount</th><th class="n">Balance</th><th></th>
        </tr></thead>
        <tbody>
          <tr v-for="(p, i) in ledger?.rows || []" :key="p.payment_id ?? 'open'">
            <td>{{ p.label || p.paid_on || "—" }}</td>
            <td class="muted">{{ p.method || (p.label ? "" : "—") }}<span v-if="p.note" class="muted"> · {{ p.note }}</span></td>
            <td class="n">{{ irr(p.amount) }}</td>
            <td class="n">{{ irr(p.balance) }}</td>
            <td class="n">
              <button v-if="p.payment_id" class="link" title="Delete payment" @click="removePayment(p.payment_id)">✕</button>
            </td>
          </tr>
        </tbody>
        <tfoot v-if="ledger"><tr>
          <td class="muted" colspan="2">Total paid</td>
          <td class="n">{{ irr(ledger.total_paid) }}</td>
          <td class="n" :class="ledger.balance > 0 ? 'neg' : 'pos'">{{ irr(ledger.balance) }}</td>
          <td></td>
        </tr></tfoot>
      </table>

      <form class="pay-form" @submit.prevent="submit">
        <input v-model.number="form.amount" type="number" min="0" step="any" placeholder="Amount (IRR)" required />
        <input v-model="form.paid_on" type="date" :max="today" />
        <select v-model="form.method"><option v-for="m in METHODS" :key="m">{{ m }}</option></select>
        <input v-model="form.note" type="text" placeholder="Note (optional)" />
        <button class="btn" type="submit" :disabled="busy || outstanding <= 0">
          {{ busy ? "Saving…" : "Record payment" }}
        </button>
      </form>
      <p v-if="formErr" class="neg" style="margin:8px 0 0">{{ formErr }}</p>
      <p v-else-if="outstanding <= 0" class="muted" style="margin:8px 0 0">Fully paid — nothing outstanding.</p>
    </div>

    <!-- Related invoices for the same client -->
    <div v-if="related?.length" class="panel">
      <h3>Related invoices · same client</h3>
      <table>
        <thead><tr>
          <th style="text-align:left">Invoice</th><th style="text-align:left">Brand</th>
          <th style="text-align:left">Project</th><th style="text-align:left">Date</th>
          <th class="n">Final</th><th class="n">Balance</th><th>Status</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in related" :key="r.id">
            <td><NuxtLink :to="`/invoices/${r.id}`" class="link">{{ r.invoice_number || "#" + r.id }}</NuxtLink></td>
            <td>{{ r.brand || "—" }}<span v-if="r.same_brand" class="tag">same</span></td>
            <td>{{ r.project || "—" }}<span v-if="r.same_project" class="tag">same</span></td>
            <td>{{ r.jalali_date || "—" }}</td>
            <td class="n">{{ irr(r.final_amount) }}</td>
            <td class="n">{{ irr(r.balance) }}</td>
            <td><StatusChip v-if="r.status" :status="r.status" /></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.pay-form { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border); }
.pay-form input, .pay-form select { padding: 8px 12px; border: 1px solid var(--border); border-radius: 999px; background: #fff; color: var(--text); }
.pay-form input[type="number"] { width: 160px; }
.tag { margin-inline-start: 6px; font-size: 10px; color: var(--primary); background: var(--accent-surface); padding: 1px 7px; border-radius: 999px; }
tfoot td { border-top: 1px solid var(--border); font-weight: 600; }
</style>
