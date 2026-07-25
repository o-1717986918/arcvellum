export const NARRATIVE_FOCUS_LEVELS = ["book", "chapter", "scene", "character"] as const;

export type NarrativeFocusLevel = (typeof NARRATIVE_FOCUS_LEVELS)[number];

export interface NarrativeFocusScope {
  level: NarrativeFocusLevel;
  focus_id: string;
  chapter_ids: string[];
  scene_ids: string[];
  character_ids: string[];
  anchor_node_ids: string[];
  context_node_ids: string[];
}

export function parseNarrativeFocusScope(value: unknown): NarrativeFocusScope {
  const source = isRecord(value) ? value : {};
  return {
    level: isNarrativeFocusLevel(source.level) ? source.level : "book",
    focus_id: stringValue(source.focus_id || source.focus),
    chapter_ids: stringArray(source.chapter_ids),
    scene_ids: stringArray(source.scene_ids),
    character_ids: stringArray(source.character_ids),
    anchor_node_ids: stringArray(source.anchor_node_ids),
    context_node_ids: stringArray(source.context_node_ids),
  };
}

function isNarrativeFocusLevel(value: unknown): value is NarrativeFocusLevel {
  return typeof value === "string" && NARRATIVE_FOCUS_LEVELS.includes(value as NarrativeFocusLevel);
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
