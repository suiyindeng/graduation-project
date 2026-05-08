import { api } from './client'

export const authApi = {
  login: (payload) => api.post('/auth/login', payload),
  register: (payload) => api.post('/auth/register', payload),
  captcha: () => api.get('/auth/captcha'),
  requestPasswordResetCode: (payload) => api.post('/auth/password-reset/code', payload),
  confirmPasswordReset: (payload) => api.post('/auth/password-reset/confirm', payload)
}

export const userApi = {
  me: () => api.get('/users/me'),
  stats: () => api.get('/users/me/stats'),
  update: (payload) => api.put('/users/me', payload),
  avatar: (formData) => api.post('/users/avatar', formData)
}

export const datasetApi = {
  list: () => api.get('/datasets'),
  upload: (formData) => api.post('/datasets/upload', formData),
  detail: (id) => api.get(`/datasets/${id}`),
  chartAnalysis: (id) => api.get(`/datasets/${id}/chart-analysis`),
  forecast: (id, payload) => api.post(`/datasets/${id}/forecast`, payload),
  modelRuns: (id) => api.get(`/datasets/${id}/model-runs`),
  remove: (id) => api.delete(`/datasets/${id}`)
}

export const reportApi = {
  exportWord: (payload) =>
    api.post('/reports/export', payload, {
      responseType: 'blob'
    })
}

export const adminApi = {
  users: () => api.get('/admin/users'),
  datasets: () => api.get('/admin/datasets'),
  stats: (params) => api.get('/admin/stats', { params }),
  updateUser: (id, payload) => api.put(`/admin/users/${id}`, payload),
  updateUserRole: (id, payload) => api.put(`/admin/users/${id}/role`, payload)
}
