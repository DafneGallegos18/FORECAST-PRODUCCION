<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../services/api'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'
import Toast from 'primevue/toast'
import { useToast } from 'primevue/usetoast'

const toast = useToast()
const exclusions = ref<any[]>([])
const loading = ref(true)
const displayDialog = ref(false)

const newExclusion = ref({
  exclusion_type: 'item_code',
  value: '',
  secondary_value: '',
  description: '',
  case_sensitive: false
})

const exclusionTypes = ref([
  { label: 'Excluir SKU / Código de Producto', value: 'item_code' },
  { label: 'Excluir Cliente (CardCode)', value: 'card_code' },
  { label: 'Excluir Cliente + Producto', value: 'card_item' },
  { label: 'Excluir Clientes que contengan nombre', value: 'card_name_contains' },
  { label: 'Excluir Grupo de Clientes (ID)', value: 'customer_group' }
])

const loadExclusions = async () => {
  loading.value = true
  try {
    const response = await api.get('/api/exclusions/?active_only=false')
    exclusions.value = response.data
  } catch (error) {
    console.error('Error fetching exclusions:', error)
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudieron cargar las exclusiones.', life: 3000 })
  } finally {
    loading.value = false
  }
}

const toggleExclusion = async (id: number) => {
  try {
    await api.patch(`/api/exclusions/${id}/toggle`)
    toast.add({ severity: 'success', summary: 'Actualizado', detail: 'El estado de la exclusión fue modificado.', life: 3000 })
    loadExclusions()
  } catch (error) {
    console.error('Error toggling exclusion:', error)
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo cambiar el estado.', life: 3000 })
  }
}

const deleteExclusion = async (id: number) => {
  if (!confirm('¿Estás seguro de eliminar permanentemente esta regla de exclusión?')) return
  try {
    await api.delete(`/api/exclusions/${id}`)
    toast.add({ severity: 'success', summary: 'Eliminado', detail: 'Exclusión eliminada.', life: 3000 })
    loadExclusions()
  } catch (error) {
    console.error('Error deleting exclusion:', error)
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo eliminar.', life: 3000 })
  }
}

const saveExclusion = async () => {
  if (!newExclusion.value.value) {
    alert('Por favor, ingresa el valor principal.')
    return
  }
  try {
    await api.post('/api/exclusions/', newExclusion.value)
    toast.add({ severity: 'success', summary: 'Creada', detail: 'Regla de exclusión agregada con éxito.', life: 3000 })
    displayDialog.value = false
    loadExclusions()
    // Limpiar formulario
    newExclusion.value = {
      exclusion_type: 'item_code',
      value: '',
      secondary_value: '',
      description: '',
      case_sensitive: false
    }
  } catch (error) {
    console.error('Error saving exclusion:', error)
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo guardar la exclusión.', life: 3000 })
  }
}

const getTypeName = (type: string) => {
  const match = exclusionTypes.value.find(t => t.value === type)
  return match ? match.label : type
}

onMounted(() => {
  loadExclusions()
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <Toast />
    
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-2xl font-bold text-gray-800 font-sans">Exclusiones Dinámicas</h2>
        <p class="text-gray-500">Administra los filtros de SAP B1 que excluyen productos, clientes o grupos del cálculo</p>
      </div>
      <Button 
        label="Nueva Regla de Exclusión" 
        icon="pi pi-plus" 
        severity="primary" 
        @click="displayDialog = true"
      />
    </div>

    <div class="card bg-white p-6 rounded-xl shadow-sm border border-gray-100">
      <DataTable :value="exclusions" :loading="loading" stripedRows paginator :rows="10">
        <template #empty>No se encontraron reglas de exclusión.</template>
        <template #loading>Cargando datos. Por favor espera.</template>
        
        <Column header="Tipo" sortable style="width: 25%">
          <template #body="{ data }">
            {{ getTypeName(data.exclusion_type) }}
          </template>
        </Column>
        
        <Column header="Valor Principal" sortable style="width: 15%">
          <template #body="{ data }">
            <span class="font-mono bg-gray-100 text-gray-800 px-2 py-1 rounded text-xs">{{ data.value }}</span>
          </template>
        </Column>

        <Column header="Valor Secundario (ItemCode)" style="width: 15%">
          <template #body="{ data }">
            <span v-if="data.secondary_value" class="font-mono bg-gray-100 text-gray-800 px-2 py-1 rounded text-xs">
              {{ data.secondary_value }}
            </span>
            <span v-else class="text-gray-400">—</span>
          </template>
        </Column>

        <Column field="description" header="Descripción" style="width: 25%"></Column>
        
        <Column field="is_active" header="Estado" sortable style="width: 10%">
          <template #body="{ data }">
            <Tag 
              :value="data.is_active ? 'ACTIVO' : 'INACTIVO'" 
              :severity="data.is_active ? 'success' : 'danger'" 
              class="cursor-pointer"
              @click="toggleExclusion(data.id)"
            />
          </template>
        </Column>

        <Column header="Acciones" style="width: 10%">
          <template #body="{ data }">
            <div class="flex gap-2">
              <Button 
                icon="pi pi-trash" 
                outlined 
                rounded 
                severity="danger" 
                @click="deleteExclusion(data.id)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- Diálogo para Agregar Exclusión -->
    <Dialog v-model:visible="displayDialog" modal header="Nueva Regla de Exclusión" :style="{ width: '450px' }">
      <div class="flex flex-col gap-4 mt-2">
        <div class="flex flex-col gap-2">
          <label for="type" class="font-semibold text-gray-700">Tipo de Exclusión</label>
          <Dropdown 
            id="type"
            v-model="newExclusion.exclusion_type" 
            :options="exclusionTypes" 
            optionLabel="label" 
            optionValue="value"
            placeholder="Selecciona el tipo" 
            class="w-full"
          />
        </div>

        <div class="flex flex-col gap-2">
          <label for="value" class="font-semibold text-gray-700">
            {{ newExclusion.exclusion_type === 'card_name_contains' ? 'Texto a buscar' : 'Código o ID a filtrar' }}
          </label>
          <InputText 
            id="value" 
            v-model="newExclusion.value" 
            placeholder="Ej. 2112035, C056, Empleados..." 
            class="w-full"
          />
        </div>

        <div v-if="newExclusion.exclusion_type === 'card_item'" class="flex flex-col gap-2">
          <label for="secondary" class="font-semibold text-gray-700">SKU / Código de Producto</label>
          <InputText 
            id="secondary" 
            v-model="newExclusion.secondary_value" 
            placeholder="Ej. 2112028" 
            class="w-full"
          />
        </div>

        <div class="flex flex-col gap-2">
          <label for="desc" class="font-semibold text-gray-700">Descripción / Motivo</label>
          <InputText 
            id="desc" 
            v-model="newExclusion.description" 
            placeholder="Ej. SKU de sólo conversión" 
            class="w-full"
          />
        </div>
      </div>

      <template #footer>
        <Button label="Cancelar" icon="pi pi-times" text @click="displayDialog = false" />
        <Button label="Guardar" icon="pi pi-check" severity="primary" @click="saveExclusion" />
      </template>
    </Dialog>
  </div>
</template>
