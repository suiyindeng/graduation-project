<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { BarChart3 } from 'lucide-vue-next'
import ThemeSwitcher from '../components/ThemeSwitcher.vue'
import { authApi } from '../api/modules'

defineProps({
  theme: {
    type: String,
    default: 'arcaea'
  }
})
const emit = defineEmits(['theme-change'])
const loading = ref(false)
const error = ref('')
const message = ref('')
const step = ref('request')
const arcaeaFallItems = [
  { id: 1, style: { '--fall-left': '8%', '--fall-delay': '-2s', '--fall-duration': '19s', '--fall-drift': '24px', '--fall-size': '12px', '--fall-rotate': '-12deg' } },
  { id: 2, style: { '--fall-left': '18%', '--fall-delay': '-10s', '--fall-duration': '23s', '--fall-drift': '-28px', '--fall-size': '13px', '--fall-rotate': '10deg' } },
  { id: 3, style: { '--fall-left': '29%', '--fall-delay': '-5s', '--fall-duration': '21s', '--fall-drift': '32px', '--fall-size': '11px', '--fall-rotate': '18deg' } },
  { id: 4, style: { '--fall-left': '41%', '--fall-delay': '-13s', '--fall-duration': '25s', '--fall-drift': '-20px', '--fall-size': '14px', '--fall-rotate': '-8deg' } },
  { id: 5, style: { '--fall-left': '55%', '--fall-delay': '-7s', '--fall-duration': '20s', '--fall-drift': '26px', '--fall-size': '12px', '--fall-rotate': '14deg' } },
  { id: 6, style: { '--fall-left': '68%', '--fall-delay': '-16s', '--fall-duration': '26s', '--fall-drift': '-34px', '--fall-size': '13px', '--fall-rotate': '-16deg' } },
  { id: 7, style: { '--fall-left': '79%', '--fall-delay': '-4s', '--fall-duration': '22s', '--fall-drift': '22px', '--fall-size': '11px', '--fall-rotate': '8deg' } },
  { id: 8, style: { '--fall-left': '90%', '--fall-delay': '-12s', '--fall-duration': '24s', '--fall-drift': '-26px', '--fall-size': '14px', '--fall-rotate': '-10deg' } },
]
const captcha = ref({ captcha_id: '', image_url: '' })

const form = ref({
  email: '',
  captcha_code: '',
  reset_code: '',
  new_password: '',
  confirm_password: ''
})

const passwordChecks = computed(() => {
  const password = form.value.new_password
  return [
    { key: 'length', label: '至少 8 位字符', passed: password.length >= 8 },
    { key: 'letter', label: '包含英文字母', passed: /[A-Za-z]/.test(password) },
    { key: 'number', label: '包含数字', passed: /\d/.test(password) },
  ]
})
const passwordStrongEnough = computed(() => passwordChecks.value.every((item) => item.passed))
const confirmTouched = computed(() => form.value.confirm_password.length > 0)
const passwordMatched = computed(() => confirmTouched.value && form.value.new_password === form.value.confirm_password)
const captchaImage = computed(() =>
  captcha.value.image_url && captcha.value.captcha_id ? `${captcha.value.image_url}?v=${captcha.value.captcha_id}` : '',
)
const canRequestCode = computed(
  () => form.value.email.trim().length > 0 && form.value.captcha_code.trim().length === 4 && !loading.value,
)
const canResetPassword = computed(
  () =>
    form.value.email.trim().length > 0 &&
    form.value.reset_code.trim().length === 6 &&
    passwordStrongEnough.value &&
    passwordMatched.value &&
    !loading.value,
)

async function loadCaptcha() {
  const { data } = await authApi.captcha()
  captcha.value = data
  form.value.captcha_code = ''
}

async function requestCode() {
  loading.value = true
  error.value = ''
  message.value = ''
  try {
    const { data } = await authApi.requestPasswordResetCode({
      email: form.value.email,
      captcha_id: captcha.value.captcha_id,
      captcha_code: form.value.captcha_code,
    })
    step.value = 'reset'
    form.value.reset_code = data.dev_reset_code || ''
    message.value = data.dev_reset_code
      ? `开发模式验证码：${data.dev_reset_code}，${data.expires_minutes} 分钟内有效。`
      : data.message
  } catch (err) {
    error.value = err.message
    await loadCaptcha()
  } finally {
    loading.value = false
  }
}

async function resetPassword() {
  loading.value = true
  error.value = ''
  message.value = ''
  try {
    if (!passwordStrongEnough.value) {
      error.value = '新密码至少 8 位，并且需要包含字母和数字'
      return
    }
    if (!passwordMatched.value) {
      error.value = '两次输入的新密码不一致'
      return
    }
    const { data } = await authApi.confirmPasswordReset({
      email: form.value.email,
      reset_code: form.value.reset_code,
      new_password: form.value.new_password,
      confirm_password: form.value.confirm_password,
    })
    message.value = data.message
    step.value = 'done'
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
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
  <div class="auth-layout mode-login">
    <!-- Reversible Arcaea auth decoration: remove this block and the matching CSS block to undo. -->
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
        <h1>重置登录密码</h1>
        <p>通过注册邮箱和验证码确认身份后，设置新的登录密码。</p>
      </div>
    </section>

    <section class="auth-panel">
      <form v-if="step === 'request'" class="form-stack" @submit.prevent="requestCode">
        <label>注册邮箱<input v-model="form.email" required type="email" /></label>
        <label>
          图形验证码
          <div class="captcha-row">
            <input v-model="form.captcha_code" required maxlength="4" placeholder="输入图中字符" />
            <img v-if="captchaImage" :src="captchaImage" alt="验证码，点击刷新" role="button" tabindex="0" @click="loadCaptcha" @keydown.enter.prevent="loadCaptcha" />
          </div>
        </label>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button class="primary-button" :disabled="!canRequestCode">{{ loading ? '验证中' : '获取重置验证码' }}</button>
        <RouterLink class="forgot-link center-link" to="/auth">返回登录</RouterLink>
      </form>

      <form v-else-if="step === 'reset'" class="form-stack" @submit.prevent="resetPassword">
        <p v-if="message" class="status-text">{{ message }}</p>
        <label>邮箱<input v-model="form.email" disabled /></label>
        <label>重置验证码<input v-model="form.reset_code" required maxlength="6" /></label>
        <label>新密码<input v-model="form.new_password" required type="password" minlength="8" /></label>
        <div class="password-checks" aria-live="polite">
          <span v-for="item in passwordChecks" :key="item.key" :class="{ passed: item.passed }">{{ item.label }}</span>
        </div>
        <label>
          确认新密码
          <input
            v-model="form.confirm_password"
            required
            type="password"
            minlength="8"
            :class="{ 'input-valid': passwordMatched, 'input-invalid': confirmTouched && !passwordMatched }"
          />
        </label>
        <p v-if="confirmTouched" :class="passwordMatched ? 'success-text compact-text' : 'error-text compact-text'">
          {{ passwordMatched ? '两次密码输入一致' : '两次输入的新密码不一致' }}
        </p>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button class="primary-button" :disabled="!canResetPassword">{{ loading ? '重置中' : '确认修改密码' }}</button>
      </form>

      <div v-else class="form-stack">
        <p class="status-text">{{ message }}</p>
        <RouterLink class="primary-button" to="/auth">返回登录</RouterLink>
      </div>
    </section>
  </div>
</template>
