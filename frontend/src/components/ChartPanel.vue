<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  chart: {
    type: Object,
    required: true
  }
})

const chartEl = ref(null)
let chartInstance = null

function renderChart() {
  if (!chartEl.value) return
  chartInstance = chartInstance || echarts.init(chartEl.value)
  chartInstance.resize()
  chartInstance.setOption(props.chart.option, true)
}

function getImage() {
  return chartInstance?.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#ffffff'
  })
}

defineExpose({ getImage, renderChart, title: props.chart.title })

watch(
  () => props.chart,
  async () => {
    await nextTick()
    renderChart()
  },
  { deep: true }
)

onMounted(() => {
  renderChart()
  window.addEventListener('resize', renderChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', renderChart)
  chartInstance?.dispose()
})
</script>

<template>
  <section class="chart-card">
    <header>
      <div>
        <h3>{{ chart.title }}</h3>
        <p>{{ chart.reason }}</p>
      </div>
      <span>{{ chart.type }}</span>
    </header>
    <div ref="chartEl" class="chart-canvas"></div>
  </section>
</template>
