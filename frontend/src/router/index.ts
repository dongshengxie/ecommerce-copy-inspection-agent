import { createRouter, createWebHistory } from 'vue-router'

import WorkbenchPlaceholderView from '../views/WorkbenchPlaceholderView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'workbench',
      component: WorkbenchPlaceholderView,
    },
  ],
})
