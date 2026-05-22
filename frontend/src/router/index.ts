import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import ForecastDetail from '../views/ForecastDetail.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: Home
    },
    {
      path: '/forecast/:id',
      name: 'forecast-detail',
      component: ForecastDetail,
      props: true
    }
  ]
})

export default router
