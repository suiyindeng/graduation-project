<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { BadgeCheck, BarChart3, BookOpen, Database, Layers3, RefreshCcw, Sparkles } from 'lucide-vue-next'
import ChartPanel from '../components/ChartPanel.vue'
import { datasetApi } from '../api/modules'

const datasets = ref([])
const currentDataset = ref(null)
const analysis = ref(null)
const selectedDatasetId = ref('')
const loading = ref(false)
const message = ref('')
const chartRefs = ref([])
const activeChartId = ref('')

const activeChartAnalysis = computed(() => {
  const charts = analysis.value?.charts || []
  return charts.find((chart) => chart.id === activeChartId.value) || charts[0] || null
})

const activeChart = computed(() => {
  const chartId = activeChartAnalysis.value?.id
  return currentDataset.value?.charts_json?.find((chart) => chart.id === chartId) || null
})

const modelMetricItems = computed(() => {
  const metrics = analysis.value?.model_insight?.metrics || {}
  return [
    ['MAE', metrics.mae ?? '-'],
    ['R2', metrics.r2 ?? '-'],
    ['RMSE', metrics.rmse ?? '-']
  ]
})

function resetAnalysis() {
  analysis.value = null
  activeChartId.value = ''
  chartRefs.value = []
}

async function loadDatasets() {
  message.value = ''
  try {
    const { data } = await datasetApi.list()
    datasets.value = data
    if (!selectedDatasetId.value && data.length) {
      selectedDatasetId.value = String(data[0].id)
      await loadSelectedDataset()
    }
  } catch (error) {
    message.value = error.message
  }
}

