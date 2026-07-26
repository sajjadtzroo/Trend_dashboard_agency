// Client-side grid export: CSV (native), XLSX (SheetJS), PDF (jsPDF + autotable).
// Heavy libs are lazy-imported inside handlers so they stay out of the SSR build
// and the initial bundle. Source is always the grid's current `view` (filtered+sorted).
export type Col = { key: string; label: string };

const titleCase = (k: string) =>
  k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export function columnsFor(rows: any[], omit: string[] = ["id"]): Col[] {
  const first = rows?.[0];
  if (!first) return [];
  return Object.keys(first).filter((k) => !omit.includes(k)).map((k) => ({ key: k, label: titleCase(k) }));
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const cell = (v: any) => (v == null ? "" : v);

export function exportCSV(rows: any[], cols: Col[], name: string) {
  const esc = (v: any) => {
    const s = String(cell(v));
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const head = cols.map((c) => esc(c.label)).join(",");
  const body = rows.map((r) => cols.map((c) => esc(r[c.key])).join(",")).join("\n");
  download(new Blob(["﻿" + head + "\n" + body], { type: "text/csv;charset=utf-8" }), name + ".csv");
}

export async function exportXLSX(rows: any[], cols: Col[], name: string) {
  const XLSX = await import("xlsx");
  const records = rows.map((r) => Object.fromEntries(cols.map((c) => [c.label, cell(r[c.key])])));
  const ws = XLSX.utils.json_to_sheet(records, { header: cols.map((c) => c.label) });
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Data");
  XLSX.writeFile(wb, name + ".xlsx");
}

const MONEYISH = /amount|revenue|cost|profit|balance|receivable|paid|final|total|price|vat|insurance/i;

export async function exportPDF(rows: any[], cols: Col[], name: string, title?: string) {
  const { jsPDF } = await import("jspdf");
  const autoTable = (await import("jspdf-autotable")).default;
  const doc = new jsPDF({ orientation: cols.length > 6 ? "landscape" : "portrait" });
  if (title) doc.text(title, 14, 14);
  autoTable(doc, {
    startY: title ? 20 : 14,
    head: [cols.map((c) => c.label)],
    body: rows.map((r) => cols.map((c) => String(cell(r[c.key])))),
    styles: { fontSize: 8, cellPadding: 2 },
    headStyles: { fillColor: [46, 125, 50] },
    // right-align money columns
    columnStyles: Object.fromEntries(
      cols.map((c, i) => [i, MONEYISH.test(c.key) ? { halign: "right" } : {}]),
    ),
  });
  doc.save(name + ".pdf");
}
