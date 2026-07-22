<script setup lang="ts">
import { computed, type Component } from "vue";
import { BadgeCheck, BookMarked, CircleHelp, Clapperboard, GitFork, Landmark, Orbit, Sparkles, UserRound } from "lucide-vue-next";
import type { SpatialNarrativeNode, SpatialNarrativeProjection } from "@/types/spatial";

const props = defineProps<{
  nodes: SpatialNarrativeNode[];
  anchors: Record<string, { x: number; y: number; visible: boolean; scale: number }>;
  selectedNodeId?: string;
  focusNodeId?: string;
  level?: "book" | "chapter" | "scene";
  motionEvents?: SpatialNarrativeProjection["motion_events"];
}>();
const emit = defineEmits<{ select: [node: SpatialNarrativeNode]; focus: [node: SpatialNarrativeNode] }>();

const visible = computed(() => {
  const candidates = props.nodes
    .filter((node) => {
      const anchor = props.anchors[node.node_id];
      // Primary narrative beats never disappear from a full-book projection.
      // At distant camera scales they become compact glyphs; their text returns
      // only once the reader enters a sufficiently roomy local segment.
      return Boolean(anchor?.visible) && (isPrimary(node) || node.detail_level !== "far" || isPinned(node));
    })
    .sort((left, right) => nodePriority(right) - nodePriority(left));
  const accepted: SpatialNarrativeNode[] = [];
  const occupied: Array<{ left: number; right: number; top: number; bottom: number }> = [];

  for (const node of candidates) {
    const anchor = props.anchors[node.node_id];
    if (!anchor) continue;
    const rectangle = labelRectangle(node, anchor);
    if (isPrimary(node) && isOverview(node)) {
      accepted.push(node);
      continue;
    }
    // Current work and the selected node are never suppressed. Other labels
    // must earn a place in the viewport instead of overlapping into noise.
    if (!isPinned(node) && occupied.some((item) => rectanglesOverlap(item, rectangle))) continue;
    accepted.push(node);
    occupied.push(rectangle);
    if (accepted.length >= 56 && !isPinned(node)) break;
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
  return node.node_id === props.selectedNodeId
    || node.node_id === props.focusNodeId
    || node.status === "current"
    || node.status === "blocked"
    || node.type === "chapter";
}

function isPrimary(node: SpatialNarrativeNode): boolean {
  return node.type === "chapter" || node.type === "scene";
}

function isOverview(node: SpatialNarrativeNode): boolean {
  const anchor = props.anchors[node.node_id];
  return Boolean(anchor && anchor.scale < 0.59);
}

function labelRectangle(node: SpatialNarrativeNode, anchor: { x: number; y: number; scale: number }): { left: number; right: number; top: number; bottom: number } {
  const width = Math.min(158, Math.max(76, node.label.length * 11.2)) * Math.max(0.74, anchor.scale);
  const height = 42 * Math.max(0.8, anchor.scale);
  return { left: anchor.x - width / 2, right: anchor.x + width / 2, top: anchor.y - 10, bottom: anchor.y + height };
}

function rectanglesOverlap(left: { left: number; right: number; top: number; bottom: number }, right: { left: number; right: number; top: number; bottom: number }): boolean {
  return !(left.right + 8 < right.left || right.right + 8 < left.left || left.bottom + 6 < right.top || right.bottom + 6 < left.top);
}

function styleFor(node: SpatialNarrativeNode): Record<string, string | number> {
  const anchor = props.anchors[node.node_id] || { x: -2000, y: -2000, scale: 1 };
  return {
    transform: `translate3d(${anchor.x}px, ${anchor.y}px, 0) translate(-50%, -50%) scale(${anchor.scale})`,
    zIndex: Math.round(100 + anchor.scale * 160 + node.importance * 100),
  };
}

function labelFor(node: SpatialNarrativeNode): string {
  const labels: Record<string, string> = { chapter: "章节", scene: "场景", character: "人物", branch: "分支", review: "审查", canon: "设定", promise: "承诺", "reader-question": "问题", task: "任务" };
  return labels[node.type] || "资料";
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
    task: Orbit,
  };
  return icons[node.type] || Orbit;
}

function motionClass(node: SpatialNarrativeNode): Record<string, boolean> {
  const event = props.motionEvents?.find((item) => item.node_id === node.node_id);
  if (!event) return {};
  return { [`motion-${event.type}`]: true };
}

function overviewClass(node: SpatialNarrativeNode): Record<string, boolean> {
  // Nodes remain rendered and keyboard-accessible in the global overview.
  // Only text below the legibility threshold is suppressed; it returns as the
  // camera enters a readable local segment.
  return { overview: isOverview(node) };
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
      :class="[{ selected: selectedNodeId === node.node_id }, focusClass(node), motionClass(node), overviewClass(node)]"
      :data-status="node.status"
      :data-type="node.type"
      :style="styleFor(node)"
      :aria-label="`${labelFor(node)}：${node.label}`"
      @click="emit('select', node)"
      @dblclick="emit('focus', node)"
    >
      <span class="node-glyph"><component :is="iconFor(node)" :size="12" :stroke-width="1.85" /></span>
      <span>{{ node.label.slice(0, 14) }}</span>
      <small>{{ labelFor(node) }}</small>
    </button>
  </div>
</template>
