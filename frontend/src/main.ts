import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createPinia } from 'pinia'
import { createApp } from 'vue'
import { VueQueryPlugin } from '@tanstack/vue-query'

import App from './App.vue'
import { queryClient } from './app/query-client'
import { router } from './app/router'
import 'element-plus/dist/index.css'
import './styles/tokens.scss'
import './styles/base.scss'

createApp(App)
  .use(createPinia())
  .use(router)
  .use(VueQueryPlugin, { queryClient })
  .use(ElementPlus, { locale: zhCn })
  .mount('#app')
