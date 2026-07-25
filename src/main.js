import './assets/main.css'

import { createApp } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import App from './App.vue'
import router from './router/'
import { loadAccentColor } from './utils/theme.js'

// Avant le mount, pour éviter un flash de la couleur d'accent par défaut si l'utilisateur en a
// choisi une autre (voir Parametres.vue > Interface).
loadAccentColor()

createApp(App)
    .component('font-awesome-icon', FontAwesomeIcon)
    .use(router)
    .mount('#app')
