<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { SpatialNarrativeEdge, SpatialNarrativeNode, SpatialNarrativeProjection } from "@/types/spatial";

type Anchor = { x: number; y: number; visible: boolean; scale: number };

const props = defineProps<{
  projection: SpatialNarrativeProjection;
  anchors: Record<string, Anchor>;
  activeCharacterId?: string;
}>();

const host = ref<SVGSVGElement | null>(null);
const size = ref({ width: 1, height: 1 });
let resizeObserver: ResizeObserver | null = null;

const primaryType = computed(() => props.projection.level === "book" ? "chapter" : "scene");
const isDetailView = computed(() => props.projection.level !== "book");
const primaryNodes = computed(() => props.projection.nodes
  .filter((node) => node.type === primaryType.value)
  .sort((left, right) => left.order - right.order));
const spinePoints = computed(() => primaryNodes.value
  .map((node) => ({ node, anchor: props.anchors[node.node_id] }))
  .filter((item): item is { node: SpatialNarrativeNode; anchor: Anchor } => Boolean(item.anchor)));
const spinePath = computed(() => buildPath(spinePoints.value.map((item) => item.anchor)));
const spineMarkerPoints = computed(() => spinePoints.value.filter((item) => item.anchor.scale >= 0.56));

const characterRelations = computed(() => {
  const chapterIds = new Set(props.projection.nodes.filter((node) => node.type === "chapter").map((node) => node.node_id));
  return props.projection.edges
    .filter((edge) => edge.type === "participates")
    .map((edge) => ({ edge, characterId: characterEndpoint(edge, chapterIds) }))
    .filter((item): item is { edge: SpatialNarrativeEdge; characterId: string } => Boolean(item.characterId));
});

const localFlowPaths = computed(() => {
  const acceptedTypes = props.projection.level === "chapter"
    ? new Set(["bridge", "raises", "promise"])
    : props.projection.level === "scene"
      ? new Set(["participates", "branch", "review", "canon", "promise", "raises", "workflow"])
      : new Set<string>();
  if (!acceptedTypes.size) return [];
  return props.projection.edges
    .filter((edge) => acceptedTypes.has(edge.type))
    .map((edge) => {
      const source = props.anchors[edge.source];
      const target = props.anchors[edge.target];
      return source && target ? {
        id: edge.edge_id,
        path: relationshipPath(source, target, edge.edge_id),
        type: edge.type,
      } : null;
    })
    .filter((item): item is { id: string; path: string; type: string } => Boolean(item))
    .slice(0, 24);
});

const characterPaths = computed(() => characterRelations.value
  .map(({ edge, characterId }) => {
    const source = props.anchors[edge.source];
    const target = props.anchors[edge.target];
    if (!source || !target) return null;
    return {
      id: edge.edge_id,
      active: characterId === props.activeCharacterId,
      path: relationshipPath(source, target, edge.edge_id),
      color: threadColor(characterId),
    };
  })
  .filter((item): item is { id: string; active: boolean; path: string; color: string } => Boolean(item)));

onMounted(() => {
  if (!host.value) return;
  const update = () => {
    const rect = host.value?.getBoundingClientRect();
    if (rect) size.value = { width: Math.max(1, rect.width), height: Math.max(1, rect.height) };
  };
  update();
  resizeObserver = new ResizeObserver(update);
  resizeObserver.observe(host.value);
});
onBeforeUnmount(() => resizeObserver?.disconnect());

function buildPath(points: Anchor[]): string {
  if (!points.length) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  // Catmull-Rom converted to cubic Beziers. The tangent at every
  // intermediate node is shared by its neighbours, so the visible backbone
  // stays smooth while still passing through every formal chapter or scene.
  const tension = 0.78 / 6;
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let index = 0; index < points.length - 1; index += 1) {
    const before = points[Math.max(0, index - 1)];
    const start = points[index];
    const end = points[index + 1];
    const after = points[Math.min(points.length - 1, index + 2)];
    const controlA = { x: start.x + (end.x - before.x) * tension, y: start.y + (end.y - before.y) * tension };
    const controlB = { x: end.x - (after.x - start.x) * tension, y: end.y - (after.y - start.y) * tension };
    path += ` C ${controlA.x} ${controlA.y}, ${controlB.x} ${controlB.y}, ${end.x} ${end.y}`;
  }
  return path;
}

function relationshipPath(start: Anchor, end: Anchor, identity: string): string {
  const deltaX = end.x - start.x;
  const deltaY = end.y - start.y;
  const distance = Math.max(1, Math.hypot(deltaX, deltaY));
  const normalX = -deltaY / distance;
  const normalY = deltaX / distance;
  const bend = Math.min(124, Math.max(34, distance * 0.18)) * curveDirection(identity);
  const controlA = {
    x: start.x + deltaX * 0.34 + normalX * bend,
    y: start.y + deltaY * 0.34 + normalY * bend,
  };
  const controlB = {
    x: end.x - deltaX * 0.34 + normalX * bend,
    y: end.y - deltaY * 0.34 + normalY * bend,
  };
  return `M ${start.x} ${start.y} C ${controlA.x} ${controlA.y}, ${controlB.x} ${controlB.y}, ${end.x} ${end.y}`;
}

function curveDirection(value: string): number {
  let hash = 0;
  for (const character of value) hash = ((hash << 5) - hash) + character.charCodeAt(0);
  return hash % 2 === 0 ? 1 : -1;
}

function characterEndpoint(edge: SpatialNarrativeEdge, chapterIds: Set<string>): string | null {
  if (chapterIds.has(edge.source)) return edge.target;
  if (chapterIds.has(edge.target)) return edge.source;
  return null;
}

function threadColor(value: string): string {
  let hash = 0;
  for (const character of value) hash = ((hash << 5) - hash) + character.charCodeAt(0);
  const palette = ["var(--orrery-core)", "var(--orrery-branch)", "var(--orrery-canon)", "var(--orrery-warning)"];
  return palette[Math.abs(hash) % palette.length];
}
</script>

<template>
  <svg
    ref="host"
    class="narrative-spine-layer"
    :viewBox="`0 0 ${size.width} ${size.height}`"
    preserveAspectRatio="none"
    aria-hidden="true"
  >
    <path v-if="spinePath" class="narrative-spine-glow" :class="{ detail: isDetailView }" :d="spinePath" />
    <path v-if="spinePath" class="narrative-spine-track" :class="{ detail: isDetailView }" :d="spinePath" />
    <path v-if="spinePath" class="narrative-spine-signal" :class="{ detail: isDetailView }" :d="spinePath" />
    <path
      v-for="connection in localFlowPaths"
      :key="connection.id"
      class="narrative-local-flow"
      :data-level="projection.level"
      :data-type="connection.type"
      :d="connection.path"
    />
    <path
      v-for="relation in characterPaths"
      :key="relation.id"
      class="narrative-character-thread"
      :class="{ active: relation.active, muted: activeCharacterId && !relation.active }"
      :stroke="relation.color"
      :d="relation.path"
    />
    <text
      v-for="(item, index) in spineMarkerPoints"
      :key="item.node.node_id"
      class="narrative-spine-marker"
      :x="item.anchor.x + 18"
      :y="item.anchor.y - 18"
    >{{ String(index + 1).padStart(2, "0") }}</text>
  </svg>
</template>
