import type { ParameterImport } from "../stylometryTypes";

type JsonRecord = Record<string, unknown>;
function object(value: unknown): JsonRecord {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("导出文件应包含 JSON 对象。");
  return value as JsonRecord;
}
export async function readParameterFiles(files: File[]): Promise<ParameterImport> {
  if (!files.length || files.reduce((sum, file) => sum + file.size, 0) > 20_000_000) {
    throw new Error("请选择 JSON 导出文件，总计不超过 20 MB。");
  }
  const result: ParameterImport = { profile_json: "", parameters_json: "", dependency_json: "", title: "", intent: "" };
  for (const file of files) {
    let doc: JsonRecord;
    let raw: string;
    try { raw = (await file.text()).replace(/^\uFEFF/, ""); doc = object(JSON.parse(raw)); }
    catch { throw new Error(`${file.name} 的 JSON 格式无法读取，请重新导出。`); }
    mergeDocument(result, doc, file.name, raw);
  }
  return result;
}
function assign(result: ParameterImport, key: "profile_json" | "parameters_json" | "dependency_json", value: unknown) {
  const text = typeof value === "string" ? value : JSON.stringify(object(value));
  if (result[key] && result[key] !== text) throw new Error("同一批导入包含不同的画像、参数或参考树，请分开导入。");
  result[key] = text;
}
function mergeDocument(result: ParameterImport, doc: JsonRecord, filename: string, raw: string) {
  switch (doc.schema) {
    case "stylometric-profile/v1": assign(result, "profile_json", raw); break;
    case "style-controls/v1": case "style-parameter-card/v1": case "stylometric-creator-controls/v1":
      assign(result, "parameters_json", raw);
      result.title = typeof doc.title === "string" ? doc.title : result.title;
      result.intent = typeof doc.intent === "string" ? doc.intent : result.intent;
      break;
    case "style-dependency-parse/v1": assign(result, "dependency_json", raw); break;
    case "stylometric-host/v1":
      assign(result, "profile_json", fieldSource(raw, "profile")); assign(result, "parameters_json", fieldSource(raw, "controls")); break;
    case "arcvellum/stylometry-review-export/v1": {
      const profile = object(doc.profile), version = doc.saved_version ? object(doc.saved_version) : null;
      assign(result, "profile_json", profile.profile_json);
      assign(result, "parameters_json", fieldSource(raw, "controls"));
      const tree = doc.dependency_json || version?.dependency_json || profile.dependency_json;
      if (tree) assign(result, "dependency_json", tree);
      result.title = String(doc.title || version?.title || profile.title || "导入计量文风");
      result.intent = String(doc.intent ?? version?.intent ?? profile.intent ?? "");
      break;
    }
    default: throw new Error(`${filename} 不是计量台的画像、参数、参数卡或原始依存树导出。`);
  }
}

// Keep the original number tokens used by Python's artifact digest (0.0 != 0).
function fieldSource(raw: string, field: string): string {
  let index = raw.indexOf("{") + 1;
  while (index < raw.length) {
    while (/[\s,]/.test(raw[index] || "")) index++;
    if (raw[index] === "}") break;
    const nameEnd = valueEnd(raw, index), name = JSON.parse(raw.slice(index, nameEnd));
    index = nameEnd;
    while (/[\s:]/.test(raw[index] || "")) index++;
    const end = valueEnd(raw, index);
    if (name === field) return raw.slice(index, end);
    index = end;
  }
  throw new Error(`导出文件缺少 ${field} 内容。`);
}
function valueEnd(raw: string, start: number): number {
  let depth = 0, quoted = false, escaped = false;
  for (let index = start; index < raw.length; index++) {
    const char = raw[index];
    if (quoted) {
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === '"') { quoted = false; if (!depth) return index + 1; }
    } else if (!depth && (char === "," || char === "}")) return index;
    else if (char === '"') quoted = true;
    else if (char === "{" || char === "[") depth++;
    else if (char === "}" || char === "]") { depth--; if (!depth) return index + 1; }
  }
  return raw.length;
}
