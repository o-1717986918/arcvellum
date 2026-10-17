<script setup lang="ts">
import { computed, onMounted, onUpdated, ref, type Component } from "vue";
import { BadgeCheck, BookMarked, BookOpenText, CircleHelp, Clapperboard, FilePenLine, Fingerprint, GitFork, Landmark, MapPinned, Orbit, Scale, Sparkles, UserRound, Waypoints } from "lucide-vue-next";
import type { SpatialNarrativeNode, SpatialNarrativeProjection } from "@/types/spatial";
import type { NarrativeFocusLevel } from "@/features/orrery/model/focusScope";
import { observationWeight } from "@/features/orrery/layout/observationWindow";
import { heatScore, type OrreryHeatLens } from "@/features/orrery/model/exploration";
import { LabelOccupancy } from "@/features/orrery/layout/labelOccupancy";
import OrreryNodeMarks from "./OrreryNodeMarks.vue";
import { minimumReadableScale } from "./model/nodeSizing";

const props = defineProps<{
  nodes: SpatialNarrativeNode[];
  anchors: Record<string, { x: number; y: number; visible: boolean; scale: number }>;
  selectedNodeId?: string;
  focusNodeId?: string;
  navigationNodeId?: string;
  forcedNodeIds?: string[];
  showAllLabels?: boolean;
  heatLens?: OrreryHeatLens;
  comparedNodeIds?: string[];
  level?: NarrativeFocusLevel;
  motionEvents?: SpatialNarrativeProjection["motion_events"];
  activities?: SpatialNarrativeProjection["activities"];
  liveNodeIds?: string[];
  timeCursor?: number;
  timeWindow?: number;
}>();
const emit = defineEmits<{ select: [node: SpatialNarrativeNode]; focus: [node: SpatialNarrativeNode] }>();

const keyboardNodeId = ref("");
const nodeElements = new Map<string, HTMLButtonElement>();
const nodeTransforms = new WeakMap<HTMLButtonElement, string>();
onMounted(positionNodes);
onUpdated(positionNodes);
const prioritized = computed(() => [...props.nodes].sort((left, right) => nodePriority(right) - nodePriority(left)));
const visible = computed(() => prioritized.value.filter((node) => Boolean(props.anchors[node.node_id]?.visible)));
const batchedMarks = computed(() => props.nodes.length > 150 && !props.heatLens);
const motionByNode = computed(() => {
  const index = new Map<string, NonNullable<SpatialNarrativeProjection["motion_events"]>[number]>();
  for (const event of props.motionEvents || []) if (!index.has(event.node_id)) index.set(event.node_id, event);
  return index;
});
const activityByNode = computed(() => {
  const index = new Map<string, NonNullable<SpatialNarrativeProjection["activities"]>[number]>();
  for (const activity of props.activities || []) if (!index.has(activity.target)) index.set(activity.target, activity);
  return index;
});
const forcedNodeSet = computed(() => new Set(props.forcedNodeIds || []));
const comparedNodeSet = computed(() => new Set(props.comparedNodeIds || []));
const liveNodeSet = computed(() => new Set(props.liveNodeIds || []));
const ICONS: Record<string, Component> = {
  chapter: BookMarked, scene: Clapperboard, character: UserRound, branch: GitFork,
  review: BadgeCheck, canon: Landmark, promise: Sparkles, "reader-question": CircleHelp,
  project: Orbit, "story-architecture": Waypoints, "word-budget": Scale, style: Fingerprint,
  world: Landmark, location: MapPinned, draft: FilePenLine, "formal-prose": BookOpenText,
};

const labeledNodeIds = computed(() => {
  const accepted = new Set<string>();
  const occupied = new LabelOccupancy();
  // Reserve pinned labels first, including those later in the stable priority order.
  for (const node of visible.value) {
    if (!isPinned(node) && !props.showAllLabels) continue;
    accepted.add(node.node_id);
    occupied.add(labelRectangle(node, props.anchors[node.node_id]));
  }
  let ordinary = 0;

  for (const node of visible.value) {
    const anchor = props.anchors[node.node_id];
    if (!anchor) continue;
    const rectangle = labelRectangle(node, anchor);
    // Every visible entity keeps a crisp celestial mark. This pass only
    // decides which marks have enough room for copy; it never removes nodes.
    if (accepted.has(node.node_id)) continue;
    if (occupied.overlaps(rectangle)) continue;
    accepted.add(node.node_id);
    occupied.add(rectangle);
    if (++ordinary >= 72) break;
  }
  return accepted;
});

