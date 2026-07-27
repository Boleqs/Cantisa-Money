import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // loadEnv (import.meta.env n'existe pas ici, ce fichier tourne côté Node) : nécessaire pour lire
  // FRONTEND_PORT depuis le .env racine en local — en Docker il arrive déjà via process.env, voir
  // docker-compose.yml.
  const env = loadEnv(mode, process.cwd(), '')

  // API_HTTPS (voir .env.example) : équivalent local (npm run dev) au nginx du build de prod —
  // même certificat que le backend (backend/utils/tls.py le génère à son démarrage). S'il n'existe
  // pas encore (backend jamais lancé), on retombe sur du HTTP plutôt que de planter.
  let httpsConfig = undefined
  if ((env.API_HTTPS || '').toLowerCase() === 'true') {
    const certPath = env.TLS_CERT_PATH || fileURLToPath(new URL('./backend/certs/selfsigned.crt', import.meta.url))
    const keyPath = env.TLS_KEY_PATH || fileURLToPath(new URL('./backend/certs/selfsigned.key', import.meta.url))
    if (fs.existsSync(certPath) && fs.existsSync(keyPath)) {
      httpsConfig = { cert: fs.readFileSync(certPath), key: fs.readFileSync(keyPath) }
    } else {
      console.warn(`[vite] API_HTTPS=true mais certificat introuvable (${certPath}) — démarrez d'abord le backend une fois (il le génère), puis relancez "npm run dev". Servi en HTTP pour cette fois.`)
    }
  }

  return {
    plugins: [
      vue(),
      vueDevTools(),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      },
    },
    server: {
      // Nécessaire pour être joignable depuis l'extérieur du conteneur Docker (le défaut Vite,
      // localhost, ne serait accessible que depuis l'intérieur du conteneur).
      host: '0.0.0.0',
      port: Number(env.FRONTEND_PORT) || 5173,
      https: httpsConfig,
    },
    // Par défaut Vite n'expose au bundle client que les variables préfixées VITE_. On ajoute API_
    // pour réutiliser telles quelles (sans duplication ni renommage) les variables API_HOST/
    // API_PORT/API_HTTPS déjà utilisées côté backend (voir .env.example et src/router/index.js).
    // Aucun secret ne porte ce préfixe dans ce projet.
    envPrefix: ['VITE_', 'API_'],
  }
})
