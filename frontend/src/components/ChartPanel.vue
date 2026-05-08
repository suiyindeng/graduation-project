<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Download, EyeOff } from 'lucide-vue-next'
import * as echarts from 'echarts'

const props = defineProps({
  chart: {
    type: Object,
    required: true
  },
  showActions: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['hide'])
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

function safeFilename(name) {
  return String(name || 'chart').replace(/[\\/:*?"<>|]/g, '_')
}

function downloadChart() {
  const image = getImage()
  if (!image) return
  const link = document.createElement('a')
  link.href = image
  link.download = `${safeFilename(props.chart.title)}.png`
  link.click()
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
      <div class="chart-header-actions">
        <button v-if="showActions" type="button" class="chart-action-button" title="下载该图表" @click="downloadChart">
          <Download :size="16" />
        </button>
        <button v-if="showActions" type="button" class="chart-action-button" title="隐藏该图表" @click="emit('hide', chart.id)">
          <EyeOff :size="16" />
        </button>
        <span>{{ chart.type }}</span>
      </div>
    </header>
    <div ref="chartEl" class="chart-canvas"></div>
  </section>
</template>
