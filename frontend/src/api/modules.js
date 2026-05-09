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

export const ledgerApi = {
  fields: () => api.get('/ledger/fields'),
  createField: (payload) => api.post('/ledger/fields', payload),
  removeField: (id) => api.delete(`/ledger/fields/${id}`),
  records: () => api.get('/ledger/records'),
  importExcel: (formData) => api.post('/ledger/import', formData),
  createRecord: (payload) => api.post('/ledger/records', payload),
  updateRecord: (id, payload) => api.put(`/ledger/records/${id}`, payload),
  removeRecord: (id) => api.delete(`/ledger/records/${id}`),
  exportExcel: () => api.get('/ledger/export', { responseType: 'blob' }),
  toDataset: (payload) => api.post('/ledger/to-dataset', payload),
  groupPreview: (payload) => api.post('/ledger/group-preview', payload),
  groupExport: (payload) => api.post('/ledger/group-export', payload, { responseType: 'blob' }),
  groupToDataset: (payload) => api.post('/ledger/group-to-dataset', payload)
}

export const adminApi = {
  users: () => api.get('/admin/users'),
  datasets: () => api.get('/admin/datasets'),
  stats: (params) => api.get('/admin/stats', { params }),
  updateUser: (id, payload) => api.put(`/admin/users/${id}`, payload),
  updateUserRole: (id, payload) => api.put(`/admin/users/${id}/role`, payload)
}
