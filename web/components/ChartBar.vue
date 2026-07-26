<script setup lang="ts">
import { Bar } from "vue-chartjs";
import {
  Chart as ChartJS, Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale,
} from "chart.js";
import { barOptions } from "~/composables/useChartTheme";
import { useChartExport } from "~/composables/useChartExport";
ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

const props = defineProps<{ data: any; horizontal?: boolean; stacked?: boolean; name?: string }>();
const options = computed(() => barOptions({ horizontal: props.horizontal, stacked: props.stacked }));

const c = ref();
const { downloadPNG, downloadDataCSV, downloadSVG } = useChartExport(() => c.value, "bar", () => props.data);
const file = computed(() => props.name || "chart");
</script>

<template>
  <div class="chart-box">
    <div class="chart-dl">
      <button title="Download PNG" @click="downloadPNG(file)">PNG</button>
      <button title="Download data (CSV)" @click="downloadDataCSV(file)">CSV</button>
      <button title="Download SVG" @click="downloadSVG(file)">SVG</button>
    </div>
    <Bar ref="c" :data="data" :options="options" />
  </div>
</template>
