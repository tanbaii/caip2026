import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

const backendTarget = 'http://127.0.0.1:8000'

function apiProxy(path) {
  return {
    target: backendTarget,
    changeOrigin: true,
    bypass(req) {
      if (req.method === 'GET' && req.headers.accept?.includes('text/html')) {
        return '/index.html'
      }
      return null
    },
    rewrite: () => path,
  }
}

function prefixProxy() {
  return {
    target: backendTarget,
    changeOrigin: true,
  }
}

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      '/health': prefixProxy(),
      '/auth': prefixProxy(),
      '/chat': apiProxy('/chat'),
      '/ai': prefixProxy(),
      '/report': apiProxy('/report'),
      '/scenarios': prefixProxy(),
      '/users': prefixProxy(),
      '/leaderboard': apiProxy('/leaderboard'),
      '/knowledge': prefixProxy(),
    },
  },
})
