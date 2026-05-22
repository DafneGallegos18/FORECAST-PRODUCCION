import { createApp } from 'vue'
import './style.css'
import 'primeicons/primeicons.css'
import App from './App.vue'

import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import router from './router'
import ToastService from 'primevue/toastservice'

const app = createApp(App)

app.use(router)
app.use(ToastService)
app.use(PrimeVue, {
    theme: {
        preset: Aura
    }
})

app.mount('#app')
