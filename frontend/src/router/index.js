import { createRouter, createWebHistory } from 'vue-router'
import AuthView from '../views/AuthView.vue'
import DashboardView from '../views/DashboardView.vue'
import AdminView from '../views/AdminView.vue'
import ProfileView from '../views/ProfileView.vue'
import ForgotPasswordView from '../views/ForgotPasswordView.vue'
import SystemStatsView from '../views/SystemStatsView.vue'
import LegendAnalysisView from '../views/LegendAnalysisView.vue'
import LedgerView from '../views/LedgerView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/auth', component: AuthView },
    { path: '/forgot-password', component: ForgotPasswordView },
    { path: '/dashboard', component: DashboardView, meta: { requiresAuth: true } },
    { path: '/ledger', component: LedgerView, meta: { requiresAuth: true } },
    { path: '/legend-analysis', component: LegendAnalysisView, meta: { requiresAuth: true } },
    { path: '/admin', component: AdminView, meta: { requiresAuth: true, requiresAdmin: true } },
    { path: '/admin/stats', component: SystemStatsView, meta: { requiresAuth: true, requiresSuperAdmin: true } },
    { path: '/profile', component: ProfileView, meta: { requiresAuth: true } }
  ]
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  const user = JSON.parse(localStorage.getItem('current_user') || 'null')
  if (to.meta.requiresAuth && !token) {
    return '/auth'
  }
  if (to.meta.requiresAdmin && !['admin', 'super_admin'].includes(user?.role)) {
    return '/dashboard'
  }
  if (to.meta.requiresSuperAdmin && user?.role !== 'super_admin') {
    return '/dashboard'
  }
  if ((to.path === '/auth' || to.path === '/forgot-password') && token) {
    return '/dashboard'
  }
  return true
})

export default router
