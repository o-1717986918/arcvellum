import type { SpatialNarrativeNode } from "@/types/spatial";

export const CHARACTER_REFERENCE_RESOLUTIONS = ["resolved", "unresolved", "ambiguous"] as const;

export type CharacterReferenceResolution = (typeof CHARACTER_REFERENCE_RESOLUTIONS)[number];

export interface CharacterReference {
  reference_id: string;
  node_id: string;
  character_id: string;
  display_name: string;
  aliases: string[];
  resolution: CharacterReferenceResolution;
  matched_names: string[];
  candidate_character_ids: string[];
  scene_ids: string[];
  chapter_ids: string[];
  importance: string;
  source_id: string;
}

export interface CharacterThread {
  node: SpatialNarrativeNode;
  reference: CharacterReference;
  chapterCount: number;
  sceneCount: number;
}

export interface CharacterThreadGroup {
  id: "current" | "book" | "unresolved";
  label: string;
  items: CharacterThread[];
}

export function parseCharacterReference(value: unknown): CharacterReference {
  const source = isRecord(value) ? value : {};
  return {
    reference_id: stringValue(source.reference_id),
    node_id: stringValue(source.node_id),
    character_id: stringValue(source.character_id),
    display_name: stringValue(source.display_name),
    aliases: stringArray(source.aliases),
    resolution: member(source.resolution, CHARACTER_REFERENCE_RESOLUTIONS, "unresolved"),
    matched_names: stringArray(source.matched_names),
    candidate_character_ids: stringArray(source.candidate_character_ids),
    scene_ids: stringArray(source.scene_ids),
    chapter_ids: stringArray(source.chapter_ids),
    importance: stringValue(source.importance) || "secondary",
    source_id: stringValue(source.source_id),
  };
}

export function buildCharacterThreadGroups(
  references: CharacterReference[],
  nodes: SpatialNarrativeNode[],
  activeChapterId = "",
): CharacterThreadGroup[] {
  const nodesById = new Map(nodes.filter((node) => node.type === "character").map((node) => [node.node_id, node]));
  const current: CharacterThread[] = [];
  const book: CharacterThread[] = [];
  const unresolved: CharacterThread[] = [];
  for (const reference of references) {
    const node = nodesById.get(reference.node_id);
    if (!node) continue;
    const thread = {
      node,
      reference,
      chapterCount: reference.chapter_ids.length,
      sceneCount: reference.scene_ids.length,
    };
    if (reference.resolution !== "resolved") unresolved.push(thread);
    else if (activeChapterId && reference.chapter_ids.includes(activeChapterId)) current.push(thread);
    else book.push(thread);
  }
  const sort = (left: CharacterThread, right: CharacterThread) =>
    right.sceneCount - left.sceneCount
    || right.chapterCount - left.chapterCount
    || left.node.label.localeCompare(right.node.label);
  return [
    { id: "current" as const, label: "本章人物", items: current.sort(sort) },
    { id: "book" as const, label: "全书人物", items: book.sort(sort) },
    { id: "unresolved" as const, label: "待解析", items: unresolved.sort(sort) },
  ].filter((group) => group.items.length);
}

function member<T extends string>(value: unknown, values: readonly T[], fallback: T): T {
  return typeof value === "string" && values.includes(value as T) ? value as T : fallback;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(stringValue).filter(Boolean) : [];
}

function stringValue(value: unknown): string {
  return String(value || "").trim();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
