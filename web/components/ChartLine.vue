<script setup lang="ts">
import { Line } from "vue-chartjs";
import {
  Chart as ChartJS, Title, Tooltip, Legend, PointElement, LineElement, CategoryScale, LinearScale, Filler,
} from "chart.js";
import { lineOptions } from "~/composables/useChartTheme";
ChartJS.register(Title, Tooltip, Legend, PointElement, LineElement, CategoryScale, LinearScale, Filler);

defineProps<{ data: any }>();
const options = lineOptions();
</script>

<template>
  <div class="chart-box"><Line :data="data" :options="options" /></div>
</template>
