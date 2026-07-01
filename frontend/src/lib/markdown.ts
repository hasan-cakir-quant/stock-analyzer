/**
 * Minimal markdown renderer for the notes preview pane.
 *
 * Supports the small subset users actually write in stock theses:
 *   #, ##, ### headings, **bold**, *italic*, `code`, [link](url), and
 *   `*` / `-` bullet lists. Anything else renders as escaped plain text
 *   with newlines preserved.
 *
 * HTML is escaped first, so user input can't inject elements through the
 * `dangerouslySetInnerHTML` consumer. The transformations operate on
 * already-escaped text.
 */

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function isSafeUrl(url: string): boolean {
  // Allow http(s), mailto, and relative URLs. Block javascript:, data:, etc.
  return /^(https?:\/\/|mailto:|\/|\.\/|#)/i.test(url.trim());
}

export function renderMarkdownToHtml(source: string): string {
  if (!source) return "";

  // Tokenise inline markdown after escaping, then assemble line-by-line so
  // bullet groups can be wrapped in <ul>.
  const lines = escapeHtml(source).split(/\r?\n/);
  const out: string[] = [];
  let listOpen = false;

  for (const raw of lines) {
    const line = raw.trimEnd();

    const headingMatch = /^(#{1,3})\s+(.*)$/.exec(line);
    const bulletMatch = /^[*-]\s+(.*)$/.exec(line);

    if (bulletMatch) {
      if (!listOpen) {
        out.push("<ul>");
        listOpen = true;
      }
      out.push(`<li>${transformInline(bulletMatch[1])}</li>`);
      continue;
    }

    if (listOpen) {
      out.push("</ul>");
      listOpen = false;
    }

    if (headingMatch) {
      const level = headingMatch[1].length;
      out.push(`<h${level}>${transformInline(headingMatch[2])}</h${level}>`);
      continue;
    }

    if (line === "") {
      out.push("");
      continue;
    }

    out.push(`<p>${transformInline(line)}</p>`);
  }

  if (listOpen) out.push("</ul>");
  return out.join("\n");
}

function transformInline(text: string): string {
  let html = text;

  // Bold first so `**text**` doesn't get partly consumed by italic.
  html = html.replace(/\*\*([^*]+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+?)\*/g, "<em>$1</em>");
  html = html.replace(/`([^`]+?)`/g, "<code>$1</code>");

  // Links — guarded by a URL allowlist.
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    (_match: string, label: string, url: string) => {
      if (!isSafeUrl(url)) return label;
      return `<a href="${url}" target="_blank" rel="noreferrer">${label}</a>`;
    },
  );

  return html;
}
