import { describe, expect, it } from "vitest";
import { styleIdentity } from "./styleIdentity";

describe("styleIdentity", () => {
  it("uses readable latin labels when possible", () => {
    expect(styleIdentity("Quiet Historical Prose", "style")).toBe("quiet-historical-prose");
  });

  it("creates a stable valid identity for Chinese labels", () => {
    const first = styleIdentity("鲁迅", "author");
    expect(first).toMatch(/^author-[a-z0-9]{7}$/);
    expect(styleIdentity("鲁迅", "author")).toBe(first);
  });
});
