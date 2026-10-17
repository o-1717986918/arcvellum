<script setup lang="ts">
import { computed } from "vue";
import type { SpatialNarrativeNode } from "@/types/spatial";
import { observationWeight } from "./layout/observationWindow";
import { minimumReadableScale } from "./model/nodeSizing";

const props = defineProps<{
  nodes: SpatialNarrativeNode[];
  anchors: Record<string, { x: number; y: number; visible: boolean; scale: number }>;
  labeledNodeIds: Set<string>;
  focusNodeId?: string;
  timeCursor?: number;
  timeWindow?: number;
}>();
const emit = defineEmits<{ select: [node: SpatialNarrativeNode]; focus: [node: SpatialNarrativeNode] }>();
const nodesById = computed(() => new Map(props.nodes.map((node) => [node.node_id, node])));
const opacityById = computed(() => new Map(props.nodes.map((node) => [node.node_id,
  props.focusNodeId && node.node_id !== props.focusNodeId && node.parent_id !== props.focusNodeId
    ? 1 : Math.max(0.72, observationWeight(node, props.timeCursor || 0, props.timeWindow || 3)),
])));
const marks = computed(() => props.nodes.filter((node) => props.anchors[node.node_id]?.visible
  && !props.labeledNodeIds.has(node.node_id)).map((node) => {
    const anchor = props.anchors[node.node_id];
    return { node, x: Math.round(anchor.x * 10) / 10, y: Math.round(anchor.y * 10) / 10,
      radius: (node.type === "chapter" ? 6 : 4) * Math.max(minimumReadableScale(node), anchor.scale) };
  }).reverse());

function choose(event: MouseEvent, focus = false): void {
  const id = (event.target as Element).closest("[data-node-id]")?.getAttribute("data-node-id");
  const node = id ? nodesById.value.get(id) : undefined;
  if (node) focus ? emit("focus", node) : emit("select", node);
}
</script>

<template>
  <svg class="orrery-node-marks" aria-hidden="true" @click="choose($event)" @dblclick="choose($event, true)">
    <circle v-for="mark in marks" :key="mark.node.node_id" :data-node-id="mark.node.node_id"
      :data-type="mark.node.type" :cx="mark.x" :cy="mark.y" :r="mark.radius" :opacity="opacityById.get(mark.node.node_id)">
      <title>{{ mark.node.label }}</title>
    </circle>
  </svg>
</template>

<style scoped>
.orrery-node-marks { position: absolute; inset: 0; z-index: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; filter: drop-shadow(0 0 3px var(--orrery-core)); }
.orrery-node-marks circle { fill: var(--orrery-label); stroke: transparent; stroke-width: 14px; pointer-events: all; cursor: pointer; }
.orrery-node-marks circle[data-type="scene"] { fill: var(--orrery-core); }
.orrery-node-marks circle[data-type="chapter"], .orrery-node-marks circle[data-type="canon"] { fill: var(--orrery-canon); }
.orrery-node-marks circle[data-type="character"], .orrery-node-marks circle[data-type="branch"] { fill: var(--orrery-branch); }
</style>
