<script setup lang="ts">
const route = useRoute();
const id = computed(() => route.params.id as string);
const { data, error } = useApi<any>(() => `/invoices/${id.value}`);

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
  </div>
</template>
