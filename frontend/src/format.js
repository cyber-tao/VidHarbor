export function fmtCount(n) {
  n = Number(n) || 0
  if (n >= 1e8) return (n / 1e8).toFixed(1).replace(/\.0$/, '') + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(1).replace(/\.0$/, '') + '万'
  return String(n)
}

export function fmtDuration(sec) {
  sec = Math.round(Number(sec) || 0)
  if (!sec) return '--:--'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function fmtSize(bytes) {
  bytes = Number(bytes) || 0
  if (bytes >= 1 << 30) return (bytes / (1 << 30)).toFixed(2) + ' GB'
  if (bytes >= 1 << 20) return (bytes / (1 << 20)).toFixed(1) + ' MB'
  if (bytes >= 1 << 10) return (bytes / (1 << 10)).toFixed(0) + ' KB'
  return bytes + ' B'
}

export function fmtDate(yyyymmdd) {
  if (!yyyymmdd || yyyymmdd.length !== 8) return yyyymmdd || '—'
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}`
}

export function fmtTime(ts) {
  const d = new Date(Number(ts) * 1000)
  return d.toLocaleTimeString('zh-CN', { hour12: false })
}

export function fmtDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', { hour12: false })
}

export const PLATFORMS = {
  youtube: { label: 'YouTube', color: '#f87171' },
  bilibili: { label: '哔哩哔哩', color: '#60a5fa' },
  tiktok: { label: 'TikTok', color: '#f0abfc' },
  douyin: { label: '抖音', color: '#a3e635' },
  other: { label: '其他', color: '#a1a1aa' },
}

export function platformLabel(p) {
  return PLATFORMS[p]?.label ?? p
}

export function platformColor(p) {
  return PLATFORMS[p]?.color ?? '#a1a1aa'
}