function nodePriority(node: SpatialNarrativeNode): number {
  const selected = node.node_id === props.selectedNodeId ? 10_000 : 0;
  const urgent = node.status === "current" ? 3_000 : node.status === "blocked" ? 2_000 : 0;
  const formal = node.status === "formal" ? 260 : 0;
  const structure = node.type === "chapter" || node.type === "project" ? 500 : 0;
  return selected + urgent + formal + structure + node.importance * 100 + (node.detail_level === "near" ? 30 : 0);
}

function isPinned(node: SpatialNarrativeNode): boolean {
  // Ordinary scenes, including small clusters, still need collision avoidance.
  // Selection, keyboard focus and the explicit all-labels mode retain their copy.
  return node.node_id === props.selectedNodeId
    || node.node_id === keyboardNodeId.value
    || node.node_id === props.focusNodeId
    || node.node_id === props.navigationNodeId
    || forcedNodeSet.value.has(node.node_id)
    || comparedNodeSet.value.has(node.node_id)
    || liveNodeSet.value.has(node.node_id)
    || node.status === "current"
    || node.status === "blocked";
}

function isTypographic(node: SpatialNarrativeNode): boolean {
  return ["project", "story-architecture", "word-budget", "style", "world", "location", "organization", "chapter", "scene", "character", "formal-prose"].includes(node.creative_kind || node.type);
}

function isOverview(node: SpatialNarrativeNode): boolean {
  const anchor = props.anchors[node.node_id];
  return Boolean(anchor && effectiveNodeScale(node, anchor.scale) < farLodThreshold(node));
}

function farLodThreshold(node: SpatialNarrativeNode): number {
  const kind = node.creative_kind || node.type;
  if (kind === "chapter" || kind === "project") return 0.42;
  if (kind === "scene") return 0.54;
  return 0.62;
}

function lodFor(node: SpatialNarrativeNode): "far" | "mid" | "near" {
  const scale = effectiveNodeScale(node, props.anchors[node.node_id]?.scale || 0);
  if (scale < farLodThreshold(node)) return "far";
  return scale < 0.92 ? "mid" : "near";
}

function effectiveNodeScale(node: SpatialNarrativeNode, scale: number): number {
  const kind = node.creative_kind || node.type;
  return ["project", "chapter", "scene", "character"].includes(kind)
    ? Math.max(scale, minimumReadableScale(node))
    : scale;
}

function labelRectangle(node: SpatialNarrativeNode, anchor: { x: number; y: number; scale: number }): { left: number; right: number; top: number; bottom: number } {
  const scale = effectiveNodeScale(node, anchor.scale);
  const overview = scale < 0.59;
  const compactWidth = node.type === "chapter" ? 68 : node.type === "scene" ? 24 : 58;
  const width = (overview ? compactWidth : Math.min(206, Math.max(86, node.label.length * 11.8))) * Math.max(0.74, scale);
  const height = (overview ? 25 : 52) * Math.max(0.8, scale);
  return { left: anchor.x - width / 2, right: anchor.x + width / 2, top: anchor.y - 10, bottom: anchor.y + height };
}

function styleFor(node: SpatialNarrativeNode): Record<string, string | number> {
  const heat = heatScore(node, props.heatLens || "");
  return {
    "--observation-weight": observationWeight(node, props.timeCursor || 0, props.timeWindow || 3).toFixed(3),
    "--heat-opacity": (0.54 + heat * 0.46).toFixed(3),
    "--heat-saturation": (0.72 + heat * 0.58).toFixed(3),
    "--heat-brightness": (0.86 + heat * 0.34).toFixed(3),
    "--heat-glow": `${Math.round(5 + heat * 24)}px`,
    "--heat-mix": `${Math.round(24 + heat * 66)}%`,
    "--heat-shadow": `${Math.round(heat * 58)}%`,
  };
}

function captureNode(nodeId: string, value: unknown): void {
  if (value instanceof HTMLButtonElement) nodeElements.set(nodeId, value);
  else nodeElements.delete(nodeId);
}

