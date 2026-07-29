import { sentryVitePlugin } from '@sentry/vite-plugin'
import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import pkg from './package.json'
import { pwaPlugin } from './pwa.config'

// https://vite.dev/config/Pfix
export default defineConfig(({ mode }) => {
  const DEFAULT_PORT = 5179
  const root = fileURLToPath(new URL('./', import.meta.url))
  const envVars = loadEnv(mode, root, 'VITE_')
  const isProduction = mode === 'production'
  const sentryEnabled = !!envVars.VITE_SENTRY_DSN && !!process.env.SENTRY_AUTH_TOKEN

  return {
    define: {
      __APP_VERSION__: JSON.stringify(pkg.version),
      __BUILD_DATE__: JSON.stringify(new Date().toISOString()),
    },
    plugins: [
      tailwindcss(),
      vue(),
      pwaPlugin,
      // Sentry plugin for source maps upload (only in production builds)
      ...(isProduction && sentryEnabled
        ? [
            sentryVitePlugin({
              org: process.env.SENTRY_ORG,
              project: process.env.SENTRY_PROJECT,
              authToken: process.env.SENTRY_AUTH_TOKEN,
              sourcemaps: {
                assets: './dist/**',
                ignore: ['./node_modules'],
                filesToDeleteAfterUpload: './dist/**/*.map',
              },
            }),
          ]
        : []),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      },
    },
    server: {
      port: envVars.VITE_PORT ? parseInt(envVars.VITE_PORT) : DEFAULT_PORT,
      proxy: {
        '/api': {
          target: envVars.VITE_API_PROXY_URL ?? 'http://localhost:8003',
          changeOrigin: true,
        },
      },
    },
    watch: {
      ignored: ['**/backend/**'],
    },
    build: {
      chunkSizeWarningLimit: 600,
      sourcemap: true, // Generate source maps to satisfy Lighthouse performance audit
      cssCodeSplit: true, // Split CSS into separate chunks for better caching
      rollupOptions: {
        // @vueuse/core@14.3.0 — misplaced /* #__PURE__ */ in dist (vueuse/vueuse#5387)
        onwarn(warning, warn) {
          if (warning.code === 'INVALID_ANNOTATION') return
          warn(warning)
        },
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return

            if (id.includes('lucide-vue-next')) return 'vendor-icons'
            if (id.includes('@unovis') || id.includes('elkjs') || id.includes('maplibre-gl') || id.includes('leaflet') || id.includes('/three/')) {
              return 'vendor-charts'
            }
            if (id.includes('vee-validate') || id.includes('@vee-validate') || id.includes('/zod/')) return 'vendor-forms'
            if (id.includes('markdown-it')) return 'vendor-markdown'
            if (id.includes('date-fns')) return 'vendor-dates'
            if (id.includes('qrcode')) return 'vendor-qrcode'
            if (id.includes('@simplewebauthn')) return 'vendor-webauthn'
            if (id.includes('@tanstack/vue-table')) return 'vendor-table'
            if (id.includes('@tanstack/vue-query')) return 'vendor-query'
            if (id.includes('@vueuse/')) return 'vendor-vueuse'
            if (id.includes('reka-ui')) return 'vendor-ui'
            if (id.includes('floating-vue')) return 'vendor-tooltips'
            if (id.includes('vue-sonner') || id.includes('/sonner/')) return 'vendor-notifications'
            if (id.includes('vue-i18n')) return 'vendor-i18n'
            if (id.includes('vue-router')) return 'vendor-router'
            if (id.includes('pinia')) return 'vendor-pinia'
            if (id.includes('/vue/') || id.includes('/@vue/')) return 'vendor-vue'

            return 'vendor'
          },
        },
      },
    },
  }
})
