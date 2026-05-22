<script setup lang="ts">
import { ref } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import api from '../services/api'
import { useToast } from 'primevue/usetoast'

const props = defineProps<{
  items: any[]
  loading: boolean
  isDraft?: boolean
}>()

const emit = defineEmits<{
  (e: 'update-item', item: any): void
}>()

const toast = useToast()
const expandedRows = ref({})
const dt = ref()
const filters = ref({
  global: { value: null, matchMode: 'contains' }
})

// Edición de la celda PADRE (Ajuste Global)
const onParentEditComplete = async (event: any) => {
  if (!props.isDraft) {
    event.preventDefault()
    return
  }
  let { data, newValue, field } = event;
  if (newValue !== null && newValue !== data[field] && newValue >= 0) {
    try {
      const response = await api.patch(`/api/forecast/items/${data.id}/adjust`, {
        new_value: newValue,
        reason: 'Ajuste general manual'
      })
      // Emitimos el item completo actualizado (viene desde el backend con el nuevo general_adjustment)
      emit('update-item', response.data)
      toast.add({ severity: 'success', summary: 'Ajuste General Guardado', detail: `Total de ${data.item_code} actualizado.`, life: 2000 })
    } catch (e) {
      toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo guardar el ajuste.', life: 3000 })
      event.preventDefault()
    }
  } else {
    event.preventDefault()
  }
}

// Edición de la celda HIJO (Ajuste por Cliente)
const onClientEditComplete = async (event: any) => {
  if (!props.isDraft) {
    event.preventDefault()
    return
  }
  let { data: client, newValue, field } = event;
  if (newValue !== null && newValue !== client[field] && newValue >= 0) {
    try {
      const response = await api.patch(`/api/forecast/clients/${client.id}/adjust`, {
        new_value: newValue,
        reason: 'Ajuste cliente manual'
      })
      // El backend devuelve el PADRE completo actualizado (response.data)
      // porque su total general cambió al subir/bajar este cliente.
      emit('update-item', response.data)
      toast.add({ severity: 'success', summary: 'Ajuste de Cliente Guardado', detail: `Necesidad para ${client.card_name} actualizada.`, life: 2000 })
    } catch (e) {
      toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo guardar el ajuste del cliente.', life: 3000 })
      event.preventDefault()
    }
  } else {
    event.preventDefault()
  }
}

