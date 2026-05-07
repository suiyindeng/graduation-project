<script setup>
import { onMounted, ref } from 'vue'
import { Database, UsersRound } from 'lucide-vue-next'
import { adminApi } from '../api/modules'

const users = ref([])
const datasets = ref([])
const error = ref('')

async function loadAdminData() {
  error.value = ''
  try {
    const [userResponse, datasetResponse] = await Promise.all([adminApi.users(), adminApi.datasets()])
    users.value = userResponse.data
    datasets.value = datasetResponse.data
  } catch (err) {
    error.value = err.message
  }
}

onMounted(loadAdminData)
</script>

<template>
  <div class="page-grid">
    <header class="page-header">
      <div>
        <span class="eyebrow">ADMIN</span>
        <h1>系统管理</h1>
      </div>
    </header>

    <p v-if="error" class="error-text">{{ error }}</p>

    <section class="admin-columns">
      <div class="admin-panel">
        <header><UsersRound :size="20" /><h2>用户信息</h2></header>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>ID</th><th>用户名</th><th>邮箱</th><th>角色</th><th>主题</th></tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id">
                <td>{{ user.id }}</td>
                <td>{{ user.username }}</td>
                <td>{{ user.email }}</td>
                <td>{{ user.role === 'admin' ? '管理员' : '普通用户' }}</td>
                <td>{{ user.theme_preference }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="admin-panel">
        <header><Database :size="20" /><h2>数据集记录</h2></header>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>ID</th><th>用户ID</th><th>文件名</th><th>行数</th><th>列数</th></tr>
            </thead>
            <tbody>
              <tr v-for="dataset in datasets" :key="dataset.id">
                <td>{{ dataset.id }}</td>
                <td>{{ dataset.owner_id }}</td>
                <td>{{ dataset.filename }}</td>
                <td>{{ dataset.rows_count }}</td>
                <td>{{ dataset.columns_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>
