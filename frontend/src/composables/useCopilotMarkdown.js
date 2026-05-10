import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

// ── Markdown 渲染器配置 ──────────────────────────────────────
// P1-7 Fix: html:false 防止 XSS（LLM 输出中的恶意 HTML 通过 v-html 直接渲染）
const mdParser = new MarkdownIt({
  html: false,      // 禁止原始 HTML 标签，保证 v-html 渲染安全
  linkify: true,
  typographer: true,
  breaks: true,     // 换行符 → <br>
})

/** 解析 Markdown + 折叠 thinking 思考链（DeepSeek R1 推理内容） */
export function renderMarkdown(raw) {
  if (!raw) return ''
  // 提取 thinking 块（DeepSeek R1 推理过程）
  const thinkRegex = /<think>([\s\S]*?)<\/think>/g
  const parts = []
  let lastIdx = 0
  let match

  while ((match = thinkRegex.exec(raw)) !== null) {
    // 思考前的普通内容
    if (match.index > lastIdx) {
      parts.push({ type: 'content', text: raw.slice(lastIdx, match.index) })
    }
    // 推理内容
    parts.push({ type: 'thinking', text: match[1].trim() })
    lastIdx = match.index + match[0].length
  }
  // 剩余普通内容
  if (lastIdx < raw.length) {
    parts.push({ type: 'content', text: raw.slice(lastIdx) })
  }

  if (parts.length === 0) return DOMPurify.sanitize(mdParser.render(raw))

  return parts.map(p => {
    if (p.type === 'thinking') {
      // 折叠式推理
      const safeHtml = p.text.replace(/</g, '&lt;').replace(/>/g, '&gt;')
      return `<details class="copilot-thinking"><summary>🧠 深度推理（${p.text.length}字）</summary><div class="copilot-thinking-content">${safeHtml}</div></details>`
    }
    return DOMPurify.sanitize(mdParser.render(p.text))
  }).join('')
}

/** 简单渲染（用于缓存消息回显） */
export function mdRender(text) {
  if (!text) return ''
  return renderMarkdown(text)
}

export { mdParser }