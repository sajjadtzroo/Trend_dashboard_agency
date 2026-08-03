<script setup lang="ts">
import { Chart } from "vue-chartjs";
import { Chart as ChartJS, Tooltip } from "chart.js";
import { SankeyController, Flow } from "chartjs-chart-sankey";
import { sankeyOptions } from "~/composables/useChartTheme";
import { useChartExport } from "~/composables/useChartExport";
ChartJS.register(SankeyController, Flow, Tooltip);

const props = defineProps<{ data: any; money?: boolean; name?: string }>();
const options = computed(() => sankeyOptions(props.money !== false));

const c = ref();
const { downloadPNG, downloadDataCSV, downloadSVG } = useChartExport(() => c.value, "sankey", () => props.data);
const file = computed(() => props.name || "sankey");
</script>

<template>
  <div class="chart-box" style="height:360px">
    <div class="chart-dl">
      <button title="Download PNG" @click="downloadPNG(file)">PNG</button>
      <button title="Download data (CSV)" @click="downloadDataCSV(file)">CSV</button>
      <button title="Download SVG" @click="downloadSVG(file)">SVG</button>
    </div>
    <Chart ref="c" type="sankey" :data="data" :options="options" />
  </div>
</template>
