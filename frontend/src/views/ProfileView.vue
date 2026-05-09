<script setup>
import { computed, onMounted, ref } from 'vue'
import { Activity, Camera, Clock3, History, Mail, Save, Shield, UserRound } from 'lucide-vue-next'
import { getAssetUrl } from '../api/client'
import { userApi } from '../api/modules'

const emit = defineEmits(['auth-updated'])
const user = ref(JSON.parse(localStorage.getItem('current_user') || 'null'))
const usage = ref(null)
const form = ref({
  username: '',
  email: '',
  theme_preference: 'arcaea'
})
const message = ref('')

const avatarText = computed(() => user.value?.username?.slice(0, 1)?.toUpperCase() || 'U')
const isSuperAdmin = computed(() => user.value?.role === 'super_admin')
const canUseFenghuaTheme = computed(() => user.value?.role === 'super_admin' && user.value?.username === '冴月麟')
const recentLogins = computed(() => usage.value?.recent_logins || [])
const recentOperations = computed(() => usage.value?.recent_operations || [])
const registeredText = computed(() => formatDate(usage.value?.registered_at || user.value?.created_at))
const lastLoginText = computed(() => formatDate(recentLogins.value[0]?.created_at))
const roleLabel = computed(() => {
  if (user.value?.role === 'super_admin') return '超级管理员'
  if (user.value?.role === 'admin') return '管理员'
  return '普通用户'
})

const actionLabels = {
  register: '账号注册',
  password_reset: '密码重置',
  profile_update: '资料设置',
  avatar_update: '头像设置',
  dataset_upload: '数据清洗',
  dataset_delete: '删除数据',
  chart_analysis: '图例分析',
  forecast_create: '行情预测',
  report_export: '报告导出',
  ledger_field_create: '记账字段',
  ledger_field_delete: '记账字段',
  ledger_record_create: '记账记录',
  ledger_record_delete: '记账记录',
  ledger_export: '记账导出',
  ledger_to_dataset: '记账转数据'
}

function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function actionLabel(action) {
  return actionLabels[action] || '系统操作'
}

function fillForm(data) {
  user.value = data
  form.value.username = data.username
  form.value.email = data.email
  form.value.theme_preference = data.theme_preference || 'arcaea'
}

async function loadProfile() {
  const [{ data: profile }, { data: stats }] = await Promise.all([userApi.me(), userApi.stats()])
  localStorage.setItem('current_user', JSON.stringify(profile))
  fillForm(profile)
  usage.value = stats
}

async function saveProfile() {
  message.value = ''
  try {
    const payload = isSuperAdmin.value
      ? { theme_preference: form.value.theme_preference }
      : { ...form.value }
    const { data } = await userApi.update(payload)
    localStorage.setItem('current_user', JSON.stringify(data))
    localStorage.setItem('theme', data.theme_preference)
    document.documentElement.dataset.theme = data.theme_preference
    fillForm(data)
    emit('auth-updated', data)
    message.value = '用户信息已保存'
  } catch (error) {
    message.value = error.message
  }
}

async function uploadAvatar(event) {
  const file = event.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    const { data } = await userApi.avatar(formData)
    localStorage.setItem('current_user', JSON.stringify(data))
    fillForm(data)
    emit('auth-updated', data)
    message.value = '头像已更新'
  } catch (error) {
    message.value = error.message
  } finally {
    event.target.value = ''
  }
}

onMounted(loadProfile)
</script>

