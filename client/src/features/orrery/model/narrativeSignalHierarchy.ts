import type { CharacterReference } from "@/features/orrery/model/characters";
import type { NarrativeFocusLevel } from "@/features/orrery/model/focusScope";
import type { SpatialNarrativeEdge, SpatialNarrativeNode } from "@/types/spatial";

export type OrrerySignalMode = "narrative" | "all";

export interface NarrativeSignalContext {
  mode: OrrerySignalMode;
  edges: SpatialNarrativeEdge[];
  characterReferences?: CharacterReference[];
  level?: NarrativeFocusLevel;
  activeChapterId?: string;
  pinnedNodeIds?: string[];
}

export interface NarrativeSignalResult {
  nodes: SpatialNarrativeNode[];
  nodeIds: Set<string>;
  total: number;
  omitted: number;
}

const BACKBONE_KINDS = new Set(["project", "volume", "chapter"]);
const ARCHIVE_KINDS = new Set([
  "story-architecture", "word-budget", "style", "world", "location", "organization",
  "relationship", "event", "draft", "formal-prose",
]);
const TRANSIENT_KINDS = new Set([
  "branch", "reader-question", "promise", "payoff", "review", "revision", "canon",
  "human-decision", "delivery", "task",
]);
const PRIMARY_CHARACTER_LABELS = new Set(["primary", "major", "lead", "protagonist", "main", "主要", "主角"]);

/**
 * Build a presentation-only view of the project graph. The source projection
 * remains complete; this function decides which facts deserve permanent space
 * in the reader-facing sky and which should appear only on demand.
 */
export function buildNarrativeSignalHierarchy(
  nodes: SpatialNarrativeNode[],
  context: NarrativeSignalContext,
): NarrativeSignalResult {
  if (context.mode === "all") return result(nodes, nodes.length);

  const pinned = new Set((context.pinnedNodeIds || []).filter(Boolean));
  const attention = new Set(nodes.filter(isAttentionNode).map((node) => node.node_id));
  for (const nodeId of pinned) attention.add(nodeId);
  const adjacentToAttention = adjacentNodeIds(context.edges, attention);
  const primaryCharacters = primaryCharacterIds(context.characterReferences || [], context.activeChapterId || "");
  const detailChapterId = context.activeChapterId || currentChapterId(nodes) || firstChapterId(nodes);

  const visible = nodes.filter((node) => {
    const kind = node.creative_kind || node.type;
    if (BACKBONE_KINDS.has(kind)) return true;
    if (attention.has(node.node_id)) return true;

    if (kind === "scene") {
      return context.level !== "book" && sceneChapterId(node) === detailChapterId;
    }

    if (kind === "character") {
      return primaryCharacters.has(node.node_id)
        || node.importance >= 0.72
        || adjacentToAttention.has(node.node_id);
    }

    if (ARCHIVE_KINDS.has(kind)) return false;

    if (TRANSIENT_KINDS.has(kind)) {
      if (adjacentToAttention.has(node.node_id)) return true;
      return isOpenNarrativeSignal(node);
    }

    return adjacentToAttention.has(node.node_id) && node.importance >= 0.62;
  });

  return result(visible, nodes.length);
}

function currentChapterId(nodes: SpatialNarrativeNode[]): string {
  return sceneChapterId(nodes.find((node) => (node.creative_kind || node.type) === "scene" && isAttentionNode(node)));
}

function firstChapterId(nodes: SpatialNarrativeNode[]): string {
  const chapter = nodes
    .filter((node) => (node.creative_kind || node.type) === "chapter")
    .sort((left, right) => left.order - right.order)[0];
  return normalizeChapterId(chapter?.source_id || chapter?.node_id || "");
}

function sceneChapterId(node?: SpatialNarrativeNode): string {
  if (!node) return "";
  return normalizeChapterId(String(node.metrics.chapter_id || node.parent_id || node.cluster_id || ""));
}

function normalizeChapterId(value: string): string {
  return value.trim().replace(/^chapter:/, "");
}

function result(nodes: SpatialNarrativeNode[], total: number): NarrativeSignalResult {
  return {
    nodes,
    nodeIds: new Set(nodes.map((node) => node.node_id)),
    total,
    omitted: Math.max(0, total - nodes.length),
  };
}

function isAttentionNode(node: SpatialNarrativeNode): boolean {
  return node.status === "current"
    || node.status === "blocked"
    || node.completion_state === "active"
    || node.completion_state === "blocked"
    || ["active", "awaiting", "reviewing", "revision", "blocked"].includes(String(node.lifecycle || ""));
}

function isOpenNarrativeSignal(node: SpatialNarrativeNode): boolean {
  const kind = node.creative_kind || node.type;
  // Promises, questions, branches and decisions remain available in the
  // archive and all-details view. In the permanent sky they surface through
  // attention state or a direct edge to the current work, not merely because
  // they have not been closed yet. Otherwise a long book becomes hundreds of
  // equally loud unresolved reminders.
  if (kind === "delivery") return ["available", "active", "awaiting"].includes(String(node.lifecycle || ""));
  return false;
}

function adjacentNodeIds(edges: SpatialNarrativeEdge[], roots: Set<string>): Set<string> {
  const adjacent = new Set<string>();
  for (const edge of edges) {
    if (roots.has(edge.source)) adjacent.add(edge.target);
    if (roots.has(edge.target)) adjacent.add(edge.source);
  }
  return adjacent;
}

function primaryCharacterIds(references: CharacterReference[], activeChapterId: string): Set<string> {
  return new Set(references
    .filter((reference) => PRIMARY_CHARACTER_LABELS.has(reference.importance.toLowerCase())
      || Boolean(activeChapterId && reference.chapter_ids.includes(activeChapterId)))
    .map((reference) => reference.node_id));
}
