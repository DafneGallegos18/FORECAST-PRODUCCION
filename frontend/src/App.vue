<script setup lang="ts">
// App.vue ahora solo actúa como contenedor (layout principal)
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <!-- Navbar simple -->
    <header class="bg-indigo-600 text-white shadow-md">
      <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <div class="flex items-center gap-2 cursor-pointer" @click="$router.push('/')">
          <i class="pi pi-box text-2xl"></i>
          <h1 class="text-xl font-bold">Production Forecast</h1>
        </div>
      </div>
    </header>

    <!-- Contenido principal enrutado -->
    <main class="flex-grow max-w-7xl mx-auto w-full px-4 py-8">
      <router-view></router-view>
    </main>
  </div>
</template>
