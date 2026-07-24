<script setup lang="ts">
import { ref, onMounted } from 'vue'

const isDarkMode = ref(false)

const applyTheme = () => {
  if (isDarkMode.value) {
    document.documentElement.classList.add('dark', 'p-dark')
    localStorage.setItem('theme', 'dark')
  } else {
    document.documentElement.classList.remove('dark', 'p-dark')
    localStorage.setItem('theme', 'light')
  }
}

const toggleDarkMode = () => {
  isDarkMode.value = !isDarkMode.value
  applyTheme()
}

onMounted(() => {
  const savedTheme = localStorage.getItem('theme')
  if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    isDarkMode.value = true
  } else {
    isDarkMode.value = false
  }
  applyTheme()
})
</script>

<template>
  <div class="min-h-screen bg-gray-100 dark:bg-slate-900 text-gray-900 dark:text-slate-100 flex flex-col transition-colors duration-200">
    <!-- Navbar simple -->
    <header class="bg-indigo-600 dark:bg-slate-800 text-white shadow-md border-b dark:border-slate-700 transition-colors">
      <div class="max-w-[98%] mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-2 cursor-pointer" @click="$router.push('/')">
          <i class="pi pi-box text-2xl text-indigo-200 dark:text-indigo-400"></i>
          <h1 class="text-xl font-bold font-sans tracking-tight">Production Forecast</h1>
        </div>

        <div class="flex items-center gap-6">
          <nav class="flex items-center gap-6 text-sm font-medium">
            <router-link to="/" class="hover:text-indigo-200 dark:hover:text-indigo-300 transition-colors" active-class="text-indigo-200 dark:text-indigo-400 border-b-2 border-indigo-200 dark:border-indigo-400 pb-1">Historial</router-link>
            <router-link to="/exclusions" class="hover:text-indigo-200 dark:hover:text-indigo-300 transition-colors" active-class="text-indigo-200 dark:text-indigo-400 border-b-2 border-indigo-200 dark:border-indigo-400 pb-1">Exclusiones</router-link>
            <router-link to="/special-demands" class="hover:text-indigo-200 dark:hover:text-indigo-300 transition-colors" active-class="text-indigo-200 dark:text-indigo-400 border-b-2 border-indigo-200 dark:border-indigo-400 pb-1">Demandas Especiales</router-link>
          </nav>

          <!-- Conmutador de modo claro / oscuro -->
          <button 
            @click="toggleDarkMode" 
            class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-700 dark:bg-slate-700 hover:bg-indigo-800 dark:hover:bg-slate-600 text-xs font-semibold text-white transition-all shadow-inner"
            :title="isDarkMode ? 'Cambiar a Modo Claro' : 'Cambiar a Modo Oscuro'"
          >
            <i :class="isDarkMode ? 'pi pi-sun text-amber-300' : 'pi pi-moon text-indigo-200'"></i>
            <span>{{ isDarkMode ? 'Claro' : 'Oscuro' }}</span>
          </button>
        </div>
      </div>
    </header>

    <!-- Contenido principal enrutado -->
    <main class="flex-grow max-w-[98%] mx-auto w-full px-2 py-6">
      <router-view></router-view>
    </main>
  </div>
</template>

