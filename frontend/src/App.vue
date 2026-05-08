<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { BarChart3, BookOpen, LineChart, LogOut, Settings, Shield, UploadCloud } from 'lucide-vue-next'
import ThemeSwitcher from './components/ThemeSwitcher.vue'
import { userApi } from './api/modules'
import { getAssetUrl } from './api/client'

const router = useRouter()
const route = useRoute()
const user = ref(JSON.parse(localStorage.getItem('current_user') || 'null'))
const token = ref(localStorage.getItem('access_token'))
const theme = ref(localStorage.getItem('theme') || 'arcaea')

const isAuthed = computed(() => Boolean(token.value))
const isAuthPage = computed(() => route.path === '/auth' || route.path === '/forgot-password')
const avatarText = computed(() => user.value?.username?.slice(0, 1)?.toUpperCase() || 'U')
const canUseAdmin = computed(() => ['admin', 'super_admin'].includes(user.value?.role))
const canUseSystemStats = computed(() => user.value?.role === 'super_admin')
const canUseFenghuaTheme = computed(() => user.value?.role === 'super_admin' && user.value?.username === '冴月麟')
const roleLabel = computed(() => {
  if (user.value?.role === 'super_admin') return '超级管理员'
  if (user.value?.role === 'admin') return '管理员'
  return '普通用户'
})

function applyTheme(name) {
  const nextTheme = name === 'forgotten_fenghua' && !canUseFenghuaTheme.value ? 'arcaea' : name
  theme.value = nextTheme
  document.documentElement.dataset.theme = nextTheme
  localStorage.setItem('theme', nextTheme)
}

async function setTheme(name) {
  if (name === 'forgotten_fenghua' && !canUseFenghuaTheme.value) return
  applyTheme(name)
  if (user.value) {
    try {
      const { data } = await userApi.update({ theme_preference: name })
      user.value = data
      localStorage.setItem('current_user', JSON.stringify(data))
    } catch {
      // Theme switching should still work locally when the network request fails.
    }
  }
}

function logout() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('current_user')
  token.value = null
  user.value = null
  router.push('/auth')
}

function updateAuth(value) {
  user.value = value
  token.value = localStorage.getItem('access_token')
  if (value?.theme_preference) {
    applyTheme(value.theme_preference)
  }
}

onMounted(async () => {
  applyTheme(theme.value || 'arcaea')
  if (isAuthed.value) {
    try {
      const { data } = await userApi.me()
      user.value = data
      localStorage.setItem('current_user', JSON.stringify(data))
      applyTheme(data.theme_preference || theme.value)
    } catch {
      logout()
    }
  }
})

watch(
  () => route.path,
  (path) => {
    if (path === '/auth' || path === '/forgot-password') {
      applyTheme(localStorage.getItem('theme') || 'arcaea')
    }
  },
)
</script>

<template>
  <div v-if="!isAuthed || isAuthPage" class="auth-shell">
    <RouterView :theme="theme" @theme-change="setTheme" @auth-updated="updateAuth" />
  </div>

  <div v-else class="app-shell">
    <aside v-if="isAuthed" class="sidebar">
      <div class="brand-mark">
        <div class="brand-icon"><BarChart3 :size="24" /></div>
        <div>
          <strong>AutoViz</strong>
          <span>Sales Insight</span>
        </div>
      </div>

      <nav class="nav-list">
        <RouterLink to="/dashboard"><UploadCloud :size="18" /> 工作台</RouterLink>
        <RouterLink to="/legend-analysis"><BookOpen :size="18" /> 图例分析</RouterLink>
        <RouterLink v-if="canUseAdmin" to="/admin"><Shield :size="18" /> 管理端</RouterLink>
        <RouterLink v-if="canUseSystemStats" to="/admin/stats"><LineChart :size="18" /> 系统数据统计</RouterLink>
        <RouterLink to="/profile"><Settings :size="18" /> 用户中心</RouterLink>
      </nav>

      <ThemeSwitcher :theme="theme" :user="user" @change="setTheme" />

      <div class="user-strip" @click="router.push('/profile')">
        <img v-if="user?.avatar_url" :src="getAssetUrl(user.avatar_url)" alt="avatar" />
        <div v-else class="avatar-fallback">{{ avatarText }}</div>
        <div>
          <strong>{{ user?.username }}</strong>
          <span>{{ roleLabel }}</span>
        </div>
      </div>

      <button class="ghost-button" @click="logout"><LogOut :size="18" /> 退出登录</button>
    </aside>

    <main class="content-area">
      <RouterView @auth-updated="updateAuth" />
    </main>
  </div>
</template>
