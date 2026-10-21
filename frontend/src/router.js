import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'dashboard', component: () => import('./views/DashboardView.vue') },
  { path: '/charts', name: 'charts', component: () => import('./views/ChartsView.vue') },
  { path: '/tasks', name: 'tasks', component: () => import('./views/TasksView.vue') },
  { path: '/library', name: 'library', component: () => import('./views/LibraryView.vue') },
  { path: '/video/:id', name: 'video', component: () => import('./views/VideoDetailView.vue') },
  { path: '/schedules', name: 'schedules', component: () => import('./views/SchedulesView.vue') },
  { path: '/settings', name: 'settings', component: () => import('./views/SettingsView.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