<template>
  <div class="profile-page">
    <header class="page-header">
      <div>
        <span class="eyebrow">PROFILE</span>
        <h1>用户中心</h1>
      </div>
    </header>

    <section class="profile-grid">
      <article class="profile-card profile-identity-card">
        <div class="avatar-large">
          <img v-if="user?.avatar_url" :src="getAssetUrl(user.avatar_url)" alt="avatar" />
          <span v-else>{{ avatarText }}</span>
        </div>
        <div class="profile-main-info">
          <span class="profile-role">{{ roleLabel }}</span>
          <h2>{{ user?.username }}</h2>
          <p><Mail :size="16" /> {{ user?.email }}</p>
        </div>
        <label class="file-button">
          <Camera :size="18" /> 更换头像
          <input hidden type="file" accept=".jpg,.jpeg,.png,.webp" @change="uploadAvatar" />
        </label>
      </article>

      <section class="profile-form">
        <header><UserRound :size="20" /><h2>账号资料</h2></header>
        <p v-if="isSuperAdmin" class="muted-text">超级管理员为系统固定账号，用户名和邮箱不可在用户中心修改。</p>
        <label>用户名<input v-model="form.username" :disabled="isSuperAdmin" /></label>
        <label>邮箱<input v-model="form.email" type="email" :disabled="isSuperAdmin" /></label>
        <label>
          默认主题
          <select v-model="form.theme_preference">
            <option value="arcaea">Arcaea 玻璃水晶</option>
            <option value="rosmontis">迷迭香 轻盈一梦</option>
            <option value="skadi">斯卡蒂 腐蚀之心</option>
            <option value="module_disabled">模块禁用 千禧蓝白</option>
            <option value="seven_rebirth">七日重生 符咒阴月</option>
            <option v-if="canUseFenghuaTheme" value="forgotten_fenghua">遗忘的风华 花灯旧梦</option>
          </select>
        </label>
        <button class="primary-button" @click="saveProfile"><Save :size="18" /> 保存设置</button>
        <p v-if="message" class="status-text">{{ message }}</p>
      </section>
    </section>

    <section class="profile-form profile-summary">
      <header><Shield :size="20" /><h2>个人使用概览</h2></header>
      <div class="profile-metrics">
        <article class="metric-tile">
          <span>上传数据集</span>
          <strong>{{ usage?.dataset_count ?? 0 }}</strong>
        </article>
        <article class="metric-tile">
          <span>累计清洗行数</span>
          <strong>{{ usage?.cleaned_rows ?? 0 }}</strong>
        </article>
        <article class="metric-tile">
          <span>预测次数</span>
          <strong>{{ usage?.forecast_count ?? 0 }}</strong>
        </article>
        <article class="metric-tile">
          <span>最近上传</span>
          <strong>{{ formatDate(usage?.last_dataset_at) }}</strong>
        </article>
      </div>
    </section>

    <section class="profile-log-grid">
      <article class="profile-form">
        <header><Clock3 :size="20" /><h2>账户时间记录</h2></header>
        <div class="profile-metrics profile-time-metrics">
          <article class="metric-tile">
            <span>账户注册时间</span>
            <strong>{{ registeredText }}</strong>
          </article>
          <article class="metric-tile">
            <span>最近登录</span>
            <strong>{{ lastLoginText }}</strong>
          </article>
          <article class="metric-tile">
            <span>近一周登录</span>
            <strong>{{ recentLogins.length }}</strong>
          </article>
          <article class="metric-tile">
            <span>近一周操作</span>
            <strong>{{ usage?.operation_count_7d ?? 0 }}</strong>
          </article>
        </div>
        <div class="profile-log-list">
          <h3>最近一周登录记录</h3>
          <p v-if="!recentLogins.length" class="empty-state profile-empty-note">最近一周暂无登录记录。</p>
          <article v-for="item in recentLogins" :key="item.id" class="profile-log-item">
            <span class="profile-log-dot"></span>
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.detail || '登录系统' }}</p>
            </div>
            <time>{{ formatDate(item.created_at) }}</time>
          </article>
        </div>
      </article>

      <article class="profile-form">
        <header><History :size="20" /><h2>系统使用操作记录</h2></header>
        <div class="profile-log-summary">
          <span><Activity :size="16" /> 总操作 {{ usage?.operation_count_total ?? 0 }} 次</span>
          <span>最近保留 {{ recentOperations.length }} 条</span>
        </div>
        <div class="profile-log-list">
          <p v-if="!recentOperations.length" class="empty-state profile-empty-note">暂无系统操作记录。</p>
          <article v-for="item in recentOperations" :key="item.id" class="profile-log-item">
            <span class="profile-log-tag">{{ actionLabel(item.action) }}</span>
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.detail || '已完成操作' }}</p>
            </div>
            <time>{{ formatDate(item.created_at) }}</time>
          </article>
        </div>
      </article>
    </section>
  </div>
</template>
