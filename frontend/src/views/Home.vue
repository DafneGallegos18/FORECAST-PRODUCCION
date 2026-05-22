<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'

const router = useRouter()
const runs = ref<any[]>([])
const loading = ref(true)
const generating = ref(false)

const loadRuns = async () => {
  loading.value = true
  try {
    const response = await api.get('/api/forecast/runs')
    runs.value = response.data
  } catch (error) {
    console.error('Error fetching runs:', error)
  } finally {
    loading.value = false
  }
}

const generateForecast = async () => {
  generating.value = true
  try {
    const response = await api.post('/api/forecast/run', {})
    // Redirigir al detalle de la nueva corrida
    router.push(`/forecast/${response.data.id}`)
  } catch (error) {
    console.error('Error generating forecast:', error)
    alert('Error al generar el pronóstico. Revisa la consola.')
  } finally {
    generating.value = false
  }
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString()
}

const getStatusSeverity = (status: string) => {
  switch (status) {
    case 'approved': return 'success'
    case 'draft': return 'warn'
    case 'rejected': return 'danger'
    default: return 'info'
  }
}

onMounted(() => {
  loadRuns()
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-2xl font-bold text-gray-800">Historial de Pronósticos</h2>
        <p class="text-gray-500">Visualiza y gestiona las corridas de producción</p>
      </div>
      <Button 
        label="Generar Nuevo Forecast" 
        icon="pi pi-bolt" 
        severity="primary" 
        :loading="generating"
        @click="generateForecast"
      />
    </div>

    <div class="card bg-white p-6 rounded-xl shadow-sm border border-gray-100">
      <DataTable :value="runs" :loading="loading" stripedRows paginator :rows="10">
        <template #empty>No se encontraron pronósticos.</template>
        <template #loading>Cargando datos. Por favor espera.</template>
        
        <Column field="id" header="ID" sortable style="width: 10%"></Column>
        <Column header="Fecha de Creación" sortable style="width: 25%">
          <template #body="{ data }">
            {{ formatDate(data.created_at) }}
          </template>
        </Column>
        <Column field="item_count" header="Items Procesados" sortable style="width: 20%"></Column>
        <Column header="Configuración" style="width: 20%">
          <template #body="{ data }">
            <span class="text-sm text-gray-600">Histórico: {{ data.lookback_days }}d | Meta: {{ data.target_stock_days }}d</span>
          </template>
        </Column>
        <Column field="status" header="Estado" sortable style="width: 15%">
          <template #body="{ data }">
            <Tag :value="data.status.toUpperCase()" :severity="getStatusSeverity(data.status)" />
          </template>
        </Column>
        <Column header="Acciones" style="width: 10%">
          <template #body="{ data }">
            <Button 
              icon="pi pi-eye" 
              outlined 
              rounded 
              severity="info" 
              @click="$router.push(`/forecast/${data.id}`)"
            />
          </template>
        </Column>
      </DataTable>
    </div>
  </div>
</template>
