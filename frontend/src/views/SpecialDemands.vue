<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../services/api'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Toast from 'primevue/toast'
import { useToast } from 'primevue/usetoast'

const toast = useToast()
const demands = ref<any[]>([])
const loading = ref(true)
const displayDialog = ref(false)
const isEditing = ref(false)
const currentEditingId = ref<number | null>(null)

// Catálogos SAP y Búsqueda
const sapProducts = ref<any[]>([])
const sapClients = ref<any[]>([])
const loadingSapData = ref(false)

const productSearchQuery = ref('')
const showProductDropdown = ref(false)

const clientSearchQuery = ref('')
const showClientDropdown = ref(false)

const newDemand = ref({
  item_code: '',
  item_name: '',
  card_code: '',
  card_name: '',
  quantity: 0,
  start_date: '',
  end_date: '',
  reason: ''
})

const loadDemands = async () => {
  loading.value = true
  try {
    const response = await api.get('/api/special-demands/')
    demands.value = response.data
  } catch (error) {
    console.error('Error fetching special demands:', error)
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudieron cargar las demandas especiales.', life: 3000 })
  } finally {
    loading.value = false
  }
}

const loadSapCatalogs = async () => {
  if (sapProducts.value.length > 0 && sapClients.value.length > 0) return
  loadingSapData.value = true
  try {
    const [prodRes, clientRes] = await Promise.all([
      api.get('/api/special-demands/sap-products'),
      api.get('/api/special-demands/sap-clients')
    ])
    sapProducts.value = prodRes.data || []
    sapClients.value = clientRes.data || []
  } catch (error) {
    console.error('Error al cargar catálogos de SAP:', error)
  } finally {
    loadingSapData.value = false
  }
}

// Búsqueda interactiva de Productos en tiempo real
const filteredProducts = computed(() => {
  if (!productSearchQuery.value.trim()) {
    return sapProducts.value.slice(0, 30)
  }
  const q = productSearchQuery.value.toLowerCase().trim()
  return sapProducts.value
    .filter(p => (p.ItemCode && p.ItemCode.toLowerCase().includes(q)) || (p.ItemName && p.ItemName.toLowerCase().includes(q)))
    .slice(0, 40)
})

const selectProduct = (p: any) => {
  newDemand.value.item_code = p.ItemCode
  newDemand.value.item_name = p.ItemName
  productSearchQuery.value = `[${p.ItemCode}] ${p.ItemName}`
  showProductDropdown.value = false
}

// Búsqueda interactiva de Clientes en tiempo real
const filteredClients = computed(() => {
  if (!clientSearchQuery.value.trim()) {
    return sapClients.value.slice(0, 30)
  }
  const q = clientSearchQuery.value.toLowerCase().trim()
  return sapClients.value
    .filter(c => (c.CardCode && c.CardCode.toLowerCase().includes(q)) || (c.CardName && c.CardName.toLowerCase().includes(q)))
    .slice(0, 40)
})

const selectClient = (c: any | null) => {
  if (!c) {
    newDemand.value.card_code = ''
    newDemand.value.card_name = ''
    clientSearchQuery.value = ''
  } else {
    newDemand.value.card_code = c.CardCode
    newDemand.value.card_name = c.CardName
    clientSearchQuery.value = `[${c.CardCode}] ${c.CardName}`
  }
  showClientDropdown.value = false
}

const openCreateDialog = () => {
  isEditing.value = false
  currentEditingId.value = null
  productSearchQuery.value = ''
  clientSearchQuery.value = ''
  showProductDropdown.value = false
  showClientDropdown.value = false

  newDemand.value = {
    item_code: '',
    item_name: '',
    card_code: '',
    card_name: '',
    quantity: 0,
    start_date: new Date().toISOString().slice(0, 10),
    end_date: '',
    reason: ''
  }
  displayDialog.value = true
  loadSapCatalogs()
}

