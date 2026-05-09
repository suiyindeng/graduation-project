<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { BarChart3, LockKeyhole, UserPlus } from 'lucide-vue-next'
import ThemeSwitcher from '../components/ThemeSwitcher.vue'
import { authApi } from '../api/modules'

defineProps({
  theme: {
    type: String,
    default: 'arcaea'
  }
})
const emit = defineEmits(['auth-updated', 'theme-change'])
const router = useRouter()
const mode = ref('login')
const loading = ref(false)
const error = ref('')
const arcaeaFallItems = [
  { id: 1, style: { '--fall-left': '6%', '--fall-delay': '-1s', '--fall-duration': '18s', '--fall-drift': '28px', '--fall-size': '13px', '--fall-rotate': '-10deg' } },
  { id: 2, style: { '--fall-left': '14%', '--fall-delay': '-9s', '--fall-duration': '22s', '--fall-drift': '-22px', '--fall-size': '11px', '--fall-rotate': '8deg' } },
  { id: 3, style: { '--fall-left': '23%', '--fall-delay': '-4s', '--fall-duration': '20s', '--fall-drift': '34px', '--fall-size': '12px', '--fall-rotate': '16deg' } },
  { id: 4, style: { '--fall-left': '33%', '--fall-delay': '-12s', '--fall-duration': '24s', '--fall-drift': '-36px', '--fall-size': '14px', '--fall-rotate': '-16deg' } },
  { id: 5, style: { '--fall-left': '44%', '--fall-delay': '-6s', '--fall-duration': '19s', '--fall-drift': '18px', '--fall-size': '10px', '--fall-rotate': '12deg' } },
  { id: 6, style: { '--fall-left': '53%', '--fall-delay': '-15s', '--fall-duration': '25s', '--fall-drift': '-26px', '--fall-size': '13px', '--fall-rotate': '-6deg' } },
  { id: 7, style: { '--fall-left': '62%', '--fall-delay': '-3s', '--fall-duration': '21s', '--fall-drift': '30px', '--fall-size': '12px', '--fall-rotate': '20deg' } },
  { id: 8, style: { '--fall-left': '71%', '--fall-delay': '-11s', '--fall-duration': '23s', '--fall-drift': '-18px', '--fall-size': '11px', '--fall-rotate': '-18deg' } },
  { id: 9, style: { '--fall-left': '81%', '--fall-delay': '-7s', '--fall-duration': '20s', '--fall-drift': '24px', '--fall-size': '14px', '--fall-rotate': '6deg' } },
  { id: 10, style: { '--fall-left': '91%', '--fall-delay': '-17s', '--fall-duration': '26s', '--fall-drift': '-32px', '--fall-size': '12px', '--fall-rotate': '-12deg' } },
]
const captcha = ref({
  captcha_id: '',
  image_url: ''
})

const loginForm = ref({
  account: '',
  password: '',
  captcha_code: ''
})

const registerForm = ref({
  username: '',
  email: '',
  password: '',
  confirm_password: '',
  role: 'user',
  admin_code: '',
  captcha_code: ''
})

const passwordChecks = computed(() => {
  const password = registerForm.value.password
  return [
    { key: 'length', label: '至少 8 位字符', passed: password.length >= 8 },
    { key: 'letter', label: '包含英文字母', passed: /[A-Za-z]/.test(password) },
    { key: 'number', label: '包含数字', passed: /\d/.test(password) },
  ]
})

const passwordStrongEnough = computed(() => passwordChecks.value.every((item) => item.passed))
const confirmTouched = computed(() => registerForm.value.confirm_password.length > 0)
const passwordMatched = computed(
  () => confirmTouched.value && registerForm.value.password === registerForm.value.confirm_password,
)
const canRegister = computed(() => {
  const form = registerForm.value
  const adminReady = form.role !== 'admin' || form.admin_code.trim().length > 0
  return (
    form.username.trim().length >= 2 &&
    form.email.trim().length > 0 &&
    passwordStrongEnough.value &&
    passwordMatched.value &&
    form.captcha_code.trim().length === 4 &&
    adminReady &&
    !loading.value
  )
})

const captchaImage = computed(() =>
  captcha.value.image_url && captcha.value.captcha_id ? `${captcha.value.image_url}?v=${captcha.value.captcha_id}` : '',
)

function persistAuth(data) {
  localStorage.setItem('access_token', data.access_token)
  localStorage.setItem('current_user', JSON.stringify(data.user))
  localStorage.setItem('theme', data.user.theme_preference || 'arcaea')
  document.documentElement.dataset.theme = data.user.theme_preference || 'arcaea'
  emit('auth-updated', data.user)
  router.push(['admin', 'super_admin'].includes(data.user.role) ? '/admin' : '/dashboard')
}

async function login() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await authApi.login({
      ...loginForm.value,
      captcha_id: captcha.value.captcha_id,
    })
    persistAuth(data)
  } catch (err) {
    error.value = err.message
    await loadCaptcha()
  } finally {
    loading.value = false
  }
}

