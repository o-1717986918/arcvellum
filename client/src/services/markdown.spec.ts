import { describe, expect, it } from "vitest";
import { renderSafeMarkdown } from "./markdown";

describe("renderSafeMarkdown", () => {
  it("renders useful advisor markdown", () => {
    const html = renderSafeMarkdown("## 判断\n\n- 人物动机成立\n- **代价**仍需补齐\n\n> 这一点来自正文。\n\n`scene` ");
    expect(html).toContain("<h2>判断</h2>");
    expect(html).toContain("<ul>");
    expect(html).toContain("<strong>代价</strong>");
    expect(html).toContain("<blockquote>");
    expect(html).toContain("<code>scene</code>");
  });

  it("removes raw html scripts images and unsafe links", () => {
    const html = renderSafeMarkdown('<script>alert(1)</script>\n<img src="https://tracker.invalid/x">\n[x](javascript:alert(1))\n[site](https://example.com)');
    expect(html).not.toContain("<script");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("javascript:");
    expect(html).toContain('href="https://example.com"');
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it("tolerates partial streaming markdown", () => {
    expect(() => renderSafeMarkdown("```text\nunfinished")).not.toThrow();
  });
});
