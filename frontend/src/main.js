import { createApp } from 'vue'
import { createPinia } from 'pinia'
import naive from 'naive-ui'
import App from './App.vue'
import { api } from './api.js'
import { createAppRouter } from './router.js'
import './style.css'

// 首次带令牌打开（推荐 /#token=…：片段不会发到服务器、不进访问日志；兼容 /?token=…）：
// 换成会话 Cookie 并从地址栏抹掉令牌，再挂载应用
async function exchangeUrlToken() {
  const url = new URL(location.href)
  const hash = new URLSearchParams(url.hash.slice(1))
  const token = url.searchParams.get('token') || hash.get('token')
  if (!token) return
  url.searchParams.delete('token')
  hash.delete('token')
  url.hash = hash.toString()
  history.replaceState(null, '', url)
  try {
    await api.createSession(token)
  } catch { /* 令牌无效：界面会弹出令牌输入 */ }
}

exchangeUrlToken().finally(() => {
  const app = createApp(App)
  app.use(createPinia())
  app.use(createAppRouter())
  app.use(naive)
  app.mount('#app')
})
