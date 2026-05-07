import { createRouter, createWebHistory } from 'vue-router'
import AuthView from '../views/AuthView.vue'
import DashboardView from '../views/DashboardView.vue'
import AdminView from '../views/AdminView.vue'
import ProfileView from '../views/ProfileView.vue'
import ForgotPasswordView from '../views/ForgotPasswordView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/auth', component: AuthView },
    { path: '/forgot-password', component: ForgotPasswordView },
    { path: '/dashboard', component: DashboardView, meta: { requiresAuth: true } },
    { path: '/admin', component: AdminView, meta: { requiresAuth: true, requiresAdmin: true } },
    { path: '/profile', component: ProfileView, meta: { requiresAuth: true } }
  ]
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  const user = JSON.parse(localStorage.getItem('current_user') || 'null')
  if (to.meta.requiresAuth && !token) {
    return '/auth'
  }
  if (to.meta.requiresAdmin && user?.role !== 'admin') {
    return '/dashboard'
  }
  if ((to.path === '/auth' || to.path === '/forgot-password') && token) {
    return '/dashboard'
  }
  return true
})

export default router
