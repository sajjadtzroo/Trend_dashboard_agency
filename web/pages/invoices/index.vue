<script setup lang="ts">
const { data: rows, pending } = useApi<any[]>("/invoices");
const { q, view, sortBy, arrow, count } = useGrid(rows, {
  sort: "jalali_date",
  keys: ["invoice_number", "po_number", "client", "brand", "project", "status"],
});
</script>

<template>
  <div>
    <h2>Invoices</h2>

    <div class="kpis">
      <KpiCard label="Invoices" icon="total" :value="String(rows?.length || 0)" />
      <KpiCard label="Total Invoiced" icon="ar" variant="dark" :value="irrC(sumBy(rows, 'amount'))" />
      <KpiCard label="Collected" icon="profit" :value="irrC(sumBy(rows, 'amount_paid'))" />
      <KpiCard label="Outstanding" icon="ar" :value="irrC(sumBy(rows, 'balance'))" />
    </div>

    <div class="panel">
      <div class="grid-toolbar">
        <input v-model="q" class="search" type="search" placeholder="Search invoice, client, brand…" aria-label="Search invoices" />
        <span class="count">{{ count }} of {{ rows?.length || 0 }} invoices</span>
        <GridExport :rows="view" name="invoices" title="Invoices" />
      </div>
      <Loadable :pending="pending" :empty="!rows?.length" empty-text="No invoices yet.">
        <table class="grid pin">
          <thead><tr>
            <th class="s" @click="sortBy('invoice_number')">Invoice #{{ arrow('invoice_number') }}</th>
            <th class="s" @click="sortBy('po_number')">PO{{ arrow('po_number') }}</th>
            <th class="s" @click="sortBy('client')">Client{{ arrow('client') }}</th>
            <th class="s" @click="sortBy('brand')">Brand{{ arrow('brand') }}</th>
            <th class="s" @click="sortBy('project')">Project{{ arrow('project') }}</th>
            <th class="s" @click="sortBy('jalali_date')">Date{{ arrow('jalali_date') }}</th>
            <th class="s n" @click="sortBy('amount')">Amount{{ arrow('amount') }}</th>
            <th class="s n" @click="sortBy('final_amount')">Final{{ arrow('final_amount') }}</th>
            <th class="s n" @click="sortBy('receivable')">Receivable{{ arrow('receivable') }}</th>
            <th class="s n" @click="sortBy('amount_paid')">Paid{{ arrow('amount_paid') }}</th>
            <th class="s n" @click="sortBy('balance')">Balance{{ arrow('balance') }}</th>
            <th class="s" @click="sortBy('status')">Status{{ arrow('status') }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in view" :key="r.id">
              <td>
                <a :href="`/invoices/${r.id}`" target="_blank" rel="noopener"
                   style="color: var(--primary); font-weight: 600">{{ r.invoice_number || "#" + r.id }}</a>
              </td>
              <td>{{ r.po_number || "—" }}</td>
              <td>{{ r.client || "—" }}</td>
              <td>{{ r.brand || "—" }}</td>
              <td>{{ r.project || "—" }}</td>
              <td>{{ r.jalali_date || "—" }}</td>
              <td class="n">{{ irr(r.amount) }}</td>
              <td class="n">{{ irr(r.final_amount) }}</td>
              <td class="n">{{ irr(r.receivable) }}</td>
              <td class="n">{{ irr(r.amount_paid) }}</td>
              <td class="n" :class="r.balance < 0 ? 'neg' : ''">{{ irr(r.balance) }}</td>
              <td><StatusChip v-if="r.status" :status="r.status" /><span v-else>—</span></td>
            </tr>
            <tr v-if="!view.length"><td colspan="12" class="table-empty">No invoices match “{{ q }}”.</td></tr>
          </tbody>
        </table>
      </Loadable>
    </div>
  </div>
</template>
