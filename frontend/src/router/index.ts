import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import ForecastDetail from '../views/ForecastDetail.vue'
import Exclusions from '../views/Exclusions.vue'
import SpecialDemands from '../views/SpecialDemands.vue'

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
    },
    {
      path: '/exclusions',
      name: 'exclusions',
      component: Exclusions
    },
    {
      path: '/special-demands',
      name: 'special-demands',
      component: SpecialDemands
    }
  ]
})

export default router
