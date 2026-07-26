// Download a chart as PNG (native), its data as CSV (native), or SVG vector
// (re-render Chart.js into an svgcanvas 2D context). getRef() returns the
// vue-chartjs component instance whose `.chart` is the live Chart.js instance.
import { exportCSV, type Col } from "~/composables/useExport";

type ChartType = "bar" | "line" | "doughnut";

function anchor(href: string, filename: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
}

export function useChartExport(getRef: () => any, type: ChartType, getData: () => any) {
  function downloadPNG(name = "chart") {
    const chart = getRef()?.chart;
    if (!chart) return;
    anchor(chart.toBase64Image("image/png", 1), name + ".png");
  }

  function downloadDataCSV(name = "chart") {
    const d = getData() || {};
    const labels: any[] = d.labels || [];
    const sets: any[] = d.datasets || [];
    const cols: Col[] = [{ key: "label", label: "Label" },
      ...sets.map((s, i) => ({ key: "s" + i, label: s.label || `Series ${i + 1}` }))];
    const rows = labels.map((lab, i) => {
      const row: any = { label: lab };
      sets.forEach((s, si) => (row["s" + si] = s.data?.[i]));
      return row;
    });
    exportCSV(rows, cols, name);
  }

  async function downloadSVG(name = "chart") {
    const chart = getRef()?.chart;
    if (!chart) return;
    const { Context } = await import("svgcanvas");
    const { Chart } = await import("chart.js/auto");
    const w = chart.width || 640, h = chart.height || 360;
    const ctx: any = new Context(w, h);
    // svgcanvas needs a canvas-like host; give Chart.js the shim + a matching size.
    const svgChart = new Chart(ctx, {
      type,
      data: JSON.parse(JSON.stringify(getData() || {})),
      options: { ...chart.options, responsive: false, animation: false, devicePixelRatio: 1, width: w, height: h },
    });
    const svg = ctx.getSerializedSvg(true);
    svgChart.destroy();
    anchor("data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg), name + ".svg");
  }

  return { downloadPNG, downloadDataCSV, downloadSVG };
}
