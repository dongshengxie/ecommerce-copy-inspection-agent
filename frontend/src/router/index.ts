import { createRouter, createWebHistory } from 'vue-router'

import InspectionWorkbenchView from '../views/InspectionWorkbenchView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'workbench',
      component: InspectionWorkbenchView,
    },
  ],
})
