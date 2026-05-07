<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { AlertTriangle, BadgeCheck, BarChart3, Database, Download, FileSpreadsheet, RefreshCcw, Sparkles, Table2, TrendingDown, TrendingUp, UploadCloud, Wand2, X } from 'lucide-vue-next'
import ChartPanel from '../components/ChartPanel.vue'
import DataPreview from '../components/DataPreview.vue'
import { datasetApi, reportApi } from '../api/modules'

const datasets = ref([])
const currentDataset = ref(null)
const forecast = ref(null)
const selectedFile = ref(null)
const fileInput = ref(null)
const isDraggingFile = ref(false)
const loading = ref(false)
const message = ref('')
const chartRefs = ref([])
const activeResultTab = ref('overview')
const forecastForm = ref({
  periods: 6,
  target_column: '',
  date_column: ''
})

const profileItems = computed(() => {
  const profile = currentDataset.value?.profile_json || {}
  return [
    ['原始行数', profile.original_rows ?? '-'],
    ['清洗后行数', profile.cleaned_rows ?? '-'],
    ['删除重复行', profile.duplicates_removed ?? '-'],
    ['数值字段', profile.numeric_columns?.join('、') || '-'],
    ['日期字段', profile.date_columns?.join('、') || '-'],
    ['分类字段', profile.categorical_columns?.join('、') || '-']
  ]
})

const selectedFileSize = computed(() => {
  if (!selectedFile.value?.size) return ''
  const size = selectedFile.value.size
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
})

const resultTabs = computed(() => [
  { key: 'overview', label: '数据概览', icon: Database },
  { key: 'charts', label: '可视化图表', icon: BarChart3, count: currentDataset.value?.charts_json?.length || 0 },
  { key: 'forecast', label: '行情预测', icon: TrendingUp },
  { key: 'preview', label: '数据预览', icon: Table2 },
])

const forecastInsight = computed(() => {
  const rows = forecast.value?.prediction_json || []
  if (!rows.length) return null

  const values = rows.map((row) => Number(row.predicted_value)).filter((value) => Number.isFinite(value))
  if (!values.length) return null

  const first = values[0]
  const last = values[values.length - 1]
  const average = values.reduce((sum, value) => sum + value, 0) / values.length
  const change = last - first
  const changeRate = first ? (change / first) * 100 : 0
  const absRate = Math.abs(changeRate)
  const direction = absRate < 5 ? 'stable' : change > 0 ? 'up' : 'down'
  const mae = Number(forecast.value?.metrics_json?.mae)
  const r2 = Number(forecast.value?.metrics_json?.r2)
  const maeRate = average && Number.isFinite(mae) ? (mae / average) * 100 : null

  let confidence = '较低'
  if (Number.isFinite(r2) && r2 >= 0.5 && (maeRate === null || maeRate <= 25)) {
    confidence = '较高'
  } else if (Number.isFinite(r2) && r2 >= 0.1 && (maeRate === null || maeRate <= 45)) {
    confidence = '中等'
  }

  const target = forecast.value.target_column
  const trendText = direction === 'up' ? '上升' : direction === 'down' ? '下降' : '基本平稳'
  const title = `未来 ${rows.length} 期${target}预计${trendText}`
  const plainSummary =
    direction === 'stable'
      ? `预测值整体波动不大，平均约为 ${average.toFixed(2)}，可以按常规节奏安排库存和销售计划。`
      : `预测值从 ${first.toFixed(2)} 变化到 ${last.toFixed(2)}，变化约 ${Math.abs(change).toFixed(2)}，幅度约 ${absRate.toFixed(1)}%。`

  const suggestion =
    direction === 'up'
      ? '建议提前关注备货、热销品类和销售人员排班，避免需求上升时供给不足。'
      : direction === 'down'
        ? '建议谨慎备货，优先清理库存，并结合促销、渠道投放或产品结构调整。'
        : '建议保持稳定运营，重点观察是否有节假日、渠道活动或异常订单造成短期波动。'

  const confidenceText =
    confidence === '较高'
      ? '历史验证表现较好，可以作为计划参考。'
      : confidence === '中等'
        ? '预测有参考价值，但仍需要结合业务经验判断。'
        : '模型解释力偏弱，更适合看趋势方向，不建议单独作为决策依据。'

  return {
    rows,
    title,
    trendText,
    direction,
    average: average.toFixed(2),
    changeText: `${change >= 0 ? '+' : ''}${change.toFixed(2)}`,
    changeRateText: `${changeRate >= 0 ? '+' : ''}${changeRate.toFixed(1)}%`,
    confidence,
    confidenceText,
    plainSummary,
    suggestion,
    maeText: Number.isFinite(mae) ? mae.toFixed(2) : '-',
    r2Text: Number.isFinite(r2) ? r2.toFixed(3) : '-',
    maeRateText: maeRate !== null ? `${maeRate.toFixed(1)}%` : '-'
  }
})

