import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    // 三个测试文件串行执行。router.test.ts 会在用例内部动态 import 完整视图
    // 依赖树（element-plus / echarts / 页面组件），多文件并行转换时争抢 CPU，
    // 冷启动下 10 次基线复现 1 次失败；串行后消除该竞争。
    fileParallelism: false,
    // 首次编译整棵依赖树在冷缓存下可超过 20s，原值会把环境抖动误判为用例失败。
    testTimeout: 60000,
    hookTimeout: 60000,
  },
})
