import { URL, fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import { tanstackStart } from '@tanstack/react-start/plugin/vite'
import viteReact from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { nitro } from 'nitro/vite'

const config = defineConfig({
  optimizeDeps: {
    exclude: ['bun', 'bun:sqlite'],
  },
  resolve: {
    tsconfigPaths: true,
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  plugins: [
    tailwindcss(),
    tanstackStart(),
    viteReact(),
    nitro(),
  ],
  environments: {
    ssr: { build: { rollupOptions: { input: './src/server.ts' } } },
  },
})

export default config
