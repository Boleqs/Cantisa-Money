<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import axios from 'axios'
import Modal from './components/Modal.vue'

const data = ref([])
const sortBy = ref('id') // Critère de tri par défaut
const sortOrder = ref('asc') // Ordre de tri par défaut
const selectedTypes = ref(['entrant', 'sortant']) // Types de virements sélectionnés
const selectedMonth = ref('') // Mois sélectionné
const showModal = ref(false)
const currentVirement = ref(null)
const modalTitle = ref('')
const modalAction = ref('modify')

onMounted(async () => {
  try {
    const response = await axios.get('http://localhost:5000/api/virements')
    console.log('Fetched data:', response.data) // Log the fetched data
    data.value = response.data
    sortData() // Trier les données initialement
  } catch (error) {
    console.error('Error fetching data:', error)
  }
})

// Fonction pour trier les données
const sortData = () => {
  data.value.sort((a, b) => {
    let result = 0
    if (sortBy.value === 'date_prod') {
      result = new Date(a[sortBy.value]) - new Date(b[sortBy.value])
    } else if (sortBy.value === 'montant') {
      result = parseFloat(a[sortBy.value]) - parseFloat(b[sortBy.value])
    } else if (sortBy.value === 'description') {
        if (a[sortBy.value] === null) {
            result = 1
        } else if (b[sortBy.value] === null) {
            result = -1
        } else {
            result = a[sortBy.value].toString().localeCompare(b[sortBy.value].toString())
        }
      
    }
      else {
      result = a[sortBy.value].toString().localeCompare(b[sortBy.value].toString())
    }
    return sortOrder.value === 'asc' ? result : -result
  })
}

// Fonction pour changer le critère de tri
const sortByColumn = (column) => {
  if (sortBy.value === column) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = column
    sortOrder.value = 'asc'
  }
  sortData()
}

// Regarder les changements de sortBy et trier les données en conséquence
watch(sortBy, sortData)
watch(sortOrder, sortData)

// Filtrer les données en fonction des types sélectionnés et du mois sélectionné
const filteredData = computed(() => {
  return data.value.filter(virement => {
    const virementDate = new Date(virement.date_prod)
    if (selectedMonth.value) {
      const selectedDate = new Date(selectedMonth.value)
      const isSameMonth = virementDate.getMonth() === selectedDate.getMonth()
      const isSameYear = virementDate.getFullYear() === selectedDate.getFullYear()
      return selectedTypes.value.includes(virement.type) && isSameMonth && isSameYear
    } else {
      return selectedTypes.value.includes(virement.type)
    }
  })
})

// Calculer le total des montants de toutes les données
const total = computed(() => {
  return data.value.reduce((acc, virement) => {
    return acc + (virement.type === 'sortant' ? -virement.montant : virement.montant)
  }, 0)
})

const deleteVirement = async (id) => {
  try {
    const response = await axios.delete(`http://localhost:5000/api/virements/${id}`)
    alert(response.data.message) // Afficher l'alerte avec le message de l'API
    data.value = data.value.filter(virement => virement.id !== id)
  } catch (error) {
    console.error('Error deleting virement:', error)
    alert('Error deleting virement') // Afficher une alerte en cas d'erreur
  }
}

const openModal = (virement, action) => {
  currentVirement.value = { ...virement }
  modalTitle.value = action === 'modify' ? 'Modifier Virement' : 'Ajouter Virement'
  modalAction.value = action
  showModal.value = true
}

const modifyVirement = async () => {
  try {
    const response = await axios.put(`http://localhost:5000/api/virements/${currentVirement.value.id}`, currentVirement.value)
//    alert(response.data.message) // Afficher l'alerte avec le message de l'API
    const virement = data.value.find(virement => virement.id === currentVirement.value.id)
    if (virement) {
      Object.assign(virement, currentVirement.value)
    }
    showModal.value = false
  } catch (error) {
    console.error('Error updating virement:', error)
    alert('Error updating virement') // Afficher une alerte en cas d'erreur
  }
}

const addVirement = async () => {
  try {
    const response = await axios.post(`http://localhost:5000/api/virements`, currentVirement.value)
//    alert(response.data.message) // Afficher l'alerte avec le message de l'API
    data.value.push(response.data)
    showModal.value = false
  } catch (error) {
    console.error('Error adding virement:', error)
    alert('Error adding virement') // Afficher une alerte en cas d'erreur
  }
}
</script>

