import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: process.env.GITHUB_ACTIONS
    ? '/bird-observation-explorer/'
    : '/',

  plugins: [
    vue(),
    tailwindcss(),
  ],
})