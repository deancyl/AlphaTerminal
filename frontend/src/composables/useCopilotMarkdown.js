import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const mdParser = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
})

const defaultFenceRenderer = mdParser.renderer.rules.fence || function(tokens, idx, options, env, self) {
  return self.renderToken(tokens, idx, options, env, self)
}

mdParser.renderer.rules.fence = function(tokens, idx, options, env, self) {
  const token = tokens[idx]
  const code = token.content.trim()
  const info = token.info ? token.info.trim() : ''
  const langClass = info ? ` language-${info}` : ''
  const encodedCode = encodeURIComponent(code)
  
  return `<pre class="group" data-code="${encodedCode}"><code class="${langClass}">${mdParser.utils.escapeHtml(code)}</code></pre>`
}

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