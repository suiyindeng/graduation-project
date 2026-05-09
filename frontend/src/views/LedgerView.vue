<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { BarChart3, Check, Download, Edit3, FileUp, Plus, ReceiptText, Save, Trash2, X } from 'lucide-vue-next'
import { ledgerApi } from '../api/modules'

const router = useRouter()
const loading = ref(false)
const message = ref('')
const fieldGroups = ref({ system: [], dataset: [], custom: [] })
const records = ref([])
const selectedFields = ref(['日期', '事项', '收入', '支出', '分类', '备注'])
const form = ref({})
const editingRecordId = ref(null)
const editForm = ref({})
const customField = ref({ name: '', field_type: 'text' })
const groupConfig = ref({
  group_field: '分类',
  filename: '整合记账数据集'
})
const groupedPreview = ref(null)
const numericFieldNames = new Set(['收入', '支出', '金额', '单价', '数量', '总金额', '实付金额', '记录数量'])
const dateFieldNames = new Set(['日期', '订单日期', '下单日期', '成交日期', '时间', '创建时间', '记录时间'])

const fieldSections = computed(() => [
  { key: 'system', title: '常用字段', fields: fieldGroups.value.system },
  { key: 'dataset', title: '已有数据字段', fields: fieldGroups.value.dataset },
  { key: 'custom', title: '我的字段', fields: fieldGroups.value.custom }
])

const allFields = computed(() => {
  const seen = new Set()
  return [...fieldGroups.value.system, ...fieldGroups.value.dataset, ...fieldGroups.value.custom].filter((field) => {
    if (!field?.name || seen.has(field.name)) return false
    seen.add(field.name)
    return true
  })
})

const activeFields = computed(() =>
  selectedFields.value
    .map((name) => allFields.value.find((field) => field.name === name) || { name, field_type: 'text' })
    .filter((field) => field.name)
)

const recordColumns = computed(() => {
  const columns = new Set(activeFields.value.map((field) => field.name))
  records.value.forEach((record) => {
    Object.keys(record.content_json || {}).forEach((column) => columns.add(column))
  })
  return [...columns]
})

const textRecordColumns = computed(() => {
  const numericHints = new Set(['收入', '支出', '金额', '单价', '数量', '总金额', '记录数量'])
  return recordColumns.value.filter((column) => !numericHints.has(column))
})

const groupedColumns = computed(() => groupedPreview.value?.columns || [])

function fieldTypeLabel(type) {
  if (type === 'number') return '数值'
  if (type === 'date') return '日期'
  return '文本'
}

function inputType(type) {
  if (type === 'number') return 'number'
  if (type === 'date') return 'date'
  return 'text'
}

function fieldForColumn(column) {
  const matched = allFields.value.find((field) => field.name === column)
  if (matched) return matched
  if (numericFieldNames.has(column)) return { name: column, field_type: 'number' }
  if (dateFieldNames.has(column)) return { name: column, field_type: 'date' }
  return { name: column, field_type: 'text' }
}

function dateInputValue(value) {
  if (!value) return ''
  const text = String(value)
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text
  if (/^\d{4}-\d{2}-\d{2}T/.test(text)) return text.slice(0, 10)
  return text
}

function normalizedValue(field, value) {
  if (value === undefined || value === null || String(value).trim() === '') return null
  if (field.field_type === 'number') return Number(value)
  return value
}

function contentFromSource(source, fields) {
  const content = {}
  fields.forEach((field) => {
    const value = normalizedValue(field, source[field.name])
    if (value !== null && !(field.field_type === 'number' && Number.isNaN(value))) {
      content[field.name] = value
    }
  })
  return content
}

function toggleField(name) {
  if (selectedFields.value.includes(name)) {
    selectedFields.value = selectedFields.value.filter((item) => item !== name)
    delete form.value[name]
  } else {
    selectedFields.value = [...selectedFields.value, name]
  }
}

async function loadLedger() {
  const [{ data: fields }, { data: recordRows }] = await Promise.all([ledgerApi.fields(), ledgerApi.records()])
  fieldGroups.value = fields
  records.value = recordRows
  if (editingRecordId.value && !recordRows.some((record) => record.id === editingRecordId.value)) {
    cancelEditRecord()
  }
  if (!recordColumns.value.includes(groupConfig.value.group_field)) {
    groupConfig.value.group_field = textRecordColumns.value[0] || recordColumns.value[0] || '分类'
  }
}

