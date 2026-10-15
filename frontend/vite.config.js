import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Le porte si scelgono in backend/.env (GANTT_PORTA_BACKEND, GANTT_PORTA_FRONTEND),
// lo stesso file che leggono il backend e gli e2e. Dal file si caricano solo le
// variabili con prefisso GANTT_PORTA_: il resto (credenziali, chiavi) non entra
// nella configurazione del frontend. Una variabile già presente nell'ambiente
// vince sul file.
const BACKEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../backend')

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, BACKEND, 'GANTT_PORTA_')
  const portaFrontend = Number(env.GANTT_PORTA_FRONTEND || 3100)
  const portaBackend = Number(env.GANTT_PORTA_BACKEND || 8100)

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: portaFrontend,
      // Se la porta è occupata Vite si ferma invece di prenderne un'altra:
      // un frontend su una porta diversa da quella attesa manderebbe gli e2e
      // e il CORS a cercarlo nel posto sbagliato.
      strictPort: true,
      proxy: {
        '/api': `http://localhost:${portaBackend}`,
      },
    },
  }
})