async function register() {
  loading.value = true
  error.value = ''
  try {
    if (!passwordStrongEnough.value) {
      error.value = '密码至少 8 位，并且需要包含字母和数字'
      return
    }
    if (registerForm.value.password !== registerForm.value.confirm_password) {
      error.value = '两次输入的密码不一致'
      return
    }
    if (registerForm.value.captcha_code.trim().length !== 4) {
      error.value = '请输入 4 位验证码'
      return
    }
    const payload = { ...registerForm.value }
    if (payload.role !== 'admin') payload.admin_code = null
    payload.captcha_id = captcha.value.captcha_id
    const { data } = await authApi.register(payload)
    persistAuth(data)
  } catch (err) {
    error.value = err.message
    await loadCaptcha()
  } finally {
    loading.value = false
  }
}

async function loadCaptcha() {
  const { data } = await authApi.captcha()
  captcha.value = data
  loginForm.value.captcha_code = ''
  registerForm.value.captcha_code = ''
}

onMounted(() => {
  if (!localStorage.getItem('theme')) {
    localStorage.setItem('theme', 'arcaea')
    document.documentElement.dataset.theme = 'arcaea'
  }
  loadCaptcha()
})
</script>

<template>
  <div class="auth-layout" :class="`mode-${mode}`">
    <div class="arcaea-fall-layer" aria-hidden="true">
      <span v-for="item in arcaeaFallItems" :key="item.id" class="arcaea-fall-item" :style="item.style"></span>
    </div>

    <ThemeSwitcher class="auth-theme-switcher" :theme="theme" @change="emit('theme-change', $event)" />

    <section class="auth-visual">
      <div class="crystal-frame">
        <div class="auth-brand">
          <span><BarChart3 :size="24" /></span>
          <strong>AutoViz Sales Insight</strong>
        </div>
        <h1>自动数据可视化系统</h1>
        <p>面向实木家具销售数据的清洗、推荐分析、预测与 Word 报告导出。</p>
      </div>
    </section>

    <section class="auth-panel">
      <div class="segment">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'"><LockKeyhole :size="17" /> 登录</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'"><UserPlus :size="17" /> 注册</button>
      </div>

      <form v-if="mode === 'login'" class="form-stack" @submit.prevent="login">
        <label>账号或邮箱<input v-model="loginForm.account" required /></label>
        <label>密码<input v-model="loginForm.password" required type="password" /></label>
        <label>
          验证码
          <div class="captcha-row">
            <input v-model="loginForm.captcha_code" required maxlength="4" placeholder="输入图中字符" />
            <img v-if="captchaImage" :src="captchaImage" alt="验证码，点击刷新" role="button" tabindex="0" @click="loadCaptcha" @keydown.enter.prevent="loadCaptcha" />
          </div>
        </label>
        <RouterLink class="forgot-link" to="/forgot-password">忘记密码？</RouterLink>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button class="primary-button" :disabled="loading">{{ loading ? '登录中' : '进入系统' }}</button>
      </form>

      <form v-else class="form-stack" @submit.prevent="register">
        <label>用户名<input v-model="registerForm.username" required minlength="2" /></label>
        <label>邮箱<input v-model="registerForm.email" required type="email" /></label>
        <label>密码<input v-model="registerForm.password" required type="password" minlength="8" /></label>
        <div class="password-checks" aria-live="polite">
          <span v-for="item in passwordChecks" :key="item.key" :class="{ passed: item.passed }">{{ item.label }}</span>
        </div>
        <label>
          确认密码
          <input
            v-model="registerForm.confirm_password"
            required
            type="password"
            minlength="8"
            :class="{ 'input-valid': passwordMatched, 'input-invalid': confirmTouched && !passwordMatched }"
          />
        </label>
        <p v-if="confirmTouched" :class="passwordMatched ? 'success-text compact-text' : 'error-text compact-text'">
          {{ passwordMatched ? '两次密码输入一致' : '两次输入的密码不一致' }}
        </p>
        <label>
          用户角色
          <select v-model="registerForm.role">
            <option value="user">普通用户</option>
            <option value="admin">管理员</option>
          </select>
        </label>
        <label v-if="registerForm.role === 'admin'">管理员密钥<input v-model="registerForm.admin_code" placeholder="请输入管理员密钥" /></label>
        <label>
          验证码
          <div class="captcha-row">
            <input v-model="registerForm.captcha_code" required maxlength="4" placeholder="输入图中字符" />
            <img v-if="captchaImage" :src="captchaImage" alt="验证码，点击刷新" role="button" tabindex="0" @click="loadCaptcha" @keydown.enter.prevent="loadCaptcha" />
          </div>
        </label>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button class="primary-button" :disabled="!canRegister">{{ loading ? '注册中' : '创建账号' }}</button>
      </form>
    </section>
  </div>
</template>
