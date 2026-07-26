<script setup lang="ts">
import { Line } from "vue-chartjs";
import {
  Chart as ChartJS, Title, Tooltip, Legend, PointElement, LineElement, CategoryScale, LinearScale, Filler,
} from "chart.js";
import { lineOptions } from "~/composables/useChartTheme";
import { useChartExport } from "~/composables/useChartExport";
ChartJS.register(Title, Tooltip, Legend, PointElement, LineElement, CategoryScale, LinearScale, Filler);

const props = defineProps<{ data: any; name?: string }>();
const options = lineOptions();

const c = ref();
const { downloadPNG, downloadDataCSV, downloadSVG } = useChartExport(() => c.value, "line", () => props.data);
const file = computed(() => props.name || "chart");
</script>

<template>
  <div class="chart-box">
    <div class="chart-dl">
      <button title="Download PNG" @click="downloadPNG(file)">PNG</button>
      <button title="Download data (CSV)" @click="downloadDataCSV(file)">CSV</button>
      <button title="Download SVG" @click="downloadSVG(file)">SVG</button>
    </div>
    <Line ref="c" :data="data" :options="options" />
  </div>
</template>
