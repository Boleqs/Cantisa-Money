<template>
  <div class="div_form">
    <form @submit.prevent="createAccount">
      <br>
      <label for="username">Login : </label>
      <input type="text" v-model="username" name="username"/>
      <br>
      <label for="email">Email : </label>
      <input type="text" v-model="email" name="email"/>
      <br>
      <label for="password">Password : </label>
      <input type="password" v-model="password" name="password" minlength="4"/>
      <br><br>
      <button id="submit_button">
        <span v-if="!loading">Créer le compte</span>
        <span v-else>Création...</span>
      </button>
    </form>
  </div>
</template>

<script setup>
  import { ref } from 'vue'
  import axios from 'axios'
  import { useRouter } from 'vue-router'
  import TopRightDisplay from "@/components/TopRightDisplay.vue";

  const username = ref('')
  const email = ref('')
  const password = ref('')
  const loading = ref(false)
  const error = ref('')
  const created = ref('')
  const router = useRouter()
  const emit = defineEmits(['msg-event'])

  const API_BASE = 'http://localhost:5000/api/user'

  async function createAccount () {
    try {
      const { data } = await axios.post(`${API_BASE}`, {
        username: username.value,
        email: email.value,
        password: password.value,
        role_id: '00000000-cafe-46fe-9a04-a03b4c253f1f'
      })
      emit('msg-event', { type: 'info', content: `The account ${username} has been created!`})
    } catch (e) {
      try {
        // if missing value error
        error.value = e.response.data.response_data || 'Server error.'
      }
      catch (e) {
        // if other error, typically network error
        error.value = e
      }
    } finally {
      loading.value = false
    }
  }
</script>

<style scoped>

</style>