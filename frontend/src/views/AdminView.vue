<script setup>
import { computed, onMounted, ref } from 'vue'
import { Database, Save, Shield, UsersRound } from 'lucide-vue-next'
import { adminApi } from '../api/modules'

const currentUser = computed(() => JSON.parse(localStorage.getItem('current_user') || 'null'))
const isSuperAdmin = computed(() => currentUser.value?.role === 'super_admin')
const users = ref([])
const datasets = ref([])
const error = ref('')
const message = ref('')

function roleLabel(role) {
  if (role === 'super_admin') return '超级管理员'
  if (role === 'admin') return '管理员'
  return '普通用户'
}

function editablePayload(user) {
  return {
    username: user.username,
    email: user.email,
    role: user.role === 'super_admin' ? undefined : user.role,
    theme_preference: user.theme_preference,
    is_active: user.is_active
  }
}

function canEditUser(user) {
  return user.role !== 'super_admin'
}

async function loadAdminData() {
  error.value = ''
  message.value = ''
  try {
    const [userResponse, datasetResponse] = await Promise.all([adminApi.users(), adminApi.datasets()])
    users.value = userResponse.data.map((user) => ({ ...user, edit: editablePayload(user) }))
    datasets.value = datasetResponse.data
  } catch (err) {
    error.value = err.message
  }
}

async function saveUser(user) {
  error.value = ''
  message.value = ''
  try {
    const apiCall =
      isSuperAdmin.value && user.edit.role
        ? adminApi.updateUserRole(user.id, user.edit)
        : adminApi.updateUser(user.id, user.edit)
    await apiCall
    message.value = '用户信息已保存'
    await loadAdminData()
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
      <button class="icon-button" type="button" title="刷新" @click="loadAdminData">
        <Shield :size="18" />
      </button>
    </header>

    <p v-if="error" class="error-text">{{ error }}</p>
    <p v-if="message" class="status-text">{{ message }}</p>

    <section class="admin-columns">
      <div class="admin-panel">
        <header><UsersRound :size="20" /><h2>用户信息</h2></header>
        <div class="table-wrap">
          <table class="admin-user-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>用户名</th>
                <th>邮箱</th>
                <th>角色</th>
                <th>状态</th>
                <th>主题</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id">
                <td>{{ user.id }}</td>
                <td><input v-model="user.edit.username" :disabled="!canEditUser(user)" /></td>
                <td><input v-model="user.edit.email" :disabled="!canEditUser(user)" /></td>
                <td>
                  <select v-if="isSuperAdmin && canEditUser(user)" v-model="user.edit.role">
                    <option value="user">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                  <span v-else>{{ roleLabel(user.role) }}</span>
                </td>
                <td>
                  <select v-model="user.edit.is_active" :disabled="!canEditUser(user)">
                    <option :value="true">启用</option>
                    <option :value="false">停用</option>
                  </select>
                </td>
                <td>
                  <select v-model="user.edit.theme_preference" :disabled="!canEditUser(user)">
                    <option value="arcaea">Arcaea</option>
                    <option value="rosmontis">轻盈一梦</option>
                    <option value="skadi">腐蚀之心</option>
                    <option value="module_disabled">模块禁用</option>
                    <option value="seven_rebirth">七日重生</option>
                    <option v-if="user.role === 'super_admin'" value="forgotten_fenghua">遗忘的风华</option>
                  </select>
                </td>
                <td>
                  <button v-if="canEditUser(user)" class="file-button" type="button" @click="saveUser(user)">
                    <Save :size="16" /> 保存
                  </button>
                  <span v-else class="muted-text">受保护</span>
                </td>
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
