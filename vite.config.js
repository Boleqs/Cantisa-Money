import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
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
  },
})
