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

const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_SEP = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function cellAlignStyle(sepCell: string | undefined): string {
  const cell = (sepCell ?? "").trim();
  if (cell.startsWith(":") && cell.endsWith(":")) return ' style="text-align:center"';
  if (cell.endsWith(":")) return ' style="text-align:right"';
  return "";
}

function buildHtmlTable(lines: string[], start: number): { html: string; next: number } {
  const header = splitTableRow(lines[start]);
  const seps = splitTableRow(lines[start + 1]);
  const aligns = header.map((_, col) => cellAlignStyle(seps[col]));
  let i = start + 2;
  const rows: string[][] = [];
  while (i < lines.length && TABLE_ROW.test(lines[i])) {
    rows.push(splitTableRow(lines[i]));
    i += 1;
  }
  const head = header
    .map((cell, col) => `<th${aligns[col]} class="border border-line px-3 py-1.5 font-semibold">${renderMarkdownInline(cell)}</th>`)
    .join("");
  const body = rows
    .map(
      (row) =>
        "<tr>" +
        header
          .map((_, col) => {
            const cell = row[col] ?? "";
            return `<td${aligns[col]} class="border border-line px-3 py-1.5 align-top">${renderMarkdownInline(cell)}</td>`;
          })
          .join("") +
        "</tr>"
    )
    .join("");
  return {
    html:
      '<div class="my-2 overflow-x-auto rounded-xl"><table class="w-full border-collapse text-sm">' +
      `<thead><tr class="bg-canvas">${head}</tr></thead><tbody>${body}</tbody></table></div>`,
    next: i - 1
  };
}

/**
 * 安全轻量 Markdown 渲染器：先对全部文本做 HTML 转义，防止任何 XSS 注入。
 * 支持标题、列表、引用、代码块、GFM 管道表格与行内加粗/斜体/代码。
 */
export function renderMarkdown(source: string): string {
  const escaped = escapeHtml(source);
  const lines = escaped.split(/\r?\n/);
  const out: string[] = [];
  let inCode = false;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (line.trim().startsWith("```")) {
      out.push(inCode ? "</code></pre>" : '<pre class="overflow-x-auto rounded-xl bg-canvas p-3"><code>');
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      out.push(line);
      continue;
    }
    if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_SEP.test(lines[i + 1])) {
      const table = buildHtmlTable(lines, i);
      out.push(table.html);
      i = table.next;
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