const openEditDialog = (demand: any) => {
  isEditing.value = true
  currentEditingId.value = demand.id
  productSearchQuery.value = demand.item_code ? `[${demand.item_code}] ${demand.item_name || ''}` : ''
  clientSearchQuery.value = demand.card_code ? `[${demand.card_code}] ${demand.card_name || ''}` : ''
  showProductDropdown.value = false
  showClientDropdown.value = false
  
  newDemand.value = {
    item_code: demand.item_code || '',
    item_name: demand.item_name || '',
    card_code: demand.card_code || '',
    card_name: demand.card_name || '',
    quantity: demand.quantity || 0,
    start_date: demand.start_date ? demand.start_date.slice(0, 10) : '',
    end_date: demand.end_date ? demand.end_date.slice(0, 10) : '',
    reason: demand.reason || ''
  }
  displayDialog.value = true
  loadSapCatalogs()
}

const toggleDemand = async (id: number) => {
  try {
    await api.patch(`/api/special-demands/${id}/toggle`)
    toast.add({ severity: 'success', summary: 'Actualizado', detail: 'Estado de la demanda especial modificado.', life: 3000 })
    loadDemands()
  } catch (error) {
    console.error('Error toggling special demand:', error)
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo cambiar el estado.', life: 3000 })
  }
}

const deleteDemand = async (id: number) => {
  if (!confirm('¿Estás seguro de eliminar permanentemente esta demanda especial?')) return
  try {
    await api.delete(`/api/special-demands/${id}`)
    toast.add({ severity: 'success', summary: 'Eliminado', detail: 'Demanda especial eliminada.', life: 3000 })
    loadDemands()
  } catch (error) {
    console.error('Error deleting special demand:', error)
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo eliminar.', life: 3000 })
  }
}

const saveDemand = async () => {
  if (!newDemand.value.item_code || newDemand.value.quantity <= 0 || !newDemand.value.start_date || !newDemand.value.end_date) {
    alert('Por favor, completa los campos requeridos: SKU, cantidad mayor a 0 y fechas de vigencia.')
    return
  }
  
  try {
    const payload = {
      ...newDemand.value,
      card_code: newDemand.value.card_code.trim() || null,
      card_name: newDemand.value.card_name.trim() || null,
      item_name: newDemand.value.item_name.trim() || null,
      start_date: new Date(newDemand.value.start_date).toISOString(),
      end_date: new Date(newDemand.value.end_date).toISOString()
    }
    
    if (isEditing.value && currentEditingId.value) {
      await api.put(`/api/special-demands/${currentEditingId.value}`, payload)
      toast.add({ severity: 'success', summary: 'Modificada', detail: 'Demanda especial actualizada con éxito.', life: 3000 })
    } else {
      await api.post('/api/special-demands/', payload)
      toast.add({ severity: 'success', summary: 'Creada', detail: 'Incremento de demanda especial programado con éxito.', life: 3000 })
    }
    
    displayDialog.value = false
    loadDemands()
  } catch (error) {
    console.error('Error saving special demand:', error)
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo guardar la demanda especial.', life: 3000 })
  }
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString()
}

const getStatusSeverity = (data: any) => {
  if (!data.is_active) return 'danger'
  const now = new Date()
  const end = new Date(data.end_date)
  if (now > end) return 'warn'
  if (data.remaining_qty <= 0) return 'info'
  return 'success'
}

const getStatusLabel = (data: any) => {
  if (!data.is_active) return 'INACTIVO'
  const now = new Date()
  const end = new Date(data.end_date)
  if (now > end) return 'EXPIRADO'
  if (data.remaining_qty <= 0) return 'CONSUMIDO'
  return 'ACTIVO'
}

