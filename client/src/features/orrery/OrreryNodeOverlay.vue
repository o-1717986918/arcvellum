<script setup lang="ts">
import { computed, type Component } from "vue";
import { BadgeCheck, BookMarked, BookOpenText, CircleHelp, Clapperboard, FilePenLine, Fingerprint, GitFork, Landmark, MapPinned, Orbit, Scale, Sparkles, UserRound, Waypoints } from "lucide-vue-next";
import type { SpatialNarrativeNode, SpatialNarrativeProjection } from "@/types/spatial";
import type { NarrativeFocusLevel } from "@/features/orrery/model/focusScope";
import { observationWeight } from "@/features/orrery/layout/observationWindow";
import { heatScore, type OrreryHeatLens } from "@/features/orrery/model/exploration";

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

const visible = computed(() => props.nodes
  .filter((node) => Boolean(props.anchors[node.node_id]?.visible))
  .sort((left, right) => nodePriority(right) - nodePriority(left)));

const labeledNodeIds = computed(() => {
  const accepted = new Set<string>();
  const occupied: Array<{ left: number; right: number; top: number; bottom: number }> = [];

  for (const node of visible.value) {
    const anchor = props.anchors[node.node_id];
    if (!anchor) continue;
    const rectangle = labelRectangle(node, anchor);
    // Every visible entity keeps a crisp celestial mark. This pass only
    // decides which marks have enough room for copy; it never removes nodes.
    if (isPinned(node) || props.showAllLabels) {
      accepted.add(node.node_id);
      occupied.push(rectangle);
      continue;
    }
    if (occupied.some((item) => rectanglesOverlap(item, rectangle))) continue;
    accepted.add(node.node_id);
    occupied.push(rectangle);
    if (accepted.size >= 72) break;
  }
  return accepted;
});

function nodePriority(node: SpatialNarrativeNode): number {
  const selected = node.node_id === props.selectedNodeId ? 10_000 : 0;
  const urgent = node.status === "current" ? 3_000 : node.status === "blocked" ? 2_000 : 0;
  const formal = node.status === "formal" ? 260 : 0;
  return selected + urgent + formal + node.importance * 100 + (node.detail_level === "near" ? 30 : 0);
}

function isPinned(node: SpatialNarrativeNode): boolean {
  const sceneCount = visible.value.filter((item) => (item.creative_kind || item.type) === "scene").length;
  return node.node_id === props.selectedNodeId
    || node.node_id === props.focusNodeId
    || node.node_id === props.navigationNodeId
    || Boolean(props.forcedNodeIds?.includes(node.node_id))
    || node.status === "current"
    || node.status === "blocked"
    || node.type === "chapter"
    || (node.type === "scene" && sceneCount <= 28);
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

function rectanglesOverlap(left: { left: number; right: number; top: number; bottom: number }, right: { left: number; right: number; top: number; bottom: number }): boolean {
  return !(left.right + 8 < right.left || right.right + 8 < left.left || left.bottom + 6 < right.top || right.bottom + 6 < left.top);
}

function styleFor(node: SpatialNarrativeNode): Record<string, string | number> {
  const anchor = props.anchors[node.node_id] || { x: -2000, y: -2000, scale: 1 };
  const heat = heatScore(node, props.heatLens || "");
  const renderScale = Math.max(anchor.scale, minimumReadableScale(node));
  return {
    transform: `translate3d(${anchor.x}px, ${anchor.y}px, 0) translate(-50%, -50%) scale(${renderScale})`,
    zIndex: Math.round(100 + renderScale * 160 + node.importance * 100),
    "--observation-weight": observationWeight(node, props.timeCursor || 0, props.timeWindow || 3).toFixed(3),
    "--heat-opacity": (0.54 + heat * 0.46).toFixed(3),
    "--heat-saturation": (0.72 + heat * 0.58).toFixed(3),
    "--heat-brightness": (0.86 + heat * 0.34).toFixed(3),
    "--heat-glow": `${Math.round(5 + heat * 24)}px`,
    "--heat-mix": `${Math.round(24 + heat * 66)}%`,
    "--heat-shadow": `${Math.round(heat * 58)}%`,
  };
}

function minimumReadableScale(node: SpatialNarrativeNode): number {
  const kind = node.creative_kind || node.type;
  if (kind === "chapter") return 1.04;
  if (kind === "scene") return 0.86;
  if (kind === "project") return 1.08;
  if (kind === "character") return 0.82;
  if (["branch", "review", "promise", "reader-question", "human-decision"].includes(kind)) return 0.8;
  return 0.84;
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
  const icons: Record<string, Component> = {
    chapter: BookMarked,
    scene: Clapperboard,
    character: UserRound,
    branch: GitFork,
    review: BadgeCheck,
    canon: Landmark,
    promise: Sparkles,
    "reader-question": CircleHelp,
    project: Orbit,
    "story-architecture": Waypoints,
    "word-budget": Scale,
    style: Fingerprint,
    world: Landmark,
    location: MapPinned,
    draft: FilePenLine,
    "formal-prose": BookOpenText,
  };
  return icons[node.type] || Orbit;
}

function motionClass(node: SpatialNarrativeNode): Record<string, boolean> {
  const event = props.motionEvents?.find((item) => item.node_id === node.node_id);
  if (!event) return {};
  return { [`motion-${event.type}`]: true };
}

function activityClass(node: SpatialNarrativeNode): Record<string, boolean> {
  const activity = props.activities?.find((item) => item.target === node.source_id || item.target === node.node_id);
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
  const forced = Boolean(props.showAllLabels || props.forcedNodeIds?.includes(node.node_id) || node.node_id === props.navigationNodeId);
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
    <button
      v-for="node in visible"
      :key="node.node_id"
      class="orrery-v3-node"
      :class="[{ selected: selectedNodeId === node.node_id, navigating: navigationNodeId === node.node_id, compared: comparedNodeIds?.includes(node.node_id), 'heat-active': Boolean(heatLens), 'creative-live-active': liveNodeIds?.includes(node.node_id), typographic: isTypographic(node), symbolic: !isTypographic(node) }, focusClass(node), motionClass(node), activityClass(node), overviewClass(node)]"
      :data-status="node.status"
      :data-lod="lodFor(node)"
      :data-completion="node.completion_state"
      :data-type="node.type"
      :data-kind="node.creative_kind || node.type"
      :data-lifecycle="node.lifecycle || node.completion_state"
      :style="styleFor(node)"
      :aria-label="`${labelFor(node)}：${node.label}`"
      @click="emit('select', node)"
      @dblclick="emit('focus', node)"
    >
      <span v-if="isTypographic(node)" class="node-luminary" aria-hidden="true"><i></i><b></b></span>
      <span v-else class="node-glyph"><component :is="iconFor(node)" :size="12" :stroke-width="1.85" /></span>
      <span class="node-copy">
        <small class="node-kicker">{{ compactLabelFor(node) }}</small>
        <span class="node-title">{{ displayLabelFor(node) }}</span>
        <small class="node-meta">{{ nodeMetaFor(node) }}</small>
      </span>
    </button>
  </div>
</template>
