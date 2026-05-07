import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
  timeout: 120000
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

export function getAssetUrl(path) {
  if (!path) return ''
  return path.startsWith('http') ? path : path
}
