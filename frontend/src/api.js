async function req(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  get: (path) => req(path),
  post: (path, data) => req(path, { method: 'POST', body: JSON.stringify(data ?? {}) }),
  del: (path) => req(path, { method: 'DELETE' }),

  // tasks
  createTasks: (urls) => api.post('/api/tasks', { urls }),
  listTasks: () => api.get('/api/tasks'),
  cancelTask: (id) => api.del(`/api/tasks/${id}`),
  retryTask: (id) => api.post(`/api/tasks/${id}/retry`),

  // charts
  getCharts: (platform, category, refresh = false) =>
    api.get(`/api/charts/${platform}?category=${encodeURIComponent(category)}${refresh ? '&refresh=true' : ''}`),

  // stats & videos
  stats: () => api.get('/api/stats'),
  videos: (params) => api.get('/api/videos?' + new URLSearchParams(params).toString()),
  video: (id) => api.get(`/api/videos/${id}`),
  deleteVideo: (id) => api.del(`/api/videos/${id}?delete_files=true`),
}
