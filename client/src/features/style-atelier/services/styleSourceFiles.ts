export interface PreparedStyleSource {
  filename: string;
  media_type: "text/plain" | "text/markdown";
  content: string;
  character_count: number;
  file_key: string;
}

export interface SanitizedStyleText {
  ok: boolean;
  content: string;
  message?: string;
}

const MAX_SOURCE_BYTES = 20 * 1024 * 1024;
const MAX_SOURCE_CHARACTERS = 5_000_000;

export async function decodeStyleSourceFile(file: File): Promise<PreparedStyleSource> {
  const suffix = file.name.match(/\.(txt|md|markdown)$/i)?.[1]?.toLowerCase();
  if (!suffix) throw new Error(`“${file.name}”不是支持的文本格式，请选择 TXT 或 Markdown。`);
  if (file.size > MAX_SOURCE_BYTES) throw new Error(`“${file.name}”超过 20 MB，请拆分后导入。`);

  const content = decodeStyleSourceBytes(await file.arrayBuffer());
  if (content === null) {
    throw new Error(`“${file.name}”无法识别编码，请把文件另存为 UTF-8 或 GB18030 后重试。`);
  }
  const sanitized = sanitizeStyleSourceText(content);
  if (!sanitized.ok) {
    throw new Error(
      sanitized.message === "没有可导入的正文。"
        ? `“${file.name}”没有可导入的正文。`
        : `“${file.name}”${sanitized.message}`,
    );
  }
  const normalized = sanitized.content;
  if (normalized.length > MAX_SOURCE_CHARACTERS) {
    throw new Error(`“${file.name}”超过 500 万字符，请拆分后导入。`);
  }
  return {
    filename: file.name,
    media_type: suffix === "txt" ? "text/plain" : "text/markdown",
    content: normalized,
    character_count: normalized.length,
    file_key: `${file.name}:${file.size}:${file.lastModified}`,
  };
}

export function sanitizeStyleSourceText(text: string): SanitizedStyleText {
  const content = text.replace(/^\uFEFF/, "").replace(/\x00/g, "").trim();
  if (!content) {
    return { ok: false, content: "", message: "没有可导入的正文。" };
  }
  if (content.includes("\ufffd")) {
    return {
      ok: false,
      content,
      message: "里含有无法识别的替换字符，请从原始文件重新复制并另存为 UTF-8。",
    };
  }
  return { ok: true, content };
}

function decodeStyleSourceBytes(bytes: ArrayBuffer): string | null {
  for (const label of ["utf-8", "gb18030"]) {
    try {
      return new TextDecoder(label, { fatal: true }).decode(bytes);
    } catch {
      continue;
    }
  }
  return null;
}
