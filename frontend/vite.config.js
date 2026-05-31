import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ command }) => ({
  plugins: [react()],
  // Defaults to '/' for custom domains or local dev, and '/WAR/' for the default github.io subfolder
  base: process.env.GITHUB_PAGES_CUSTOM_DOMAIN ? '/' : (command === 'serve' ? '/' : '/WAR/'),
}))
