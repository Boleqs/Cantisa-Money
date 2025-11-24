  <template>
    <div v-show=error>
      <TopRightDisplay p-type="error">{{error}}</TopRightDisplay>
    </div>
    <div class="div_form">
      <form @submit.prevent="login">
        <br>
        <label for="login">Login : </label>
        <input type="text" v-model="email" name="login"/>
        <br>
        <label for="password">Password : </label>
        <input type="password" v-model="password" name="password" minlength="4"/>
        <br><br>
        <button id="submit_button">
          <span v-if="!loading">Se connecter</span>
          <span v-else>Connexion...</span>
        </button>
      </form>
    </div>
  </template>

  <script setup>
    import { ref } from 'vue'
    import axios from 'axios'
    import { useRouter } from 'vue-router'
    import TopRightDisplay from "@/components/TopRightDisplay.vue";

    const email = ref('')
    const password = ref('')
    const loading = ref(false)
    const error = ref('')
    const router = useRouter()

    const API_BASE = 'http://localhost:5000/api/auth'

    async function login () {
      error.value = ''
      loading.value = true
      try {
        const { data } = await axios.post(`${API_BASE}/login`, {
          login: email.value,
          password: password.value
        })
        router.push('/')     // redirect after success
      } catch (e) {
        try {
          // if login error
          error.value = e.response.data.response_data || 'Server error.'}
        catch {
          // if other error, typically network error
          error.value = e
        }
      } finally {
        loading.value = false
      }
    }
  </script>

  <style>
  .div_form {
    align-items: center;
  }
  </style>