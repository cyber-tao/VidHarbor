import { createApp } from 'vue'

import { setToken } from './api.js'

// 首次带 ?token= 访问：记住令牌并从地址栏清除（服务端启用 VIDHARBOR_TOKEN 时使用）
{
  const q = new URLSearchParams(location.search)
  const t = q.get('token')
  if (t) {
    setToken(t)
    q.delete('token')
    const rest = q.toString()
    history.replaceState(null, '', location.pathname + (rest ? `?${rest}` : '') + location.hash)
  }
}
import { createPinia } from 'pinia'
import naive from 'naive-ui'
import App from './App.vue'
import router from './router.js'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(naive)
app.mount('#app')
