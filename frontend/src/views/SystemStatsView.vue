<script setup>
import { onMounted, ref } from 'vue'
import { BarChart3, Search } from 'lucide-vue-next'
import { adminApi } from '../api/modules'

const stats = ref(null)
const error = ref('')
const filters = ref({
  q: '',
  date_from: '',
  date_to: ''
})

function roleLabel(role) {
  if (role === 'super_admin') return '超级管理员'
  if (role === 'admin') return '管理员'
  return '普通用户'
}

async function loadStats() {
  error.value = ''
  try {
    const params = Object.fromEntries(
      Object.entries(filters.value).filter(([, value]) => String(value || '').trim() !== ''),
    )
    const { data } = await adminApi.stats(params)
    stats.value = data
  } catch (err) {
    error.value = err.message
  }
}

onMounted(loadStats)
</script>

<template>
  <div class="page-grid">
    <header class="page-header">
      <div>
        <span class="eyebrow">SUPER ADMIN</span>
        <h1>系统数据统计</h1>
      </div>
    </header>

    <section class="admin-panel stats-filter-panel">
      <header><Search :size="20" /><h2>使用查询</h2></header>
      <div class="stats-filter-grid">
        <label>用户关键词<input v-model="filters.q" placeholder="用户名、邮箱或角色" /></label>
        <label>开始日期<input v-model="filters.date_from" type="date" /></label>
        <label>结束日期<input v-model="filters.date_to" type="date" /></label>
        <button class="primary-button" type="button" @click="loadStats">查询</button>
      </div>
    </section>

    <p v-if="error" class="error-text">{{ error }}</p>

    <section v-if="stats" class="admin-stats">
      <article class="metric-tile">
        <span>注册用户</span>
        <strong>{{ stats.total_users }}</strong>
      </article>
      <article class="metric-tile">
        <span>数据集数量</span>
        <strong>{{ stats.total_datasets }}</strong>
      </article>
      <article class="metric-tile">
        <span>累计清洗行数</span>
        <strong>{{ stats.total_cleaned_rows }}</strong>
      </article>
      <article class="metric-tile">
        <span>预测次数</span>
        <strong>{{ stats.total_forecasts }}</strong>
      </article>
    </section>

    <section v-if="stats" class="admin-panel">
      <header><BarChart3 :size="20" /><h2>近期数据清洗量</h2></header>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>日期</th><th>清洗文件数</th><th>清洗行数</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in stats.recent_days" :key="item.date">
              <td>{{ item.date }}</td>
              <td>{{ item.datasets }}</td>
              <td>{{ item.rows }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="stats" class="admin-panel">
      <header><BarChart3 :size="20" /><h2>用户使用统计</h2></header>
      <div class="table-wrap">
        <table class="usage-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>邮箱</th>
              <th>角色</th>
              <th>状态</th>
              <th>上传数据集</th>
              <th>清洗行数</th>
              <th>预测次数</th>
              <th>最近上传</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in stats.user_usage" :key="user.user_id">
              <td>{{ user.user_id }}</td>
              <td>{{ user.username }}</td>
              <td>{{ user.email }}</td>
              <td>{{ user.role_label || roleLabel(user.role) }}</td>
              <td>{{ user.is_active ? '启用' : '停用' }}</td>
              <td>{{ user.dataset_count }}</td>
              <td>{{ user.cleaned_rows }}</td>
              <td>{{ user.forecast_count }}</td>
              <td>{{ user.last_dataset_at || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
