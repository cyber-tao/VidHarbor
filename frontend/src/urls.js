// 从任意粘贴文本提取 http(s) 链接：App 分享文案是「乱码 + 链接」混合体，
// 整行不可直接当 URL 用；后端 create_tasks 也会再做一次同样的清洗。
const URL_RE = /https?:\/\/[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+/g

export function extractUrls(text) {
  const found = [...text.matchAll(URL_RE)]
    .map((m) => m[0].replace(/[.,;:!?)\]}>'"`|]+$/, ''))
  return [...new Set(found)]
}
