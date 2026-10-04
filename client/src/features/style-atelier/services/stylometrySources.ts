import { api, query } from "@/services/api";
import { decodeStyleSourceFile } from "./styleSourceFiles";
import type { ArchiveAssetDetail, ArchiveAssetGroup } from "@/features/archive/types";
import type { CorpusSource } from "../stylometryTypes";

export async function sourceChoices(root: string) {
  const tree = await api<{ groups: ArchiveAssetGroup[] }>(`/archive/tree?${query({ project_root: root })}`);
  return tree.groups.flatMap(group => group.items);
}
export async function sourceFromArchive(root: string, assetId: string): Promise<CorpusSource> {
  const result = await api<{ asset: ArchiveAssetDetail }>(`/archive/assets/${encodeURIComponent(assetId)}?${query({ project_root: root })}`);
  return source(result.asset.content, result.asset.source_path || assetId, result.asset.revision,
    result.asset.media_type === "text/markdown");
}
export async function sourceFromFile(file: File): Promise<CorpusSource> {
  const decoded = await decodeStyleSourceFile(file);
  return source(decoded.content, file.name, "", decoded.media_type === "text/markdown");
}
export function source(text: string, origin = "粘贴文本", revision = "", markdown = false): CorpusSource {
  return { source_id: "source-" + crypto.randomUUID(), work_id: "work-1", text,
    split: "train", topic: "unknown", genre: "narrative", markdown, origin, revision };
}
