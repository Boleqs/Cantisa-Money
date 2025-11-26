  <template>
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
    const emit = defineEmits(['msg-event'])

    const email = ref('')
    const password = ref('')
    const loading = ref(false)
    const msg_content = ref('')
    const router = useRouter()
    const msg_type = ref()


    const API_BASE = 'http://localhost:5000/api/auth'

    async function login () {
      loading.value = true
      try {
        const { data } = await axios.post(`${API_BASE}/login`, {
          login: email.value,
          password: password.value
        })
        router.push('/')     // redirect after success
        msg_type.value = 'info'
        msg_content.value = data
      } catch (e) {
        try {
          // if error sent by flask API
          msg_content.value = e.response.data.response_data || 'Server error.'
          msg_type.value = 'error'
        }
        catch (e) {
          // if other error, typically network error
          msg_content.value = e
          msg_type.value = 'error'
        }
      } finally {
        loading.value = false
        emit('msg-event', { type: msg_type.value, content: msg_content.value })
      }
    }
  </script>

  <style>
  .div_form {
    align-items: center;
  }
  </style>