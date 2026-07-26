export interface PreparedStyleSource {
  filename: string;
  media_type: "text/plain" | "text/markdown";
  content: string;
  character_count: number;
  file_key: string;
}

const MAX_SOURCE_BYTES = 20 * 1024 * 1024;
const MAX_SOURCE_CHARACTERS = 5_000_000;

export async function decodeStyleSourceFile(file: File): Promise<PreparedStyleSource> {
  const suffix = file.name.match(/\.(txt|md|markdown)$/i)?.[1]?.toLowerCase();
  if (!suffix) throw new Error(`“${file.name}”不是支持的文本格式，请选择 TXT 或 Markdown。`);
  if (file.size > MAX_SOURCE_BYTES) throw new Error(`“${file.name}”超过 20 MB，请拆分后导入。`);

  let content = "";
  try {
    content = new TextDecoder("utf-8", { fatal: true })
      .decode(await file.arrayBuffer())
      .replace(/^\uFEFF/, "")
      .trim();
  } catch {
    throw new Error(`“${file.name}”不是有效的 UTF-8 文本，请转换编码后重试。`);
  }
  if (!content) throw new Error(`“${file.name}”没有可导入的正文。`);
  if (content.length > MAX_SOURCE_CHARACTERS) {
    throw new Error(`“${file.name}”超过 500 万字符，请拆分后导入。`);
  }
  return {
    filename: file.name,
    media_type: suffix === "txt" ? "text/plain" : "text/markdown",
    content,
    character_count: content.length,
    file_key: `${file.name}:${file.size}:${file.lastModified}`,
  };
}
