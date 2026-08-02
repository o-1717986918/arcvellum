export interface PreparedStyleSource {
  filename: string;
  media_type: "text/plain" | "text/markdown";
  content: string;
  character_count: number;
  file_key: string;
  replacement_count?: number;
}

export interface SanitizedStyleText {
  ok: boolean;
  content: string;
  message?: string;
  replacement_count?: number;
}

export type StyleSourceEncoding =
  | "auto"
  | "utf-8"
  | "gb18030"
  | "big5"
  | "utf-16";

const MAX_SOURCE_BYTES = 20 * 1024 * 1024;
const MAX_SOURCE_CHARACTERS = 5_000_000;

export class StyleSourceEncodingError extends Error {
  replacementCount: number;

  constructor(message: string, replacementCount = 0) {
    super(message);
    this.name = "StyleSourceEncodingError";
    this.replacementCount = replacementCount;
  }
}

export async function decodeStyleSourceFile(
  file: File,
  encoding: StyleSourceEncoding = "auto",
): Promise<PreparedStyleSource> {
  assertStyleSourceFile(file);
  const decoded = decodeStyleSourceBytes(await file.arrayBuffer(), encoding);
  if (decoded === null) {
    throw new StyleSourceEncodingError(
      `“${file.name}”无法识别编码（已尝试 UTF-8、GB18030、BIG5 与 UTF-16）。请把文件另存为 UTF-8 后重试。`,
    );
  }
  const sanitized = sanitizeStyleSourceText(decoded);
  if (!sanitized.ok) {
    if (sanitized.replacement_count) {
      throw new StyleSourceEncodingError(
        `“${file.name}”含有 ${sanitized.replacement_count} 个无法识别的替换字符（�）。` +
          "这些字符在源文件里已经损坏、无法恢复；可改用未损坏的原文，或在文件选择框里选择“移除并导入”。",
        sanitized.replacement_count,
      );
    }
    throw new Error(
      sanitized.message === "没有可导入的正文。"
        ? `“${file.name}”没有可导入的正文。`
        : `“${file.name}”${sanitized.message}`,
    );
  }
  return prepareStyleSourceText(file, sanitized.content, sanitized.replacement_count || 0);
}

export async function decodeStyleSourceFileLenient(
  file: File,
  encoding: StyleSourceEncoding = "auto",
): Promise<PreparedStyleSource> {
  assertStyleSourceFile(file);
  const decoded = decodeStyleSourceBytes(await file.arrayBuffer(), encoding);
  if (decoded === null) {
    throw new StyleSourceEncodingError(
      `“${file.name}”无法识别编码（已尝试 UTF-8、GB18030、BIG5 与 UTF-16）。`,
    );
  }
  const sanitized = sanitizeStyleSourceText(decoded);
  if (!sanitized.ok && !sanitized.replacement_count) {
    throw new Error(`“${file.name}”没有可导入的正文。`);
  }
  return prepareStyleSourceText(
    file,
    sanitized.content,
    sanitized.replacement_count || 0,
  );
}

export function sanitizeStyleSourceText(text: string): SanitizedStyleText {
  const content = text
    .replace(/^[\uFEFF\uFFFE]/, "")
    .replace(/\x00/g, "")
    .trim();
  if (!content) {
    return { ok: false, content: "", message: "没有可导入的正文。" };
  }
  const replacementCount = (content.match(/\ufffd/g) || []).length;
  if (replacementCount) {
    return {
      ok: false,
      content: content.replace(/\ufffd/g, ""),
      message: "里含有无法识别的替换字符。",
      replacement_count: replacementCount,
    };
  }
  return { ok: true, content };
}

function prepareStyleSourceText(
  file: File,
  normalized: string,
  replacementCount: number,
): PreparedStyleSource {
  const suffix = file.name.match(/\.(txt|md|markdown)$/i)?.[1]?.toLowerCase();
  if (normalized.length > MAX_SOURCE_CHARACTERS) {
    throw new Error(`“${file.name}”超过 500 万字符，请拆分后导入。`);
  }
  return {
    filename: file.name,
    media_type: suffix === "txt" ? "text/plain" : "text/markdown",
    content: normalized,
    character_count: normalized.length,
    file_key: `${file.name}:${file.size}:${file.lastModified}`,
    replacement_count: replacementCount || undefined,
  };
}

function assertStyleSourceFile(file: File): void {
  if (!file.name.match(/\.(txt|md|markdown)$/i)) {
    throw new Error(`“${file.name}”不是支持的文本格式，请选择 TXT 或 Markdown。`);
  }
  if (file.size > MAX_SOURCE_BYTES) {
    throw new Error(`“${file.name}”超过 20 MB，请拆分后导入。`);
  }
}

function decodeStyleSourceBytes(
  bytes: ArrayBuffer,
  encoding: StyleSourceEncoding,
): string | null {
  const view = new Uint8Array(bytes);
  const labels =
    encoding === "auto"
      ? [...bomLabels(view), "utf-8", "gb18030"]
      : explicitLabels(encoding);
  for (const label of labels) {
    try {
      return new TextDecoder(label, { fatal: true }).decode(bytes);
    } catch {
      continue;
    }
  }
  return null;
}

function bomLabels(bytes: Uint8Array): string[] {
  if (bytes.length % 2 !== 0) return [];
  if (bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xfe) {
    return ["utf-16le"];
  }
  if (bytes.length >= 2 && bytes[0] === 0xfe && bytes[1] === 0xff) {
    return ["utf-16be"];
  }
  return [];
}

function explicitLabels(encoding: StyleSourceEncoding): string[] {
  if (encoding === "utf-16") return ["utf-16le", "utf-16be"];
  return [encoding];
}