function groupPayload() {
  return {
    group_field: groupConfig.value.group_field,
    filename: groupConfig.value.filename || '整合记账数据集'
  }
}

async function addCustomField() {
  const name = customField.value.name.trim()
  if (!name) {
    message.value = '请填写字段名称'
    return
  }
  loading.value = true
  message.value = ''
  try {
    await ledgerApi.createField({ name, field_type: customField.value.field_type })
    customField.value = { name: '', field_type: 'text' }
    await loadLedger()
    if (!selectedFields.value.includes(name)) selectedFields.value = [...selectedFields.value, name]
    message.value = '字段已添加'
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

async function removeCustomField(field) {
  if (!field?.id) return
  loading.value = true
  message.value = ''
  try {
    await ledgerApi.removeField(field.id)
    selectedFields.value = selectedFields.value.filter((name) => name !== field.name)
    delete form.value[field.name]
    await loadLedger()
    message.value = '字段已删除'
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

async function saveRecord() {
  const content = contentFromSource(form.value, activeFields.value)
  if (!Object.keys(content).length) {
    message.value = '请至少填写一项内容'
    return
  }
  loading.value = true
  message.value = ''
  try {
    await ledgerApi.createRecord({ content_json: content })
    form.value = {}
    groupedPreview.value = null
    await loadLedger()
    message.value = '记账记录已保存'
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

function startEditRecord(record) {
  if (editingRecordId.value === record.id) return
  if (editingRecordId.value) {
    message.value = '请先保存或取消当前正在修改的记录'
    return
  }
  editingRecordId.value = record.id
  const row = {}
  recordColumns.value.forEach((column) => {
    const field = fieldForColumn(column)
    const value = record.content_json?.[column] ?? ''
    row[column] = field.field_type === 'date' ? dateInputValue(value) : value
  })
  editForm.value = row
  message.value = ''
}

async function handleRecordCellDblclick(record) {
  if (loading.value) return
  if (!editingRecordId.value) {
    startEditRecord(record)
    return
  }
  if (editingRecordId.value === record.id) return

  const currentRecord = records.value.find((item) => item.id === editingRecordId.value)
  if (currentRecord) await saveEditedRecord(currentRecord)
}

function cancelEditRecord() {
  editingRecordId.value = null
  editForm.value = {}
}

async function saveEditedRecord(record) {
  const fields = recordColumns.value.map((column) => fieldForColumn(column))
  const content = contentFromSource(editForm.value, fields)
  if (!Object.keys(content).length) {
    message.value = '请至少保留一项内容'
    return
  }
  loading.value = true
  message.value = ''
  try {
    await ledgerApi.updateRecord(record.id, { content_json: content })
    cancelEditRecord()
    groupedPreview.value = null
    await loadLedger()
    message.value = '记录已更新'
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

async function saveEditingFromPage(event) {
  if (!editingRecordId.value || loading.value) return
  if (event.target.closest('.ledger-row-editing')) return
  const record = records.value.find((item) => item.id === editingRecordId.value)
  if (record) await saveEditedRecord(record)
}

async function removeRecord(id) {
  loading.value = true
  message.value = ''
  try {
    await ledgerApi.removeRecord(id)
    if (editingRecordId.value === id) cancelEditRecord()
    groupedPreview.value = null
    await loadLedger()
    message.value = '记录已删除'
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

async function importLedgerExcel(event) {
  const file = event.target.files?.[0]
  if (!file) return
  loading.value = true
  message.value = ''
  try {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await ledgerApi.importExcel(formData)
    groupedPreview.value = null
    await loadLedger()
    message.value = `已从 Excel 导入 ${data.length} 条记账记录`
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
    event.target.value = ''
  }
}

async function exportLedger() {
  loading.value = true
  message.value = ''
  try {
    const { data } = await ledgerApi.exportExcel()
    const url = URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url
    link.download = '记账记录.xlsx'
    link.click()
    URL.revokeObjectURL(url)
    message.value = 'Excel 已导出'
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

async function useForVisualization() {
  loading.value = true
  message.value = ''
  try {
    await ledgerApi.toDataset({ filename: '记账数据集' })
    message.value = '已生成可视化数据集'
    router.push('/dashboard')
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

async function previewGroupedRecords() {
  if (!records.value.length) {
    message.value = '请先保存记账记录'
    return
  }
  if (!groupConfig.value.group_field) {
    message.value = '请选择整合依据字段'
    return
  }
  loading.value = true
  message.value = ''
  try {
    const { data } = await ledgerApi.groupPreview(groupPayload())
    groupedPreview.value = data
    message.value = `已按「${groupConfig.value.group_field}」整合为 ${data.rows_count} 条词条`
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

async function exportGroupedLedger() {
  loading.value = true
  message.value = ''
  try {
    const { data } = await ledgerApi.groupExport(groupPayload())
    const url = URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url
    link.download = `${groupConfig.value.filename || '整合记账数据集'}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
    message.value = '整合 Excel 已导出'
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

async function groupedForVisualization() {
  loading.value = true
  message.value = ''
  try {
    await ledgerApi.groupToDataset(groupPayload())
    message.value = '已生成整合后的可视化数据集'
    router.push('/dashboard')
  } catch (error) {
    message.value = error.message
  } finally {
    loading.value = false
  }
}

onMounted(loadLedger)
</script>

<template>
  <div class="page-grid ledger-page" @dblclick="saveEditingFromPage">
    <header class="page-header">
      <div>
        <span class="eyebrow">LEDGER</span>
        <h1>记账管理</h1>
      </div>
    </header>

    <p v-if="message" class="status-text">{{ message }}</p>

    <section class="ledger-shell">
      <aside class="ledger-panel ledger-field-panel">
        <header class="ledger-panel-header">
          <ReceiptText :size="22" />
          <div>
            <h2>字段管理</h2>
            <p>勾选后加入右侧表单。</p>
          </div>
        </header>

        <div class="ledger-new-field">
          <input v-model="customField.name" placeholder="新增字段，如 客户来源" />
          <select v-model="customField.field_type">
            <option value="text">文本</option>
            <option value="number">数值</option>
            <option value="date">日期</option>
          </select>
          <button class="primary-button" type="button" :disabled="loading" @click="addCustomField">
            <Plus :size="16" /> 添加
          </button>
        </div>

        <div class="ledger-field-scroll">
          <section v-for="section in fieldSections" :key="section.key" class="ledger-field-section">
            <h3>{{ section.title }} <span>{{ section.fields.length }}</span></h3>
            <div v-if="section.fields.length" class="ledger-field-list">
              <label v-for="field in section.fields" :key="`${section.key}-${field.name}`" class="ledger-field-item">
                <input type="checkbox" :checked="selectedFields.includes(field.name)" @change="toggleField(field.name)" />
                <span>{{ field.name }}</span>
                <small>{{ fieldTypeLabel(field.field_type) }}</small>
                <button
                  v-if="section.key === 'custom'"
                  class="icon-button"
                  type="button"
                  title="删除字段"
                  :disabled="loading"
                  @click.stop.prevent="removeCustomField(field)"
                >
                  <Trash2 :size="14" />
                </button>
              </label>
            </div>
            <p v-else class="muted-text">{{ section.key === 'dataset' ? '暂无已上传数据字段' : '暂无自定义字段' }}</p>
          </section>
        </div>
      </aside>

      <section class="ledger-main">
        <section class="ledger-panel ledger-entry-panel">
          <header class="ledger-panel-header">
            <Save :size="22" />
            <div>
              <h2>当前条目</h2>
              <p>已选 {{ activeFields.length }} 个字段，只保存填写了内容的项。</p>
            </div>
          </header>

          <form class="ledger-form-compact" @submit.prevent="saveRecord">
            <label v-for="field in activeFields" :key="field.name">
              <span>{{ field.name }}</span>
              <input v-model="form[field.name]" :type="inputType(field.field_type)" />
            </label>
            <button class="primary-button ledger-save-button" type="submit" :disabled="loading">
              <Save :size="18" /> 保存一条记录
            </button>
          </form>
        </section>

        <section class="ledger-panel ledger-record-panel">
          <header class="ledger-panel-header ledger-record-header">
            <div class="ledger-title-inline">
              <BarChart3 :size="22" />
              <div>
                <h2>记账记录</h2>
                <p>共 {{ records.length }} 条，可直接编辑导入或手动保存的记录。</p>
              </div>
            </div>
            <div class="ledger-actions">
              <label class="ghost-button ledger-import-button">
                <FileUp :size="16" /> 导入 Excel
                <input hidden type="file" accept=".xlsx,.xls" :disabled="loading" @change="importLedgerExcel" />
              </label>
              <button class="ghost-button" type="button" :disabled="loading || !records.length" @click="exportLedger">
                <Download :size="16" /> 导出 Excel
              </button>
              <button class="primary-button" type="button" :disabled="loading || !records.length" @click="useForVisualization">
                <BarChart3 :size="16" /> 用于可视化
              </button>
            </div>
          </header>

          <div v-if="records.length" class="ledger-table-wrap">
            <table>
              <thead>
                <tr>
                  <th v-for="column in recordColumns" :key="column">{{ column }}</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="record in records" :key="record.id" :class="{ 'ledger-row-editing': editingRecordId === record.id }">
                  <td
                    v-for="column in recordColumns"
                    :key="column"
                    class="ledger-editable-cell"
                    :title="String(record.content_json[column] ?? '')"
                    @dblclick.stop="handleRecordCellDblclick(record)"
                  >
                    <input
                      v-if="editingRecordId === record.id"
                      v-model="editForm[column]"
                      class="ledger-edit-input"
                      :type="inputType(fieldForColumn(column).field_type)"
                    />
                    <span v-else>{{ record.content_json[column] ?? '-' }}</span>
                  </td>
                  <td>
                    <div class="ledger-table-actions">
                      <template v-if="editingRecordId === record.id">
                        <button
                          class="icon-button"
                          type="button"
                          title="保存修改"
                          :disabled="loading"
                          @click="saveEditedRecord(record)"
                        >
                          <Check :size="16" />
                        </button>
                        <button class="icon-button" type="button" title="取消修改" :disabled="loading" @click="cancelEditRecord">
                          <X :size="16" />
                        </button>
                      </template>
                      <template v-else>
                        <button class="icon-button" type="button" title="编辑记录" :disabled="loading" @click="startEditRecord(record)">
                          <Edit3 :size="16" />
                        </button>
                        <button class="icon-button" type="button" title="删除记录" :disabled="loading" @click="removeRecord(record.id)">
                          <Trash2 :size="16" />
                        </button>
                      </template>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <section v-else class="empty-state">还没有记账记录。</section>
        </section>

        <section class="ledger-panel ledger-group-panel">
          <header class="ledger-panel-header ledger-record-header">
            <div class="ledger-title-inline">
              <BarChart3 :size="22" />
              <div>
                <h2>相同词条整合</h2>
                <p>按选定字段把相同词条合并，数值自动求和，文本自动去重合并。</p>
              </div>
            </div>
          </header>

          <div class="ledger-group-controls">
            <label>
              <span>整合依据</span>
              <select v-model="groupConfig.group_field">
                <option v-for="column in recordColumns" :key="column" :value="column">{{ column }}</option>
              </select>
            </label>
            <label>
              <span>数据集名称</span>
              <input v-model="groupConfig.filename" placeholder="例如 本月分类记账汇总" />
            </label>
            <button class="ghost-button" type="button" :disabled="loading || !records.length" @click="previewGroupedRecords">
              预览整合
            </button>
            <button
              class="ghost-button"
              type="button"
              :disabled="loading || !records.length || !groupConfig.group_field"
              @click="exportGroupedLedger"
            >
              <Download :size="16" /> 导出整合 Excel
            </button>
            <button
              class="primary-button"
              type="button"
              :disabled="loading || !records.length || !groupConfig.group_field"
              @click="groupedForVisualization"
            >
              <BarChart3 :size="16" /> 生成整合数据集
            </button>
          </div>

          <div v-if="groupedPreview?.preview_rows?.length" class="ledger-table-wrap ledger-group-preview">
            <table>
              <thead>
                <tr>
                  <th v-for="column in groupedColumns" :key="column">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, index) in groupedPreview.preview_rows" :key="index">
                  <td v-for="column in groupedColumns" :key="column">{{ row[column] ?? '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <section v-else class="empty-state ledger-group-empty">
            选择整合依据后点击预览，可检查合并结果再导出或生成数据集。
          </section>
        </section>
      </section>
    </section>
  </div>
</template>
