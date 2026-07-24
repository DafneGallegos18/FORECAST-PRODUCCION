<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import ForecastTable from '../components/ForecastTable.vue'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Toast from 'primevue/toast'
import { useToast } from 'primevue/usetoast'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const runId = route.params.id
const run = ref<any>(null)
const items = ref<any[]>([])
const loading = ref(true)
const approving = ref(false)

const loadDetails = async () => {
  loading.value = true
  try {
    const response = await api.get(`/api/forecast/runs/${runId}`)
    run.value = response.data
    items.value = response.data.items || []
  } catch (error) {
    console.error('Error loading forecast detail:', error)
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo cargar el pronóstico.', life: 3000 })
  } finally {
    loading.value = false
  }
}

// Handler para la actualización de un item (viene de ForecastTable)
const handleItemUpdate = (updatedItem: any) => {
  const index = items.value.findIndex(i => i.id === updatedItem.id)
  if (index !== -1) {
    items.value[index] = updatedItem
  }
}

const approveForecast = async () => {
  if (!confirm('¿Estás seguro de aprobar este pronóstico? Ya no se podrán hacer ajustes manuales.')) return
  
  approving.value = true
  try {
    await api.post(`/api/forecast/runs/${runId}/approve`, {
      approved_by: 'Usuario UI',
      notes: 'Aprobado desde Dashboard'
    })
    toast.add({ severity: 'success', summary: 'Aprobado', detail: 'El pronóstico ha sido aprobado.', life: 3000 })
    loadDetails() // Recargar para actualizar el estado
  } catch (error) {
    console.error('Error approving run:', error)
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo aprobar.', life: 3000 })
  } finally {
    approving.value = false
  }
}

const isDraft = computed(() => run.value?.status === 'draft')

onMounted(() => {
  loadDetails()
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <Toast />
    
    <div class="flex items-center gap-4 text-gray-500 mb-2">
      <Button icon="pi pi-arrow-left" text rounded @click="router.push('/')" />
      <span>Volver al historial</span>
    </div>

    <!-- Skeleton o Loading -->
    <div v-if="loading && !run" class="card bg-white p-6 rounded-xl shadow-sm text-center">
      <i class="pi pi-spin pi-spinner text-3xl text-indigo-500 mb-4"></i>
      <p>Cargando detalles de la corrida...</p>
    </div>

    <template v-else-if="run">
      <!-- Header -->
      <div class="card bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div class="flex items-center gap-3 mb-1">
            <h2 class="text-2xl font-bold text-gray-800">Corrida #{{ run.id }}</h2>
            <Tag :value="run.status.toUpperCase()" :severity="run.status === 'approved' ? 'success' : 'warn'" />
          </div>
          <p class="text-sm text-gray-500">
            Generado el {{ new Date(run.created_at).toLocaleString() }} 
            | Histórico: {{ run.lookback_days }} días 
            | Meta Base: {{ run.target_stock_days }} días
            | % Vida Útil Segura: {{ run.shelf_life_safety_pct ?? 50 }}%
          </p>
        </div>
        
        <div class="flex gap-3">
          <Button 
            v-if="isDraft"
            label="Aprobar Pronóstico" 
            icon="pi pi-check" 
            severity="success" 
            :loading="approving"
            @click="approveForecast"
          />
        </div>
      </div>

      <!-- Tabla principal -->
      <div class="card bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <div v-if="isDraft" class="mb-4 p-3 bg-blue-50 text-blue-800 rounded-md flex gap-2 items-center text-sm border border-blue-100">
          <i class="pi pi-info-circle"></i>
          <span><b>Modo de edición:</b> Haz doble clic en cualquier celda de la columna "Ajuste Final" para modificar el valor manualmente y presiona Enter para guardar.</span>
        </div>
        
        <ForecastTable 
          :items="items" 
          :loading="loading" 
          :is-draft="isDraft"
          :target-stock-days="run?.target_stock_days"
          @update-item="handleItemUpdate" 
        />
      </div>
    </template>
  </div>
</template>
