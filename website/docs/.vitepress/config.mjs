import { defineConfig } from 'vitepress'

const SITE_ORIGIN = 'https://cyber-tao.github.io'
const BASE_PATH = '/VidHarbor/'
const SITE_URL = `${SITE_ORIGIN}${BASE_PATH}`

const SAFE_STORAGE_SCRIPT = `
(function(){
  try {
    var s = window.localStorage;
    s.getItem('__vh_test__');
  } catch (e) {
    var mem = {};
    var fake = {
      getItem: function(k){ return Object.prototype.hasOwnProperty.call(mem, k) ? mem[k] : null; },
      setItem: function(k, v){ mem[k] = String(v); },
      removeItem: function(k){ delete mem[k]; },
      clear: function(){ mem = {}; }
    };
    try { Object.defineProperty(window, 'localStorage', { value: fake, configurable: true }); } catch (_) {}
  }
})();
`

export default defineConfig({
  title: 'VidHarbor',
  description: 'Self-hosted multi-platform video library with hardware-first H.265/H.264 MP4 normalization, trending charts, scheduled intake, and SQLite indexing.',
  base: BASE_PATH,
  outDir: '../dist',
  appearance: 'dark',
  lastUpdated: false,
  sitemap: {
    hostname: SITE_URL,
  },
  head: [
    ['script', {}, SAFE_STORAGE_SCRIPT],
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${BASE_PATH}logo.svg` }],
    ['meta', { name: 'theme-color', content: '#6366f1' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:site_name', content: 'VidHarbor' }],
  ],
  transformHead({ pageData }) {
    const rel = pageData.relativePath
      .replace(/index\.md$/, '')
      .replace(/\.md$/, '.html')
    const isZh = rel.startsWith('zh/')
    const enPath = isZh ? rel.slice(3) : rel
    const zhPath = `zh/${enPath}`
    const canonicalUrl = `${SITE_URL}${rel}`
    const enUrl = `${SITE_URL}${enPath}`
    const zhUrl = `${SITE_URL}${zhPath}`
    return [
      ['link', { rel: 'canonical', href: canonicalUrl }],
      ['link', { rel: 'alternate', hreflang: 'en', href: enUrl }],
      ['link', { rel: 'alternate', hreflang: 'zh-CN', href: zhUrl }],
      ['link', { rel: 'alternate', hreflang: 'x-default', href: enUrl }],
    ]
  },
  themeConfig: {
    logo: '/logo.svg',
    socialLinks: [
      { icon: 'github', link: 'https://github.com/cyber-tao/VidHarbor', ariaLabel: 'GitHub Repository' },
    ],
    search: {
      provider: 'local',
      options: {
        locales: {
          zh: {
            translations: {
              button: {
                buttonText: '搜索文档',
                buttonAriaLabel: '搜索文档',
              },
              modal: {
                noResultsText: '未找到相关结果',
                resetButtonTitle: '清除查询条件',
                footer: {
                  selectText: '选择',
                  navigateText: '切换',
                  closeText: '关闭',
                },
              },
            },
          },
        },
      },
    },
  },
  locales: {
    root: {
      label: 'English',
      lang: 'en-US',
      title: 'VidHarbor',
      description: 'Self-hosted multi-platform video library with hardware-first MP4 normalization, trending charts, scheduled jobs, and SQLite indexing.',
      themeConfig: {
        nav: [
          { text: 'Quickstart', link: '/guide/quickstart' },
          { text: 'Guides', link: '/guide/deployment' },
          { text: 'Reference', link: '/reference/configuration' },
          { text: 'Evidence', link: '/reference/evidence' },
        ],
        sidebar: [
          {
            text: 'Getting Started',
            items: [
              { text: 'Quickstart', link: '/guide/quickstart' },
              { text: 'Docker, GPU & Evil0ctal', link: '/guide/deployment' },
            ],
          },
          {
            text: 'Task Guides',
            items: [
              { text: 'Cookies & Login Management', link: '/guide/cookies-and-auth' },
              { text: 'Charts, Schedules & Batch', link: '/guide/charts-and-schedules' },
            ],
          },
          {
            text: 'Reference & Architecture',
            items: [
              { text: 'Configuration Reference', link: '/reference/configuration' },
              { text: 'REST & SSE API Reference', link: '/reference/api' },
              { text: 'Architecture & Pipeline', link: '/reference/architecture' },
              { text: 'Verification & Evidence', link: '/reference/evidence' },
            ],
          },
        ],
        outline: {
          label: 'On this page',
          level: [2, 3],
        },
        docFooter: {
          prev: 'Previous page',
          next: 'Next page',
        },
        darkModeSwitchLabel: 'Appearance',
        lightModeSwitchTitle: 'Switch to light theme',
        darkModeSwitchTitle: 'Switch to dark theme',
        sidebarMenuLabel: 'Menu',
        returnToTopLabel: 'Return to top',
        langMenuLabel: 'Change language',
        footer: {
          message: 'VidHarbor v0.3.0 · Self-Hosted Multi-Platform Video Library',
          copyright: 'Source available on GitHub (cyber-tao/VidHarbor)',
        },
      },
    },
    zh: {
      label: '简体中文',
      lang: 'zh-CN',
      link: '/zh/',
      title: 'VidHarbor · 影坞',
      description: '自托管多平台本地视频库：支持 YouTube / B站 / TikTok / 抖音下载、硬件优先 MP4 统一封装、热门榜单、定时任务与 SQLite 索引。',
      themeConfig: {
        nav: [
          { text: '快速开始', link: '/zh/guide/quickstart' },
          { text: '操作指南', link: '/zh/guide/deployment' },
          { text: '配置与 API', link: '/zh/reference/configuration' },
          { text: '实测证据', link: '/zh/reference/evidence' },
        ],
        sidebar: [
          {
            text: '入门与部署',
            items: [
              { text: '快速开始', link: '/zh/guide/quickstart' },
              { text: 'Docker、GPU 与兜底部署', link: '/zh/guide/deployment' },
            ],
          },
          {
            text: '核心工作流',
            items: [
              { text: '登录管理与 Cookies', link: '/zh/guide/cookies-and-auth' },
              { text: '热门榜单、定时与批量下载', link: '/zh/guide/charts-and-schedules' },
            ],
          },
          {
            text: '参考与架构',
            items: [
              { text: '配置项完整参考', link: '/zh/reference/configuration' },
              { text: 'REST 与 SSE 接口参考', link: '/zh/reference/api' },
              { text: '系统架构与媒体管线', link: '/zh/reference/architecture' },
              { text: '实测验证与证据清单', link: '/zh/reference/evidence' },
            ],
          },
        ],
        outline: {
          label: '本页目录',
          level: [2, 3],
        },
        docFooter: {
          prev: '上一页',
          next: '下一页',
        },
        darkModeSwitchLabel: '外观主题',
        lightModeSwitchTitle: '切换到浅色主题',
        darkModeSwitchTitle: '切换到深色主题',
        sidebarMenuLabel: '菜单',
        returnToTopLabel: '返回顶部',
        langMenuLabel: '切换语言',
        footer: {
          message: 'VidHarbor (影坞) v0.3.0 · 自托管多平台本地视频库',
          copyright: '源码托管于 GitHub (cyber-tao/VidHarbor)',
        },
      },
    },
  },
})
