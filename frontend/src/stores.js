import { defineStore } from 'pinia'

import { authUrl } from './api.js'

/** SSE 实时事件：任务进度 / 日志 / 统计刷新信号 */
export const useEvents = defineStore('events', {
  state: () => ({
    connected: false,
    tasks: {},            // id -> task snapshot
    logs: [],             // {level,name,message,ts}
    logPaused: false,
    logExpanded: false,
    statsVersion: 0,      // 收到 stats_dirty 时自增，视图 watch 触发刷新
  }),
  getters: {
    taskList: (s) => Object.values(s.tasks).sort((a, b) => b.id - a.id),
    lastLog: (s) => (s.logs.length ? s.logs[s.logs.length - 1] : null),
    activeCount: (s) => Object.values(s.tasks).filter(
      (t) => t.status === 'pending' || t.status === 'running',
    ).length,
  },
  actions: {
    connect() {
      if (this._es) return
      const es = new EventSource(authUrl('/api/events'))
      this._es = es
      es.addEventListener('hello', () => { this.connected = true })
      es.onerror = () => { this.connected = false }
      es.addEventListener('task', (e) => {
        const t = JSON.parse(e.data)
        this.tasks[t.id] ? Object.assign(this.tasks[t.id], t) : (this.tasks[t.id] = t)
      })
      es.addEventListener('tasks', (e) => {
        const list = JSON.parse(e.data)
        this.tasks = {}
        for (const t of list) this.tasks[t.id] = t
      })
      es.addEventListener('log', (e) => {
        if (this.logs.length > 800) this.logs.splice(0, this.logs.length - 800)
        this.logs.push(JSON.parse(e.data))
      })
      es.addEventListener('stats_dirty', () => { this.statsVersion++ })
    },
    async loadTasks() {
      try {
        const res = await fetch('/api/tasks').then((r) => r.json())
        this.tasks = {}
        for (const t of res.tasks) this.tasks[t.id] = t
      } catch { /* SSE 会兜底 */ }
    },
    removeLocalTask(id) { delete this.tasks[id] },
  },
})
