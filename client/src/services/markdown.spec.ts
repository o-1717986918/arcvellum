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

  it("renders archive tables while stripping hostile embedded markup", () => {
    const html = renderSafeMarkdown("| 人物 | 影响 |\n| --- | --- |\n| 阿青 | 改变下一场选择 |\n\n<svg onload=\"alert(1)\"></svg><a href=\"data:text/html,boom\">bad</a>");
    expect(html).toContain("<table>");
    expect(html).toContain("<td>阿青</td>");
    expect(html).not.toContain("<svg");
    expect(html).not.toContain("onload");
    expect(html).not.toContain("data:text/html");
  });
});
