<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import InputNumber from 'primevue/inputnumber'
import SelectButton from 'primevue/selectbutton'
import Dialog from 'primevue/dialog'

const router = useRouter()
const runs = ref<any[]>([])
const loading = ref(true)
const generating = ref(false)
const showConfigDialog = ref(false)

// Configuración predeterminada del pipeline
const config = ref({
  lookback_days: 28,
  target_stock_days: 15,
  shelf_life_safety_pct: 50,
  model: 'ses'
})

const modelOptions = [
  { label: 'Promedio Simple', value: 'simple_avg' },
  { label: 'Ponderado (WMA)', value: 'wma' },
  { label: 'SES', value: 'ses' },
  { label: 'Holt-Winters', value: 'holt_winters' }
]

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
    const response = await api.post('/api/forecast/run', config.value)
    showConfigDialog.value = false
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
        @click="showConfigDialog = true"
      />
    </div>

    <!-- Modal de Configuración para Nueva Corrida -->
    <Dialog v-model:visible="showConfigDialog" header="Configurar Nueva Corrida de Forecast" modal :style="{ width: '500px' }">
      <div class="flex flex-col gap-4 py-2">
        <div class="flex flex-col gap-1">
          <label class="font-semibold text-sm text-gray-700">Días Históricos de Consumo</label>
          <InputNumber v-model="config.lookback_days" :min="7" :max="365" suffix=" días" class="w-full" />
        </div>

        <div class="flex flex-col gap-1">
          <label class="font-semibold text-sm text-gray-700">Stock Objetivo (Cobertura Base)</label>
          <InputNumber v-model="config.target_stock_days" :min="1" :max="90" suffix=" días" class="w-full" />
        </div>

        <div class="flex flex-col gap-1">
          <label class="font-semibold text-sm text-gray-700 flex justify-between">
            <span>% Cobertura Segura de Vida Útil</span>
            <span class="text-indigo-600 font-bold">{{ config.shelf_life_safety_pct }}%</span>
          </label>
          <InputNumber v-model="config.shelf_life_safety_pct" :min="10" :max="100" suffix=" %" class="w-full" />
          <span class="text-xs text-gray-500">Porcentaje de días de caducidad permitido como límite seguro de inventario.</span>
        </div>

        <div class="flex flex-col gap-1">
          <label class="font-semibold text-sm text-gray-700">Modelo Matemático</label>
          <SelectButton v-model="config.model" :options="modelOptions" optionLabel="label" optionValue="value" class="w-full text-xs" />
        </div>
      </div>

      <template #footer>
        <Button label="Cancelar" icon="pi pi-times" text @click="showConfigDialog = false" />
        <Button label="Ejecutar Forecast" icon="pi pi-check" severity="success" :loading="generating" @click="generateForecast" />
      </template>
    </Dialog>

    <div class="card bg-white p-6 rounded-xl shadow-sm border border-gray-100">
      <DataTable :value="runs" :loading="loading" stripedRows paginator :rows="10">
        <template #empty>No se encontraron pronósticos.</template>
        <template #loading>Cargando datos. Por favor espera.</template>
        
        <Column field="id" header="ID" sortable style="width: 10%"></Column>
        <Column header="Fecha de Creación" sortable style="width: 20%">
          <template #body="{ data }">
            {{ formatDate(data.created_at) }}
          </template>
        </Column>
        <Column field="item_count" header="Items Procesados" sortable style="width: 15%"></Column>
        <Column header="Configuración" style="width: 30%">
          <template #body="{ data }">
            <span class="text-sm text-gray-600">
              Histórico: {{ data.lookback_days }}d | Meta: {{ data.target_stock_days }}d | % Vida Útil: {{ data.shelf_life_safety_pct ?? 50 }}%
            </span>
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
