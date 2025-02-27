<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import axios from 'axios'

const data = ref([])
const sortBy = ref('id') // Critère de tri par défaut
const selectedTypes = ref(['entrant', 'sortant']) // Types de virements sélectionnés
const selectedMonth = ref('') // Mois sélectionné


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
  if (sortBy.value === 'id') {
    data.value.sort((a, b) => a.id.trim().localeCompare(b.id.trim()))
  } else if (sortBy.value === 'date') {
    data.value.sort((a, b) => new Date(a.date_prod) - new Date(b.date_prod))
  }
}

// Regarder les changements de sortBy et trier les données en conséquence
watch(sortBy, sortData)

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
</script>

<template>
  <header>
    <div class="total">
      <h2>Total: {{ total.toFixed(2) }}€</h2>
    </div>
  </header>
  <main class="list">
    <div>
      <label for="sort">Trier par :</label>
      <select id="sort" v-model="sortBy">
        <option value="id">ID</option>
        <option value="date">Date</option>
      </select>
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
    </div>
    <div v-if="filteredData.length">
      <h2>Data from Backend:</h2>
      <ul>
        <li class="obj" v-for="virement in filteredData" :key="virement.id">
          <div>
            <p>ID: {{ virement.id.trim() }}</p>
            <p>Type: {{ virement.type }}</p>
            <p>Date: {{ new Date(virement.date_prod).toLocaleDateString() }}</p>
            <p :class="virement.type === 'sortant' ? 'out' : 'in'">
              Montant: {{ virement.type === 'sortant' ? '-' : '' }}{{ virement.montant }}€
            </p>
            <div v-if="virement.description">
              <p>Description: {{ virement.description }}</p>
            </div>
            <div v-else>
              <p>Pas de description</p>
            </div>
          </div>
          <div class="actions">
            <input type="button" value="Modifier description" @click="modifydescription(virement.id)"/>
            <input type="button" value="Supprimer" @click="deleteVirement(virement.id)" />
          </div>
        </li>
      </ul>
    </div>
    <div v-else>
      <p>No data available</p>
    </div>
  </main>
</template>

<style scoped>
.total {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 1.5rem;
  font-weight: bold;
}
.in{
  color: green;
}
.out{
  color: red;
}
.list{
  top: 50px;
  left: 50px;
  position: absolute;
  width: 95%;
}
.obj {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid white;
  margin: 10px;
  padding: 10px;
}
.actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

</style>