<script setup lang="ts">
import { Bar } from "vue-chartjs";
import {
  Chart as ChartJS, Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale,
} from "chart.js";
import { barOptions } from "~/composables/useChartTheme";
ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

const props = defineProps<{ data: any; horizontal?: boolean; stacked?: boolean }>();
const options = computed(() => barOptions({ horizontal: props.horizontal, stacked: props.stacked }));
</script>

<template>
  <div class="chart-box"><Bar :data="data" :options="options" /></div>
</template>