const getConfidenceSeverity = (score: number | null) => {
  if (score === null) return 'secondary'
  if (score > 0.8) return 'success'
  if (score > 0.5) return 'warn'
  return 'danger'
}
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-4">
      <Button icon="pi pi-file-excel" severity="secondary" outlined label="Exportar CSV" @click="dt.exportCSV()" />
      <span class="relative">
        <i class="pi pi-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
        <InputText v-model="filters['global'].value" placeholder="Buscar producto..." class="pl-10" />
      </span>
    </div>

    <DataTable 
      ref="dt"
      v-model:expandedRows="expandedRows" 
      v-model:filters="filters"
      :value="items" 
      :loading="loading" 
      editMode="cell" 
      @cell-edit-complete="onParentEditComplete"
      dataKey="id"
      paginator 
      :rows="20"
      :rowsPerPageOptions="[10, 20, 50]"
      stripedRows
      class="text-sm border rounded-xl overflow-hidden"
      :globalFilterFields="['item_code', 'item_name']"
    >
      <template #empty>No hay productos en este pronóstico.</template>

      <!-- Expansión de fila (Desglose por cliente) -->
      <Column expander style="width: 3rem" />

      <!-- Datos básicos (Nivel SKU) -->
      <Column field="item_code" header="SKU" sortable style="width: 10%"></Column>
      <Column field="item_name" header="Producto" sortable style="width: 20%"></Column>
      
      <Column field="stock_whs_01" header="Stock Actual" sortable style="width: 10%">
        <template #body="{ data }">
          <span class="font-medium">{{ data.stock_whs_01.toLocaleString() }}</span>
          <span class="text-xs text-gray-500 ml-1">{{ data.unit }}</span>
        </template>
      </Column>
      
      <Column field="avg_daily_consumption" header="Consumo Diario" sortable style="width: 10%">
        <template #body="{ data }">
          {{ data.avg_daily_consumption.toFixed(2) }}
        </template>
      </Column>

      <Column field="target_inventory_consumption" header="Objetivo Inv." sortable style="width: 10%">
        <template #body="{ data }">
          <span class="text-blue-600 font-medium">{{ Math.ceil(data.target_inventory_consumption).toLocaleString() }}</span>
        </template>
      </Column>
      
      <Column field="committed_qty" header="Comprometido" sortable style="width: 10%">
        <template #body="{ data }">
          <span class="text-purple-600 font-medium">{{ data.committed_qty.toLocaleString() }}</span>
        </template>
      </Column>

      <!-- Necesidad del Sistema (Suma de los calculados) -->
      <Column field="calculated_need" header="Sugerencia" sortable style="width: 10%">
        <template #body="{ data }">
          <span class="text-gray-500">{{ Math.ceil(data.calculated_need).toLocaleString() }}</span>
        </template>
      </Column>

      <!-- Necesidad Final del Padre (Editable) -->
      <Column field="final_need" header="Total a Producir (Editar)" sortable style="width: 15%">
        <template #body="{ data }">
          <div :class="['flex items-center gap-2 px-2 py-1 rounded border transition-colors w-full justify-between', isDraft ? 'cursor-pointer bg-blue-50 border-blue-100 hover:bg-blue-100' : 'bg-gray-50 border-gray-100 text-gray-500']">
            <span :class="isDraft ? 'font-bold text-blue-800' : ''">{{ Math.ceil(data.final_need).toLocaleString() }}</span>
            <i v-if="isDraft" class="pi pi-pencil text-xs text-blue-400"></i>
          </div>
        </template>
        <template #editor="{ data, field }">
          <InputNumber 
            v-if="isDraft"
            v-model="data[field]" 
            autofocus 
            mode="decimal" 
            :min="0" 
            class="w-full"
          />
          <span v-else>{{ Math.ceil(data[field]) }}</span>
        </template>
      </Column>

      <!-- Desglose por Cliente (Fila Expandida) -->
      <template #expansion="{ data: parentData }">
        <div class="p-4 bg-gray-50 rounded-b-lg border-x border-b border-gray-200 shadow-inner -mt-2">
          
          <div class="flex justify-between items-center mb-4">
            <h4 class="font-bold text-indigo-800 flex items-center gap-2">
              <i class="pi pi-users"></i> Desglose por Cliente
            </h4>
            
            <div class="flex gap-4 text-xs bg-white px-3 py-2 rounded shadow-sm border border-gray-100">
              <div>
                <span class="text-gray-500 uppercase font-bold mr-2">Modelo Usado:</span>
                <span class="font-mono bg-indigo-50 text-indigo-800 px-1 rounded border border-indigo-100">{{ parentData.model_used }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-gray-500 uppercase font-bold">Confianza:</span>
                <Tag v-if="parentData.confidence_score !== null" :severity="getConfidenceSeverity(parentData.confidence_score)">
                  {{ (parentData.confidence_score * 100).toFixed(1) }}%
                </Tag>
                <Tag v-else severity="secondary" value="N/A" />
              </div>
              <div v-if="parentData.general_adjustment !== 0" class="flex items-center gap-2 text-orange-600 font-bold">
                <i class="pi pi-exclamation-triangle"></i>
                <span>Ajuste Gral / Inventario: {{ Math.ceil(parentData.general_adjustment) }}</span>
              </div>
            </div>
          </div>

          <!-- Sub-Tabla de Clientes -->
          <DataTable 
            :value="parentData.clients" 
            editMode="cell" 
            @cell-edit-complete="onClientEditComplete"
            class="text-sm p-datatable-sm shadow-sm rounded-lg overflow-hidden border border-gray-200"
          >
            <Column field="card_code" header="Cód. Cliente" style="width: 15%"></Column>
            <Column field="card_name" header="Nombre del Cliente" style="width: 25%">
              <template #body="{ data }">
                <span :class="{'italic text-gray-500': data.card_code === 'GENERAL'}">
                  {{ data.card_name }}
                </span>
              </template>
            </Column>
            <Column field="avg_daily_consumption" header="Consumo Diario" style="width: 15%">
              <template #body="{ data }">
                {{ data.avg_daily_consumption.toFixed(2) }}
              </template>
            </Column>
            <Column field="committed_qty" header="Comprometido" style="width: 15%">
              <template #body="{ data }">
                <span class="text-purple-600 font-medium">{{ data.committed_qty.toLocaleString() }}</span>
              </template>
            </Column>
            <Column field="calculated_need" header="Sugerencia" style="width: 15%">
              <template #body="{ data }">
                <span class="text-gray-500">{{ Math.ceil(data.calculated_need).toLocaleString() }}</span>
              </template>
            </Column>
            
            <!-- Edición de cliente -->
            <Column field="final_need" header="Ajuste Cliente (Editar)" style="width: 15%">
              <template #body="{ data }">
                <div :class="['flex items-center gap-2 px-2 py-1 rounded border transition-colors w-full justify-between', isDraft ? 'cursor-pointer bg-green-50 border-green-200 hover:bg-green-100' : 'bg-gray-50 border-gray-100 text-gray-500']">
                  <span :class="isDraft ? 'font-bold text-green-800' : ''">{{ Math.ceil(data.final_need).toLocaleString() }}</span>
                  <i v-if="isDraft" class="pi pi-pencil text-xs text-green-500"></i>
                </div>
              </template>
              <template #editor="{ data, field }">
                <InputNumber 
                  v-if="isDraft"
                  v-model="data[field]" 
                  autofocus 
                  mode="decimal" 
                  :min="0" 
                  class="w-full"
                />
                <span v-else>{{ Math.ceil(data[field]) }}</span>
              </template>
            </Column>
          </DataTable>

        </div>
      </template>

    </DataTable>
  </div>
</template>