function positionNodes(): void {
  // Camera movement owns just two style properties. Reapplying every heat CSS
  // variable and rebuilding hidden text for each anchor dominated dense views.
  for (const node of visible.value) {
    const element = nodeElements.get(node.node_id), anchor = props.anchors[node.node_id];
    if (!element || !anchor) continue;
    if (batchedMarks.value && !labeledNodeIds.value.has(node.node_id)) continue;
    const scale = Math.max(anchor.scale, minimumReadableScale(node));
    const x = Math.round(anchor.x * 10) / 10, y = Math.round(anchor.y * 10) / 10;
    const transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, -50%) scale(${scale})`;
    // CSSOM normalizes whitespace and zero units, so comparing its serialized
    // string caused unchanged anchors to be written again on every ambient tick.
    if (nodeTransforms.get(element) !== transform) {
      element.style.transform = transform;
      nodeTransforms.set(element, transform);
    }
    const z = String(Math.round(100 + scale * 160 + node.importance * 100));
    if (element.style.zIndex !== z) element.style.zIndex = z;
  }
}

function renderDependencies(node: SpatialNarrativeNode): unknown[] {
  return [node, batchedMarks.value, labeledNodeIds.value.has(node.node_id), effectiveNodeScale(node, props.anchors[node.node_id]?.scale || 0),
    props.selectedNodeId, props.focusNodeId, props.navigationNodeId, props.showAllLabels,
    node.node_id === keyboardNodeId.value,
    forcedNodeSet.value.has(node.node_id), comparedNodeSet.value.has(node.node_id), liveNodeSet.value.has(node.node_id),
    motionByNode.value.get(node.node_id), activityByNode.value.get(node.source_id) || activityByNode.value.get(node.node_id),
    props.heatLens, props.timeCursor, props.timeWindow];
}

function labelFor(node: SpatialNarrativeNode): string {
  const labels: Record<string, string> = {
    project: "作品原点", "story-architecture": "全书架构", "word-budget": "篇幅规划", style: "文风",
    world: "世界观", location: "地点", organization: "组织", chapter: "章节", scene: "场景", character: "人物",
    branch: "分支", review: "审查", canon: "设定", promise: "承诺", "reader-question": "问题", draft: "候选正文",
    "formal-prose": "正式正文", "human-decision": "创作决定", delivery: "交付",
  };
  return labels[node.creative_kind || node.type] || "作品资料";
}

function compactLabelFor(node: SpatialNarrativeNode): string {
  if (node.type === "chapter") {
    const match = node.label.match(/第[\d一二三四五六七八九十百千万零〇两]+[章节卷部幕]/);
    return match?.[0] || `第${Math.max(1, Math.round(node.order) + 1)}章`;
  }
  if (node.type === "scene") return `场景 ${String(Math.max(1, Math.round(node.order) + 1)).padStart(2, "0")}`;
  return labelFor(node);
}

function displayLabelFor(node: SpatialNarrativeNode): string {
  return node.label.length > 30 ? `${node.label.slice(0, 29)}…` : node.label;
}

function nodeMetaFor(node: SpatialNarrativeNode): string {
  const kind = node.creative_kind || node.type;
  const formalChars = Number(node.metrics.formal_chars || 0);
  const wordTarget = Number(node.metrics.word_target || 0);
  if (kind === "chapter" && (formalChars || wordTarget)) {
    return `${formalChars.toLocaleString()}${wordTarget ? ` / ${wordTarget.toLocaleString()}` : ""} 字`;
  }
  if (kind === "scene" && formalChars) return `${formalChars.toLocaleString()} 字正文`;
  return ({
    current: "正在形成",
    blocked: "等待处理",
    formal: "已进入正式项目",
    alternative: "候选路径",
    memory: "已写回记忆",
  } as Record<string, string>)[node.status] || "作品事实";
}

function iconFor(node: SpatialNarrativeNode): Component {
  return ICONS[node.type] || Orbit;
}

function motionClass(node: SpatialNarrativeNode): Record<string, boolean> {
  const event = motionByNode.value.get(node.node_id);
  if (!event) return {};
  return { [`motion-${event.type}`]: true };
}

function activityClass(node: SpatialNarrativeNode): Record<string, boolean> {
  const activity = activityByNode.value.get(node.source_id) || activityByNode.value.get(node.node_id);
  if (!activity) return {};
  return {
    "activity-running": ["active", "running"].includes(activity.status),
    "activity-blocked": ["blocked", "failed"].includes(activity.status),
  };
}

function overviewClass(node: SpatialNarrativeNode): Record<string, boolean> {
  // Nodes remain rendered and keyboard-accessible in the global overview.
  // Only text below the legibility threshold is suppressed; it returns as the
  // camera enters a readable local segment.
  const forced = Boolean(props.showAllLabels || forcedNodeSet.value.has(node.node_id)
    || node.node_id === props.navigationNodeId || node.node_id === keyboardNodeId.value);
  return {
    overview: isOverview(node) && !forced,
    "forced-label": forced,
    "label-suppressed": !labeledNodeIds.value.has(node.node_id) && !forced,
  };
}

function focusClass(node: SpatialNarrativeNode): Record<string, boolean> {
  if (!props.focusNodeId) return {};
  return {
    focused: node.node_id === props.focusNodeId,
    related: node.parent_id === props.focusNodeId,
    distant: node.node_id !== props.focusNodeId && node.parent_id !== props.focusNodeId,
  };
}
</script>

<template>
  <div class="orrery-v3-node-overlay" aria-label="可交互叙事节点">
    <OrreryNodeMarks v-if="batchedMarks" :nodes="prioritized" :anchors="anchors" :labeled-node-ids="labeledNodeIds"
      :focus-node-id="focusNodeId" :time-cursor="timeCursor" :time-window="timeWindow"
      @select="emit('select', $event)" @focus="emit('focus', $event)" />
    <button
      v-for="node in visible"
      :key="node.node_id"
      v-memo="renderDependencies(node)"
      :ref="(value) => captureNode(node.node_id, value)"
      class="orrery-v3-node"
      :class="[{ selected: selectedNodeId === node.node_id, navigating: navigationNodeId === node.node_id, compared: comparedNodeSet.has(node.node_id), 'heat-active': Boolean(heatLens), 'creative-live-active': liveNodeSet.has(node.node_id), typographic: isTypographic(node), symbolic: !isTypographic(node), 'mark-only': !labeledNodeIds.has(node.node_id), 'batched-mark': batchedMarks && !labeledNodeIds.has(node.node_id) }, focusClass(node), motionClass(node), activityClass(node), overviewClass(node)]"
      :data-node-id="node.node_id"
      :data-status="node.status"
      :data-lod="lodFor(node)"
      :data-completion="node.completion_state"
      :data-type="node.type"
      :data-kind="node.creative_kind || node.type"
      :data-lifecycle="node.lifecycle || node.completion_state"
      :style="styleFor(node)"
      :aria-label="`${labelFor(node)}：${node.label}`"
      :title="node.label"
      @focus="keyboardNodeId = node.node_id"
      @blur="keyboardNodeId = ''"
      @click="emit('select', node)"
      @dblclick="emit('focus', node)"
    >
      <template v-if="labeledNodeIds.has(node.node_id)">
      <span v-if="isTypographic(node)" class="node-luminary" aria-hidden="true"><i></i><b></b></span>
      <span v-else class="node-glyph"><component :is="iconFor(node)" :size="12" :stroke-width="1.85" /></span>
      <span class="node-copy">
        <small class="node-kicker">{{ compactLabelFor(node) }}</small>
        <span class="node-title">{{ displayLabelFor(node) }}</span>
        <small class="node-meta">{{ nodeMetaFor(node) }}</small>
      </span>
      </template>
    </button>
  </div>
</template>

<style scoped>
.orrery-v3-node.mark-only {
  display: block;
  width: 22px;
  min-width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}
.orrery-v3-node.mark-only::before {
  position: absolute;
  inset: 7px;
  background: var(--type-star, var(--orrery-core));
  border-radius: 50%;
  box-shadow: 0 0 6px var(--type-star, var(--orrery-core));
  content: "";
}
.orrery-v3-node.mark-only::after { display: none; }
.orrery-v3-node.mark-only[data-type="chapter"]::before { inset: 5px; border: 1px solid var(--orrery-canon); }
/* Keep the same native buttons in the tab order. Focusing one promotes its
   glyph to the full DOM label before the next paint; no entity loses access. */
.orrery-v3-node.batched-mark {
  position: absolute; top: 0; left: 0; width: 1px; min-width: 1px; height: 1px;
  padding: 0; margin: -1px; overflow: hidden; clip-path: inset(50%);
  transform: none !important; pointer-events: none;
}
</style>
