import DefaultTheme from 'vitepress/theme'
import { onMounted, watch } from 'vue'
import { useData, useRoute } from 'vitepress'
import './custom.css'

export default {
  extends: DefaultTheme,
  setup() {
    const { isDark, lang } = useData()
    const route = useRoute()

    function syncNavbarControls() {
      if (typeof document === 'undefined') return
      const isZh = lang.value === 'zh-CN'
      // Ensure theme switch aria-checked and localized label match applied state
      const switches = document.querySelectorAll('.VPSwitchAppearance')
      switches.forEach((btn) => {
        btn.setAttribute('aria-checked', isDark.value ? 'true' : 'false')
        const title = isDark.value
          ? (isZh ? '切换到浅色主题' : 'Switch to light theme')
          : (isZh ? '切换到深色主题' : 'Switch to dark theme')
        btn.setAttribute('title', title)
        btn.setAttribute('aria-label', title)
      })

      // Preserve query string and hash anchor on language switcher links
      const suffix = (window.location.search || '') + (window.location.hash || '')
      const langLinks = document.querySelectorAll('.VPNavBarTranslations .VPMenuLink a, .VPNavScreenTranslations a')
      langLinks.forEach((a) => {
        const rawHref = a.getAttribute('data-base-href') || a.getAttribute('href') || ''
        if (!a.getAttribute('data-base-href') && rawHref) {
          a.setAttribute('data-base-href', rawHref.split('#')[0].split('?')[0])
        }
        const baseHref = a.getAttribute('data-base-href')
        if (baseHref) {
          a.setAttribute('href', suffix ? `${baseHref}${suffix}` : baseHref)
        }
      })
    }

    onMounted(() => {
      syncNavbarControls()
      window.addEventListener('hashchange', syncNavbarControls)
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          const openBtn = document.querySelector('.VPNavBarTranslations button[aria-expanded="true"]')
          if (openBtn) {
            openBtn.setAttribute('aria-expanded', 'false')
            openBtn.focus()
          }
        }
      })
    })

    watch([isDark, lang, () => route.path], () => {
      setTimeout(syncNavbarControls, 30)
    })
  },
}
