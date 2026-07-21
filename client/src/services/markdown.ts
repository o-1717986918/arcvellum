import DOMPurify from "dompurify";
import MarkdownIt from "markdown-it";

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false,
});

markdown.validateLink = (value: string) => /^https?:\/\//i.test(value.trim());
markdown.renderer.rules.image = () => "";

export function renderSafeMarkdown(value: unknown): string {
  const source = normalizeAdvisorMarkdown(String(value || ""));
  if (!source) return "";
  const clean = DOMPurify.sanitize(markdown.render(source), {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ["img", "style", "iframe", "object", "embed", "form", "input", "button", "video", "audio"],
    FORBID_ATTR: ["style", "srcset"],
  });
  const template = document.createElement("template");
  template.innerHTML = clean;
  for (const anchor of template.content.querySelectorAll("a")) {
    const href = anchor.getAttribute("href") || "";
    if (!/^https?:\/\//i.test(href)) {
      anchor.replaceWith(document.createTextNode(anchor.textContent || href));
      continue;
    }
    anchor.setAttribute("target", "_blank");
    anchor.setAttribute("rel", "noopener noreferrer");
  }
  return template.innerHTML;
}

function normalizeAdvisorMarkdown(source: string): string {
  return source
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, "")
    .replace(/<[^>]+>/g, "")
    .replace(/!\[[^\]]*\]\([^\n)]*(?:\)[^\n)]*)?\)/g, "")
    .replace(/\[([^\]]+)\]\(\s*(?:javascript|vbscript|data):[^\n]*?\)/gi, "$1")
    .replace(/\b(?:javascript|vbscript):/gi, "");
}
