<script setup lang="ts">
import { Doughnut } from "vue-chartjs";
import { Chart as ChartJS, Title, Tooltip, Legend, ArcElement } from "chart.js";
import { doughnutOptions } from "~/composables/useChartTheme";
ChartJS.register(Title, Tooltip, Legend, ArcElement);

defineProps<{ data: any }>();
const options = doughnutOptions();
</script>

<template>
  <div class="chart-box"><Doughnut :data="data" :options="options" /></div>
</template>
