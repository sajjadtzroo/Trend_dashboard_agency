<script setup lang="ts">
import { Doughnut } from "vue-chartjs";
import { Chart as ChartJS, Title, Tooltip, Legend, ArcElement } from "chart.js";
import { doughnutOptions } from "~/composables/useChartTheme";
import { useChartExport } from "~/composables/useChartExport";
ChartJS.register(Title, Tooltip, Legend, ArcElement);

const props = defineProps<{ data: any; name?: string }>();
const options = doughnutOptions();

const c = ref();
const { downloadPNG, downloadDataCSV, downloadSVG } = useChartExport(() => c.value, "doughnut", () => props.data);
const file = computed(() => props.name || "chart");
</script>

<template>
  <div class="chart-box">
    <div class="chart-dl">
      <button title="Download PNG" @click="downloadPNG(file)">PNG</button>
      <button title="Download data (CSV)" @click="downloadDataCSV(file)">CSV</button>
      <button title="Download SVG" @click="downloadSVG(file)">SVG</button>
    </div>
    <Doughnut ref="c" :data="data" :options="options" />
  </div>
</template>