<template>
  <header class="navbar">
    <div class="total">
      <h2>Total: {{ total.toFixed(2) }}€</h2>
    </div>
  </header>
  <main class="list">
    <div>
      <br />
      <label for="sort_by_date">Voir virement :</label>
      <input type="month" id="sort_by_date" v-model="selectedMonth" />
    </div>
    <div>
      <label>
        <input type="checkbox" value="entrant" v-model="selectedTypes" />
        Entrant
      </label>
      <label>
        <input type="checkbox" value="sortant" v-model="selectedTypes" />
        Sortant
      </label>
      <label>
        <input type="button" value="Ajouter un virement" @click="openModal({ id: '', type: 'entrant', date_prod: '', montant: 0, description: '' }, 'add')" />
      </label>
    </div>
    <div v-if="filteredData.length">
      <h2>Data from Backend:</h2>
      <table>
        <thead>
          <tr>
            <th @click="sortByColumn('id')" :class="sortBy.value === 'id' ? (sortOrder.value === 'asc' ? 'sorted-blue' : 'sorted-green') : ''">
              ID
            </th>
            <th @click="sortByColumn('type')" :class="sortBy.value === 'type' ? (sortOrder.value === 'asc' ? 'sorted-asc' : 'sorted-desc') : ''">
              Type
            </th>
            <th @click="sortByColumn('date_prod')" :class="sortBy.value === 'date_prod' ? (sortOrder.value === 'asc' ? 'sorted-asc' : 'sorted-desc') : ''">
              Date
            </th>
            <th @click="sortByColumn('montant')" :class="sortBy.value === 'montant' ? (sortOrder.value === 'asc' ? 'sorted-asc' : 'sorted-desc') : ''">
              Montant
            </th>
            <th @click="sortByColumn('description')" :class="sortBy.value === 'description' ? (sortOrder.value === 'asc' ? 'sorted-asc' : 'sorted-desc') : ''">
              Description
            </th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="virement in filteredData" :key="virement.id">
            <td>{{ virement.id.trim() }}</td>
            <td>{{ virement.type }}</td>
            <td>{{ new Date(virement.date_prod).toLocaleDateString() }}</td>
            <td :class="virement.type === 'sortant' ? 'out' : 'in'">
              {{ virement.type === 'sortant' ? '-' : '' }}{{ virement.montant }}€
            </td>
            <td>{{ virement.description || 'Pas de description' }}</td>
            <td class="actions">
              <input type="button" value="Modifier" @click="openModal(virement, 'modify')" />
              <input type="button" value="Supprimer" @click="deleteVirement(virement.id)" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else>
      <p>No data available</p>
    </div>
  </main>

  <Modal v-if="showModal" :title="modalTitle" @close="showModal = false" :modifyVirement="modifyVirement" :addVirement="addVirement" :action="modalAction">
    <div class="modal-grid">
      <div>
        <label>ID:</label>
        <span>{{ currentVirement.id }}</span>
      </div>
      <div>
        <label>Type:</label>
        <select id="type" v-model="currentVirement.type">
        <option value="entrant">Entrant</option>
        <option value="sortant">Sortant</option>
      </select>
      </div>
      <div>
        <label>Date:</label>
        <input type="date" v-model="currentVirement.date_prod" />
      </div>
      <div>
        <label>Montant:</label>
        <input type="number" v-model="currentVirement.montant" />
      </div>
      <div>
        <label>Description:</label>
        <input v-model="currentVirement.description" />
      </div>
    </div>
  </Modal>
</template>

<style scoped>
table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid white;
}
th, td {
  border: 1px solid #ddd;
  padding: 8px;
  text-align: left;
}
th {
  background-color: #323232;
  color: white;
}
th:not(:last-child):hover {
  cursor: pointer;
  background-color: white;
  color: #323232;
}
.total {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 1.5rem;
  font-weight: bold;
}
.arrow {
  width: 20px;
  height: 20px;
  position: absolute;
  right: 10px;
}
.in {
  color: green;
}
.out {
  color: red;
}
.list {
  top: 50px;
  left: 50px;
  position: absolute;
  width: 95%;
}
.actions {
  display: flex;
  justify-content: space-between;
  gap: 60px;
  width: 100%;
}
.actions input[type="button"] {
  flex: 1;
}
.modal-grid {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 10px;
}
.modal-grid div {
  display: contents;
}
.modal-grid label {
  grid-column: 1;
  justify-self: end;
  margin-right: 10px;
}
.modal-grid input, .modal-grid span {
  grid-column: 2;
  width: 100%;
}
</style>