async function loadDatasets() {
  const { data } = await datasetApi.list()
  datasets.value = data
  if (!currentDataset.value && data.length) {
    await selectDataset(data[0].id)
  }
}

async function selectDataset(id) {
  message.value = ''
  const { data } = await datasetApi.detail(id)
  currentDataset.value = data
  forecast.value = null
  activeResultTab.value = 'overview'
  forecastForm.value.target_column = data.profile_json?.target_column || ''
  forecastForm.value.date_column = data.profile_json?.date_column || ''
}

async function setResultTab(tab) {
  activeResultTab.value = tab
  if (tab === 'charts') {
    await nextTick()
    chartRefs.value.filter(Boolean).forEach((chartRef) => chartRef.renderChart?.())
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

function acceptFile(file) {
  if (!file) return
  const extension = file.name.split('.').pop()?.toLowerCase()
  if (!['xlsx', 'xls'].includes(extension)) {
    selectedFile.value = null
    message.value = '请上传 .xlsx 或 .xls 格式的 Excel 文件'
    return
  }
  selectedFile.value = file
  message.value = ''
}

function handleFileChange(event) {
  acceptFile(event.target.files?.[0])
}

function handleDragEnter() {
  isDraggingFile.value = true
}

function handleDragLeave() {
  isDraggingFile.value = false
}

function handleDrop(event) {
  isDraggingFile.value = false
  acceptFile(event.dataTransfer.files?.[0])
}

function clearSelectedFile() {
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function uploadDataset() {
  if (!selectedFile.value) return
  loading.value = true
  message.value = ''
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const { data } = await datasetApi.upload(formData)
    currentDataset.value = data
    forecastForm.value.target_column = data.profile_json?.target_column || ''
    forecastForm.value.date_column = data.profile_json?.date_column || ''
    await loadDatasets()
    message.value = '上传并清洗完成'
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

async function runForecast() {
  if (!currentDataset.value) return
  loading.value = true
  message.value = ''
  try {
    const { data } = await datasetApi.forecast(currentDataset.value.id, {
      periods: Number(forecastForm.value.periods),
      target_column: forecastForm.value.target_column || null,
      date_column: forecastForm.value.date_column || null
    })
    forecast.value = data
    message.value = '预测完成'
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

async function exportReport() {
  if (!currentDataset.value) return
  const chartImages = chartRefs.value
    .filter(Boolean)
    .map((chartRef) => ({
      title: chartRef.title,
      image_base64: chartRef.getImage?.()
    }))
    .filter((item) => item.image_base64)

  loading.value = true
  message.value = ''
  try {
    const { data } = await reportApi.exportWord({
      dataset_id: currentDataset.value.id,
      model_run_id: forecast.value?.id || null,
      chart_images: chartImages,
      notes: '由自动数据可视化系统生成。'
    })
    const url = URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url
    link.download = '自动数据可视化分析报告.docx'
    link.click()
    URL.revokeObjectURL(url)
    message.value = 'Word 报告已导出'
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

onMounted(loadDatasets)
</script>

<template>
  <div
    class="page-grid"
    @dragenter.prevent="handleDragEnter"
    @dragover.prevent
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleDrop"
  >
    <header class="page-header">
      <div>
        <span class="eyebrow">DATA WORKBENCH</span>
        <h1>销售数据自动分析</h1>
      </div>
      <button class="icon-button" title="刷新" @click="loadDatasets"><RefreshCcw :size="18" /></button>
    </header>

    <section class="workspace-band">
      <div class="upload-zone">
        <div class="upload-copy">
          <FileSpreadsheet :size="34" />
          <div>
            <h2>上传 Excel 表格</h2>
            <p>.xlsx 或 .xls，系统会自动清洗、识别字段并推荐可视化。</p>
          </div>
        </div>

        <button
          type="button"
          class="upload-dropzone"
          :class="{ dragging: isDraggingFile, ready: selectedFile }"
          @click="openFilePicker"
        >
          <UploadCloud :size="34" />
          <span>{{ selectedFile ? '已选择文件' : '拖入 Excel 文件或点击选择' }}</span>
          <strong v-if="selectedFile">{{ selectedFile.name }}</strong>
          <small>{{ selectedFile ? selectedFileSize : '支持 .xlsx / .xls，建议上传原始销售明细表' }}</small>
        </button>

        <input ref="fileInput" class="visually-hidden" type="file" accept=".xlsx,.xls" @change="handleFileChange" />

        <div class="upload-actions">
          <button v-if="selectedFile" type="button" class="ghost-button" @click="clearSelectedFile">
            <X :size="17" /> 移除文件
          </button>
          <button class="primary-button" :disabled="loading || !selectedFile" @click="uploadDataset">
            <Wand2 :size="18" /> {{ loading ? '处理中' : '开始清洗' }}
          </button>
        </div>
      </div>

      <div class="dataset-list">
        <button
          v-for="item in datasets"
          :key="item.id"
          :class="{ active: currentDataset?.id === item.id }"
          @click="selectDataset(item.id)"
        >
          <strong>{{ item.filename }}</strong>
          <span>{{ item.rows_count }} 行 / {{ item.columns_count }} 列</span>
        </button>
        <p v-if="!datasets.length" class="muted-text">还没有上传数据集</p>
      </div>
    </section>

    <p v-if="message" class="status-text">{{ message }}</p>

    <!-- Reversible dashboard pagination block: keep result-tabs/result-panel together for easy rollback. -->
    <template v-if="currentDataset">
      <section class="result-tabs">
        <div class="tab-list" role="tablist" aria-label="数据分析分类">
          <button
            v-for="tab in resultTabs"
            :key="tab.key"
            type="button"
            role="tab"
            :aria-selected="activeResultTab === tab.key"
            :class="{ active: activeResultTab === tab.key }"
            @click="setResultTab(tab.key)"
          >
            <component :is="tab.icon" :size="17" />
            {{ tab.label }}
            <small v-if="tab.count">{{ tab.count }}</small>
          </button>
        </div>
        <button class="export-button inline-export" :disabled="loading" @click="exportReport"><Download :size="20" /> 导出 Word 报告</button>
      </section>

      <section v-show="activeResultTab === 'overview'" class="result-panel">
        <section class="metrics-grid">
          <div v-for="[label, value] in profileItems" :key="label" class="metric-tile">
            <span>{{ label }}</span>
            <strong>{{ value }}</strong>
          </div>
        </section>

        <section class="recommend-band">
          <header>
            <Sparkles :size="20" />
            <h2>系统推荐分析</h2>
          </header>
          <div class="recommend-list">
            <article v-for="item in currentDataset.recommendations_json" :key="item.id">
              <strong>{{ item.title }}</strong>
              <p>{{ item.reason }}</p>
            </article>
          </div>
        </section>
      </section>

      <section v-show="activeResultTab === 'charts'" class="chart-grid result-panel">
        <ChartPanel
          v-for="(chart, index) in currentDataset.charts_json"
          :key="chart.id"
          :ref="(el) => (chartRefs[index] = el)"
          :chart="chart"
        />
      </section>

      <section v-show="activeResultTab === 'forecast'" class="result-panel">
        <section class="forecast-band">
          <div>
            <h2>未来行情预测</h2>
            <p>选择预测目标和期数，系统会优先尝试 PyCaret，并提供 scikit-learn 回退模型。</p>
          </div>
          <label>
            预测目标
            <select v-model="forecastForm.target_column">
              <option v-for="column in currentDataset.profile_json.numeric_columns" :key="column" :value="column">{{ column }}</option>
            </select>
          </label>
          <label>
            日期字段
            <select v-model="forecastForm.date_column">
              <option value="">不使用日期</option>
              <option v-for="column in currentDataset.profile_json.date_columns" :key="column" :value="column">{{ column }}</option>
            </select>
          </label>
          <label>
            预测期数
            <input v-model="forecastForm.periods" type="number" min="1" max="24" />
          </label>
          <button class="primary-button" :disabled="loading" @click="runForecast">生成预测</button>
        </section>

        <section v-if="forecast && forecastInsight" class="forecast-result">
          <header class="forecast-result-header">
            <div>
              <span class="eyebrow">FORECAST INSIGHT</span>
              <h3>{{ forecastInsight.title }}</h3>
              <p>{{ forecastInsight.plainSummary }}</p>
            </div>
            <div class="confidence-badge" :class="`level-${forecastInsight.confidence}`">
              <BadgeCheck v-if="forecastInsight.confidence !== '较低'" :size="18" />
              <AlertTriangle v-else :size="18" />
              {{ forecastInsight.confidence }}可信度
            </div>
          </header>

          <div class="forecast-explain-grid">
            <article>
              <span>趋势判断</span>
              <strong>
                <TrendingUp v-if="forecastInsight.direction === 'up'" :size="18" />
                <TrendingDown v-else-if="forecastInsight.direction === 'down'" :size="18" />
                {{ forecastInsight.trendText }}
              </strong>
              <p>首末期变化 {{ forecastInsight.changeText }}，约 {{ forecastInsight.changeRateText }}。</p>
            </article>
            <article>
              <span>平均预测值</span>
              <strong>{{ forecastInsight.average }}</strong>
              <p>可作为未来几期的粗略计划基准。</p>
            </article>
            <article>
              <span>误差理解</span>
              <strong>约 ±{{ forecastInsight.maeText }}</strong>
              <p>历史验证中的平均误差约占预测均值 {{ forecastInsight.maeRateText }}。</p>
            </article>
          </div>

          <div class="forecast-advice">
            <strong>经营建议</strong>
            <p>{{ forecastInsight.suggestion }}</p>
            <small>{{ forecastInsight.confidenceText }}</small>
          </div>

          <div class="prediction-list">
            <article v-for="row in forecastInsight.rows" :key="row.period">
              <span>{{ row.period }}</span>
              <strong>{{ row.predicted_value }}</strong>
            </article>
          </div>

          <details class="forecast-tech">
            <summary>查看模型技术信息</summary>
            <p>算法：{{ forecast.algorithm }}</p>
            <p>MAE：{{ forecastInsight.maeText }}；R2：{{ forecastInsight.r2Text }}</p>
            <p>{{ forecast.summary }}</p>
          </details>
        </section>
      </section>

      <section v-show="activeResultTab === 'preview'" class="preview-band result-panel">
        <h2>清洗后数据预览</h2>
        <DataPreview :rows="currentDataset.preview_rows" />
      </section>
    </template>
    <!-- End reversible dashboard pagination block. -->
  </div>
</template>
