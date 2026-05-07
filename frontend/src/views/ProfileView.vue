<script setup>
import { onMounted, ref } from 'vue'
import { Camera, Save } from 'lucide-vue-next'
import { getAssetUrl } from '../api/client'
import { userApi } from '../api/modules'

const emit = defineEmits(['auth-updated'])
const user = ref(JSON.parse(localStorage.getItem('current_user') || 'null'))
const form = ref({
  username: '',
  email: '',
  theme_preference: 'arcaea'
})
const message = ref('')

function fillForm(data) {
  user.value = data
  form.value.username = data.username
  form.value.email = data.email
  form.value.theme_preference = data.theme_preference || 'arcaea'
}

async function loadProfile() {
  const { data } = await userApi.me()
  localStorage.setItem('current_user', JSON.stringify(data))
  fillForm(data)
}

async function saveProfile() {
  message.value = ''
  try {
    const { data } = await userApi.update(form.value)
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
  }
}

onMounted(loadProfile)
</script>

<template>
  <div class="profile-layout">
    <header class="page-header">
      <div>
        <span class="eyebrow">PROFILE</span>
        <h1>用户中心</h1>
      </div>
    </header>

    <section class="profile-card">
      <div class="avatar-large">
        <img v-if="user?.avatar_url" :src="getAssetUrl(user.avatar_url)" alt="avatar" />
        <span v-else>{{ user?.username?.slice(0, 1)?.toUpperCase() || 'U' }}</span>
      </div>
      <label class="file-button">
        <Camera :size="18" /> 上传头像
        <input hidden type="file" accept=".jpg,.jpeg,.png,.webp" @change="uploadAvatar" />
      </label>
    </section>

    <section class="profile-form">
      <label>用户名<input v-model="form.username" /></label>
      <label>邮箱<input v-model="form.email" type="email" /></label>
      <label>
        默认主题
        <select v-model="form.theme_preference">
          <option value="arcaea">Arcaea 玻璃水晶</option>
          <option value="rosmontis">迷迭香 轻盈一梦</option>
        </select>
      </label>
      <button class="primary-button" @click="saveProfile"><Save :size="18" /> 保存设置</button>
      <p v-if="message" class="status-text">{{ message }}</p>
    </section>
  </div>
</template>
