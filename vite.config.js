import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // loadEnv (import.meta.env n'existe pas ici, ce fichier tourne côté Node) : nécessaire pour lire
  // FRONTEND_PORT depuis le .env racine en local — en Docker il arrive déjà via process.env, voir
  // docker-compose.yml.
  const env = loadEnv(mode, process.cwd(), '')

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
    },
    // Par défaut Vite n'expose au bundle client que les variables préfixées VITE_. On ajoute API_
    // pour réutiliser telles quelles (sans duplication ni renommage) les variables API_HOST/
    // API_PORT/API_HTTPS déjà utilisées côté backend (voir .env.example et src/router/index.js).
    // Aucun secret ne porte ce préfixe dans ce projet.
    envPrefix: ['VITE_', 'API_'],
  }
})