onMounted(() => {
  loadDemands()
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <Toast />
    
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-2xl font-bold text-gray-800 dark:text-slate-100 font-sans tracking-tight">Demandas Especiales</h2>
        <p class="text-gray-500 dark:text-slate-400">Registra y rastrea incrementos excepcionales de volumen (promociones, nuevos clientes, etc.)</p>
      </div>
      <Button 
        label="Registrar Demanda Especial" 
        icon="pi pi-plus-circle" 
        severity="primary" 
        @click="openCreateDialog"
      />
    </div>

    <!-- Alert Panel Info -->
    <div class="p-4 bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900/60 rounded-xl text-indigo-900 dark:text-indigo-200 text-sm flex gap-3 items-start shadow-sm transition-colors">
      <i class="pi pi-info-circle text-lg mt-0.5 text-indigo-500 dark:text-indigo-400"></i>
      <div>
        <h4 class="font-bold mb-1">¿Cómo funciona la prevención de duplicación?</h4>
        <p class="text-indigo-800 dark:text-indigo-300">
          Cuando programas una demanda especial de un producto, el sistema buscará automáticamente las facturas reales facturadas en SAP B1 a partir de la <b>Fecha de Inicio</b>. 
          El volumen vendido se descuenta del programado (Cantidad Consumida). Solo el saldo restante (Cantidad Restante) se suma al cálculo de producción sugerida del forecast para no duplicar volumen.
        </p>
      </div>
    </div>

    <div class="card bg-white dark:bg-slate-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700 transition-colors">
      <DataTable :value="demands" :loading="loading" stripedRows paginator :rows="10">
        <template #empty>No se han registrado demandas especiales.</template>
        <template #loading>Cargando datos. Por favor espera.</template>
        
        <Column header="SKU" sortable style="width: 12%">
          <template #body="{ data }">
            <span class="font-mono bg-gray-100 dark:bg-slate-700 text-gray-800 dark:text-slate-200 px-2 py-1 rounded text-xs">{{ data.item_code }}</span>
          </template>
        </Column>

        <Column field="item_name" header="Producto" sortable style="width: 20%">
          <template #body="{ data }">
            <span class="text-gray-800 dark:text-slate-200">{{ data.item_name || '—' }}</span>
          </template>
        </Column>

        <Column header="Cliente (CardCode / Nombre)" sortable style="width: 20%">
          <template #body="{ data }">
            <span v-if="data.card_code" class="text-gray-800 dark:text-slate-200">
              <b class="text-xs font-mono text-gray-600 dark:text-slate-400">[{{ data.card_code }}]</b> {{ data.card_name || 'Desconocido' }}
            </span>
            <span v-else class="text-indigo-600 dark:text-indigo-300 font-bold text-xs bg-indigo-50 dark:bg-indigo-950/60 px-2 py-1 rounded">GENERAL (Todos)</span>
          </template>
        </Column>

        <Column field="quantity" header="Prog." sortable style="width: 8%" class="text-right font-bold"></Column>
        
        <Column field="consumed_qty" header="Consumido (SAP)" sortable style="width: 10%" class="text-right text-green-600 dark:text-green-400 font-semibold"></Column>
        
        <Column field="remaining_qty" header="Restante" sortable style="width: 8%" class="text-right text-indigo-600 dark:text-indigo-400 font-bold"></Column>

        <Column header="Vigencia" style="width: 15%">
          <template #body="{ data }">
            <span class="text-xs text-gray-600 dark:text-slate-400">{{ formatDate(data.start_date) }} al {{ formatDate(data.end_date) }}</span>
          </template>
        </Column>

        <Column field="status" header="Estado" sortable style="width: 10%">
          <template #body="{ data }">
            <Tag 
              :value="getStatusLabel(data)" 
              :severity="getStatusSeverity(data)" 
              class="cursor-pointer"
              @click="toggleDemand(data.id)"
            />
          </template>
        </Column>

        <Column header="Acciones" style="width: 10%">
          <template #body="{ data }">
            <div class="flex gap-2">
              <Button 
                icon="pi pi-pencil" 
                outlined 
                rounded 
                severity="info" 
                title="Modificar demanda especial"
                @click="openEditDialog(data)"
              />
              <Button 
                icon="pi pi-trash" 
                outlined 
                rounded 
                severity="danger" 
                title="Eliminar demanda especial"
                @click="deleteDemand(data.id)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- Diálogo de Registro y Edición -->
    <Dialog 
      v-model:visible="displayDialog" 
      modal 
      :header="isEditing ? 'Modificar Demanda Especial' : 'Registrar Demanda Especial'" 
      :style="{ width: '560px' }"
    >
      <div class="flex flex-col gap-4 mt-2 text-sm">
        
        <!-- Búsqueda interactiva de Producto desde SAP con Autocompletado -->
        <div class="relative flex flex-col gap-2 p-3 bg-gray-50 dark:bg-slate-800/80 border border-gray-200 dark:border-slate-700 rounded-lg">
          <label class="font-bold text-gray-800 dark:text-slate-200 flex items-center gap-2">
            <i class="pi pi-search text-indigo-500 dark:text-indigo-400"></i> Buscar Producto en SAP B1
          </label>
          <div class="relative">
            <input 
              type="text" 
              v-model="productSearchQuery"
              @focus="showProductDropdown = true"
              placeholder="Escribe para buscar por código o nombre (ej. 2112, queso)..."
              class="w-full border border-gray-300 dark:border-slate-600 rounded-md p-2 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 focus:outline-indigo-500 text-sm"
            />
            <div 
              v-if="showProductDropdown" 
              class="absolute z-50 left-0 right-0 mt-1 max-h-56 overflow-y-auto bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-md shadow-xl text-sm"
            >
              <div 
                v-if="loadingSapData" 
                class="p-3 text-center text-gray-500 dark:text-slate-400"
              >
                <i class="pi pi-spin pi-spinner mr-2 text-indigo-500"></i> Cargando catálogo de SAP...
              </div>
              <div v-else-if="filteredProducts.length === 0" class="p-3 text-center text-gray-500 dark:text-slate-400">
                No se encontraron coincidencias de producto.
              </div>
              <div 
                v-else 
                v-for="p in filteredProducts" 
                :key="p.ItemCode" 
                @click="selectProduct(p)"
                class="p-2.5 hover:bg-indigo-50 dark:hover:bg-slate-700 cursor-pointer border-b border-gray-100 dark:border-slate-700/50 flex flex-col transition-colors"
              >
                <span class="font-bold text-indigo-700 dark:text-indigo-300 font-mono text-xs">{{ p.ItemCode }}</span>
                <span class="text-gray-800 dark:text-slate-200">{{ p.ItemName }}</span>
              </div>
            </div>
          </div>
          <p class="text-xs text-gray-500 dark:text-slate-400">Escribe cualquier fragmento del código o nombre para ver sugerencias en tiempo real.</p>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="flex flex-col gap-1">
            <label for="item_code" class="font-semibold text-gray-700 dark:text-slate-300">SKU / Producto *</label>
            <InputText id="item_code" v-model="newDemand.item_code" placeholder="Ej. 2112028" class="dark:bg-slate-900 dark:border-slate-700 dark:text-slate-100" />
          </div>
          <div class="flex flex-col gap-1">
            <label for="item_name" class="font-semibold text-gray-700 dark:text-slate-300">Nombre del Producto</label>
            <InputText id="item_name" v-model="newDemand.item_name" placeholder="Ej. QUESO MANCHEGO..." class="dark:bg-slate-900 dark:border-slate-700 dark:text-slate-100" />
          </div>
        </div>

        <!-- Búsqueda interactiva de Cliente desde SAP con Autocompletado -->
        <div class="relative flex flex-col gap-2 p-3 bg-gray-50 dark:bg-slate-800/80 border border-gray-200 dark:border-slate-700 rounded-lg mt-1">
          <label class="font-bold text-gray-800 dark:text-slate-200 flex items-center gap-2">
            <i class="pi pi-building text-indigo-500 dark:text-indigo-400"></i> Buscar Cliente en SAP B1 (Opcional)
          </label>
          <div class="relative">
            <input 
              type="text" 
              v-model="clientSearchQuery"
              @focus="showClientDropdown = true"
              placeholder="Escribe para buscar por código o cliente (ej. C056, walmart)..."
              class="w-full border border-gray-300 dark:border-slate-600 rounded-md p-2 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 focus:outline-indigo-500 text-sm"
            />
            <div 
              v-if="showClientDropdown" 
              class="absolute z-50 left-0 right-0 mt-1 max-h-56 overflow-y-auto bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-md shadow-xl text-sm"
            >
              <div 
                @click="selectClient(null)"
                class="p-2.5 hover:bg-indigo-50 dark:hover:bg-slate-700 cursor-pointer border-b border-gray-100 dark:border-slate-700/50 text-indigo-600 dark:text-indigo-400 font-semibold"
              >
                ✨ GENERAL (Todos los clientes / Sin cliente específico)
              </div>
              <div 
                v-if="loadingSapData" 
                class="p-3 text-center text-gray-500 dark:text-slate-400"
              >
                <i class="pi pi-spin pi-spinner mr-2 text-indigo-500"></i> Cargando catálogo de clientes...
              </div>
              <div v-else-if="filteredClients.length === 0" class="p-3 text-center text-gray-500 dark:text-slate-400">
                No se encontraron coincidencias de cliente.
              </div>
              <div 
                v-else 
                v-for="c in filteredClients" 
                :key="c.CardCode" 
                @click="selectClient(c)"
                class="p-2.5 hover:bg-indigo-50 dark:hover:bg-slate-700 cursor-pointer border-b border-gray-100 dark:border-slate-700/50 flex flex-col transition-colors"
              >
                <span class="font-bold text-indigo-700 dark:text-indigo-300 font-mono text-xs">{{ c.CardCode }}</span>
                <span class="text-gray-800 dark:text-slate-200">{{ c.CardName }}</span>
              </div>
            </div>
          </div>
          <p class="text-xs text-gray-500 dark:text-slate-400">Escribe cualquier parte del código o nombre de cliente para filtrar coincidencia.</p>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="flex flex-col gap-1">
            <label for="card_code" class="font-semibold text-gray-700 dark:text-slate-300">Código de Cliente</label>
            <InputText id="card_code" v-model="newDemand.card_code" placeholder="Ej. C056 (o dejar vacío)" class="dark:bg-slate-900 dark:border-slate-700 dark:text-slate-100" />
          </div>
          <div class="flex flex-col gap-1">
            <label for="card_name" class="font-semibold text-gray-700 dark:text-slate-300">Nombre del Cliente</label>
            <InputText id="card_name" v-model="newDemand.card_name" placeholder="Ej. HEB, WALMART" class="dark:bg-slate-900 dark:border-slate-700 dark:text-slate-100" />
          </div>
        </div>

        <div class="flex flex-col gap-1">
          <label for="qty" class="font-semibold text-gray-700 dark:text-slate-300">Cantidad Extra Programada (Volumen) *</label>
          <input 
            id="qty" 
            v-model.number="newDemand.quantity" 
            type="number"
            class="w-full border border-gray-300 dark:border-slate-600 rounded-md p-2 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 focus:outline-indigo-500" 
            placeholder="Ej. 1000"
          />
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="flex flex-col gap-1">
            <label for="start" class="font-semibold text-gray-700 dark:text-slate-300">Fecha de Inicio *</label>
            <input 
              id="start" 
              v-model="newDemand.start_date" 
              type="date"
              class="w-full border border-gray-300 dark:border-slate-600 rounded-md p-2 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 focus:outline-indigo-500"
            />
          </div>
          <div class="flex flex-col gap-1">
            <label for="end" class="font-semibold text-gray-700 dark:text-slate-300">Fecha de Fin *</label>
            <input 
              id="end" 
              v-model="newDemand.end_date" 
              type="date"
              class="w-full border border-gray-300 dark:border-slate-600 rounded-md p-2 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 focus:outline-indigo-500"
            />
          </div>
        </div>

        <div class="flex flex-col gap-1">
          <label for="reason" class="font-semibold text-gray-700 dark:text-slate-300">Descripción / Motivo / Notas</label>
          <textarea 
            id="reason" 
            v-model="newDemand.reason" 
            rows="3"
            class="w-full border border-gray-300 dark:border-slate-600 rounded-md p-2 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 focus:outline-indigo-500 text-sm"
            placeholder="Ej. Promoción Buen Fin, Apertura de nueva sucursal..."
          ></textarea>
        </div>
      </div>

      <template #footer>
        <Button label="Cancelar" icon="pi pi-times" text @click="displayDialog = false" />
        <Button :label="isEditing ? 'Guardar Cambios' : 'Guardar'" icon="pi pi-check" severity="primary" @click="saveDemand" />
      </template>
    </Dialog>
  </div>
</template>


