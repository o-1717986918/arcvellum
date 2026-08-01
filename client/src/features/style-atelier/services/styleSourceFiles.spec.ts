import { describe, expect, it } from "vitest";
import {
  decodeStyleSourceFile,
  sanitizeStyleSourceText,
} from "./styleSourceFiles";

function sourceFile(name: string, bytes: Uint8Array, lastModified = 1): File {
  return {
    name,
    size: bytes.byteLength,
    lastModified,
    arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
  } as File;
}

describe("style source files", () => {
  it("decodes UTF-8 text and derives a stable import identity", async () => {
    const prepared = await decodeStyleSourceFile(
      sourceFile("春灯记.md", new TextEncoder().encode("\uFEFF# 春灯记\n\n第一章。"), 42),
    );

    expect(prepared.filename).toBe("春灯记.md");
    expect(prepared.media_type).toBe("text/markdown");
    expect(prepared.content).toBe("# 春灯记\n\n第一章。");
    expect(prepared.file_key).toContain("春灯记.md");
  });

  it("rejects unsupported files and invalid UTF-8 before starting a transaction", async () => {
    await expect(
      decodeStyleSourceFile(sourceFile("手稿.docx", new TextEncoder().encode("正文"))),
    ).rejects.toThrow("TXT 或 Markdown");
    await expect(
      decodeStyleSourceFile(sourceFile("乱码.txt", new Uint8Array([0xff, 0xfe, 0xfd]))),
    ).rejects.toThrow("无法识别编码");
  });

  it("decodes GB18030 text that is common on Chinese Windows", async () => {
    const prepared = await decodeStyleSourceFile(
      sourceFile("手稿.txt", new Uint8Array([0xd6, 0xd0, 0xce, 0xc4])),
    );

    expect(prepared.content).toBe("中文");
  });

  it("strips NUL padding from otherwise valid UTF-8 files", async () => {
    const bytes = new TextEncoder().encode("正文");
    const withNul = new Uint8Array([...bytes, 0x00, 0x00]);
    const prepared = await decodeStyleSourceFile(
      sourceFile("正文.txt", withNul),
    );

    expect(prepared.content).toBe("正文");
  });

  it("rejects files that genuinely contain replacement characters", async () => {
    const bytes = new TextEncoder().encode("正\uFFFD文");
    await expect(
      decodeStyleSourceFile(sourceFile("损坏.txt", bytes)),
    ).rejects.toThrow("替换字符");
  });

  it("sanitizes pasted text before a transaction starts", () => {
    const cleaned = sanitizeStyleSourceText("\uFEFF正文\x00\x00\n第二段");
    expect(cleaned.ok).toBe(true);
    expect(cleaned.content).toBe("正文\n第二段");

    const corrupt = sanitizeStyleSourceText("正\uFFFD文");
    expect(corrupt.ok).toBe(false);
    expect(corrupt.message).toContain("替换字符");

    const empty = sanitizeStyleSourceText("\x00 \x00");
    expect(empty.ok).toBe(false);
  });
});