async function loadSelectedDataset() {
  resetAnalysis()
  if (!selectedDatasetId.value) {
    currentDataset.value = null
    return
  }
  loading.value = true
  message.value = ''
  try {
    const { data } = await datasetApi.detail(selectedDatasetId.value)
    currentDataset.value = data
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

async function runAnalysis() {
  if (!selectedDatasetId.value) return
  loading.value = true
  message.value = ''
  try {
    const { data } = await datasetApi.chartAnalysis(selectedDatasetId.value)
    analysis.value = data
    activeChartId.value = data.charts?.[0]?.id || ''
    await nextTick()
    chartRefs.value.filter(Boolean).forEach((chartRef) => chartRef.renderChart?.())
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

function setActiveChart(chartId) {
  activeChartId.value = chartId
  nextTick(() => {
    chartRefs.value.filter(Boolean).forEach((chartRef) => chartRef.renderChart?.())
  })
}

onMounted(loadDatasets)
</script>

<template>
  <div class="page-grid legend-analysis-page">
    <header class="page-header">
      <div>
        <span class="eyebrow">CHART INTERPRETER</span>
        <h1>图例分析</h1>
      </div>
      <button class="icon-button" title="刷新数据集" @click="loadDatasets"><RefreshCcw :size="18" /></button>
    </header>

    <section class="forecast-result legend-control-panel">
      <div>
        <span class="eyebrow">DATASET</span>
        <h2>选择要解读的数据集</h2>
        <p>系统会基于清洗后的数据和已生成图表，使用 PyCaret 建模提示与统计规则说明图表含义。</p>
      </div>
      <label>
        数据集
        <select v-model="selectedDatasetId" @change="loadSelectedDataset">
          <option value="">请选择数据集</option>
          <option v-for="item in datasets" :key="item.id" :value="item.id">
            {{ item.filename }}（{{ item.rows_count }} 行）
          </option>
        </select>
      </label>
      <button class="primary-button" :disabled="loading || !selectedDatasetId" @click="runAnalysis">
        <Sparkles :size="18" /> {{ loading ? '分析中' : '生成图例分析' }}
      </button>
    </section>

    <p v-if="message" class="status-text">{{ message }}</p>

    <section v-if="currentDataset && !analysis" class="recommend-band legend-empty-panel">
      <header><BookOpen :size="20" /><h2>等待生成分析</h2></header>
      <p>
        当前已选择「{{ currentDataset.filename }}」。点击“生成图例分析”后，页面会按每张图分别说明读法、数据含义、重点发现和经营问题。
      </p>
    </section>

    <template v-if="analysis">
      <section class="metrics-grid legend-summary-grid">
        <article class="metric-tile">
          <span>分析引擎</span>
          <strong>{{ analysis.engine }}</strong>
        </article>
        <article class="metric-tile">
          <span>解释目标</span>
          <strong>{{ analysis.summary.target_column }}</strong>
        </article>
        <article class="metric-tile">
          <span>图表数量</span>
          <strong>{{ analysis.summary.chart_count }}</strong>
        </article>
      </section>

      <section class="forecast-result model-insight-panel">
        <header class="forecast-result-header">
          <div>
            <span class="eyebrow">PYCARET MODEL</span>
            <h3>模型辅助理解</h3>
            <p>{{ analysis.model_insight.plain_summary }}</p>
          </div>
          <div class="confidence-badge">
            <BadgeCheck :size="18" />
            {{ analysis.model_insight.best_model || analysis.engine }}
          </div>
        </header>

        <div class="legend-chip-row">
          <span v-for="item in analysis.model_insight.preprocessing" :key="item" class="legend-chip">{{ item }}</span>
        </div>

        <div class="forecast-explain-grid">
          <article v-for="[label, value] in modelMetricItems" :key="label">
            <span>{{ label }}</span>
            <strong>{{ value }}</strong>
            <p>用于判断模型解释结果的参考度。</p>
          </article>
        </div>

        <div v-if="analysis.model_insight.important_features?.length" class="legend-feature-list">
          <article v-for="item in analysis.model_insight.important_features" :key="`${item.name}-${item.type}`">
            <strong>{{ item.name }}</strong>
            <span>{{ item.type }} / {{ item.direction }} / {{ item.score }}</span>
            <p>{{ item.explanation }}</p>
          </article>
        </div>
      </section>

      <section class="legend-reader-grid">
        <aside class="recommend-band legend-chart-list">
          <header><Layers3 :size="20" /><h2>图表目录</h2></header>
          <button
            v-for="chart in analysis.charts"
            :key="chart.id"
            type="button"
            :class="{ active: activeChartId === chart.id }"
            @click="setActiveChart(chart.id)"
          >
            <span>{{ chart.type_label }}</span>
            <strong>{{ chart.title }}</strong>
          </button>
        </aside>

        <section class="legend-detail-stack">
          <ChartPanel
            v-if="activeChart"
            :key="activeChart.id"
            :ref="(el) => (chartRefs[0] = el)"
            :chart="activeChart"
          />

          <article v-if="activeChartAnalysis" class="forecast-result legend-detail-card">
            <header class="legend-detail-header">
              <div>
                <span class="eyebrow">{{ activeChartAnalysis.type_label }}</span>
                <h2>{{ activeChartAnalysis.title }}</h2>
                <p>{{ activeChartAnalysis.plain_language }}</p>
              </div>
              <span class="legend-type-badge">{{ activeChartAnalysis.type }}</span>
            </header>

            <div class="legend-section-grid">
              <section>
                <h3><BookOpen :size="18" /> 这张图怎么看</h3>
                <ul>
                  <li v-for="item in activeChartAnalysis.how_to_read" :key="item">{{ item }}</li>
                </ul>
              </section>

              <section>
                <h3><Database :size="18" /> 图上数据代表什么</h3>
                <ul>
                  <li v-for="item in activeChartAnalysis.data_meaning" :key="item">{{ item }}</li>
                </ul>
              </section>

              <section>
                <h3><BarChart3 :size="18" /> 系统发现</h3>
                <ul>
                  <li v-for="item in activeChartAnalysis.key_findings" :key="item">{{ item }}</li>
                </ul>
              </section>

              <section>
                <h3><Sparkles :size="18" /> 经营判断问题</h3>
                <ul>
                  <li v-for="item in activeChartAnalysis.business_questions" :key="item">{{ item }}</li>
                </ul>
              </section>
            </div>

            <div class="forecast-advice">
              <strong>PyCaret / 模型提示</strong>
              <p>{{ activeChartAnalysis.model_insight }}</p>
            </div>
          </article>
        </section>
      </section>

      <section class="recommend-band legend-tips-panel">
        <header><BookOpen :size="20" /><h2>通用读图顺序</h2></header>
        <div class="recommend-list">
          <article v-for="tip in analysis.reading_tips" :key="tip">
            <p>{{ tip }}</p>
          </article>
        </div>
      </section>
    </template>
  </div>
</template>
