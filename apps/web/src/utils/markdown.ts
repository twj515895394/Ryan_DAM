export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function renderMarkdownInline(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, '<code class="rounded bg-canvas px-1 py-0.5 font-mono text-xs">$1</code>');
}

/**
 * 安全轻量 Markdown 渲染器：先对全部文本做 HTML 转义，防止任何 XSS 注入。
 */
export function renderMarkdown(source: string): string {
  const escaped = escapeHtml(source);
  const out: string[] = [];
  let inCode = false;
  for (const line of escaped.split(/\r?\n/)) {
    if (line.trim().startsWith("```")) {
      out.push(inCode ? "</code></pre>" : '<pre class="overflow-x-auto rounded-xl bg-canvas p-3"><code>');
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      out.push(line);
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length + 1;
      out.push(`<h${level} class="mt-4 mb-2 font-semibold">` + renderMarkdownInline(heading[2]) + `</h${level}>`);
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      out.push('<li class="ml-5 list-disc">' + renderMarkdownInline(line.replace(/^\s*[-*]\s+/, "")) + "</li>");
      continue;
    }
    if (/^\s*&gt;\s?/.test(line)) {
      out.push('<blockquote class="border-l-2 border-line pl-3 text-muted">' + renderMarkdownInline(line.replace(/^\s*&gt;\s?/, "")) + "</blockquote>");
      continue;
    }
    if (!line.trim()) {
      out.push("<br>");
      continue;
    }
    out.push("<p>" + renderMarkdownInline(line) + "</p>");
  }
  return out.join("");
}
