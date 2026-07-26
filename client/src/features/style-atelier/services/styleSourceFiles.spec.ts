import { describe, expect, it } from "vitest";
import { decodeStyleSourceFile } from "./styleSourceFiles";

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
    ).rejects.toThrow("UTF-8");
  });
});
