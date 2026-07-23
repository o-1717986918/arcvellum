<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { SpatialCompletionState, SpatialNarrativeEdge, SpatialNarrativeNode, SpatialNarrativeProjection } from "@/types/spatial";

type Anchor = { x: number; y: number; visible: boolean; scale: number };
type SpinePoint = { node: SpatialNarrativeNode; anchor: Anchor };
type SpineCluster = { id: string; node: SpatialNarrativeNode; anchor: Anchor; members: SpinePoint[] };

const props = defineProps<{
  projection: SpatialNarrativeProjection;
  anchors: Record<string, Anchor>;
  activeCharacterId?: string;
  activeChapterId?: string;
}>();

const host = ref<SVGSVGElement | null>(null);
const size = ref({ width: 1, height: 1 });
let resizeObserver: ResizeObserver | null = null;

const isDetailView = computed(() => props.projection.level !== "book");
const spineClusters = computed<SpineCluster[]>(() => chapterCentroids(props.projection.nodes, props.anchors));
const spinePoints = computed<SpinePoint[]>(() => spineClusters.value.map((cluster) => ({ node: cluster.node, anchor: cluster.anchor })));
const spinePath = computed(() => buildPath(spinePoints.value.map((item) => item.anchor)));
const spineSegments = computed(() => spineClusters.value.slice(1).map((cluster, index) => {
  const previous = spineClusters.value[index];
  return {
    id: `${previous.id}>${cluster.id}`,
    path: buildPath([previous.anchor, cluster.anchor]),
    completion: chapterCompletion(cluster),
    ...chapterState(cluster.id),
  };
}));
const chapterSpokes = computed(() => spineClusters.value.flatMap((cluster) => cluster.members
  .filter((member) => Math.hypot(member.anchor.x - cluster.anchor.x, member.anchor.y - cluster.anchor.y) > 3)
  .map((member) => ({
    id: `${cluster.id}:${member.node.node_id}`,
    start: cluster.anchor,
    end: member.anchor,
    ...chapterState(cluster.id),
    completion: chapterCompletion(cluster),
  }))));
const nodesById = computed(() => new Map(props.projection.nodes.map((node) => [node.node_id, node])));
const activeChapterKey = computed(() => chapterKey(props.activeChapterId));
const hasChapterFocus = computed(() => Boolean(activeChapterKey.value));

const characterRelations = computed(() => {
  const chapterIds = new Set(props.projection.nodes.filter((node) => node.type === "chapter").map((node) => node.node_id));
  return props.projection.edges
    .filter((edge) => edge.type === "participates")
    .map((edge) => ({ edge, characterId: characterEndpoint(edge, chapterIds) }))
    .filter((item): item is { edge: SpatialNarrativeEdge; characterId: string } => Boolean(item.characterId));
});

const localFlowPaths = computed(() => {
  const acceptedTypes = props.projection.level === "book" ? new Set<string>() : new Set(["bridge"]);
  if (!acceptedTypes.size) return [];
  return props.projection.edges
    .filter((edge) => acceptedTypes.has(edge.type))
    .map((edge) => {
      const source = props.anchors[edge.source];
      const target = props.anchors[edge.target];
      return source && target && source.visible && target.visible && source.scale >= 0.62 && target.scale >= 0.62 ? {
        id: edge.edge_id,
        path: relationshipPath(source, target, edge.edge_id),
        type: edge.type,
        ...edgeChapterState(edge),
      } : null;
    })
    .filter((item): item is { id: string; path: string; type: string; active: boolean; muted: boolean } => Boolean(item))
    // Keep the chronological hand-off sparse. All non-sequence evidence is
    // drawn by `sceneEvidencePaths` below with its own visual grammar.
    .slice(0, 6);
});

const sceneEvidencePaths = computed(() => {
  if (props.projection.level === "book") return [];
  const evidenceTypes = new Set(["branch", "promise", "reader-question", "review", "canon", "task", "character"]);
  return props.projection.edges
    .map((edge) => {
      const sourceNode = nodesById.value.get(edge.source);
      const targetNode = nodesById.value.get(edge.target);
      const sourceIsScene = sourceNode?.type === "scene";
      const targetIsScene = targetNode?.type === "scene";
      const evidenceNode = sourceIsScene ? targetNode : targetIsScene ? sourceNode : undefined;
      if (!evidenceNode || !evidenceTypes.has(evidenceNode.type)) return null;
      const source = props.anchors[edge.source];
      const target = props.anchors[edge.target];
      if (!source || !target || !source.visible || !target.visible || source.scale < 0.56 || target.scale < 0.56) return null;
      return {
        id: edge.edge_id,
        path: relationshipPath(source, target, edge.edge_id),
        type: edge.type,
        nodeType: evidenceNode.type,
        ...edgeChapterState(edge),
      };
    })
    .filter((item): item is { id: string; path: string; type: string; nodeType: string; active: boolean; muted: boolean } => Boolean(item))
    // Evidence is not a disposable decoration. Only in-view relationships are
    // rendered, but every such branch, promise, review, canon patch, task or
    // participant keeps its formal connection to the owning scene.
    .sort((left, right) => evidencePriority(left.nodeType, left.type) - evidencePriority(right.nodeType, right.type));
});

const characterPaths = computed(() => characterRelations.value
  .map(({ edge, characterId }) => {
    const source = props.anchors[edge.source];
    const target = props.anchors[edge.target];
    if (!source || !target) return null;
    const chapter = edgeChapterState(edge);
    const characterActive = characterId === props.activeCharacterId;
    return {
      id: edge.edge_id,
      active: characterActive || (!props.activeCharacterId && chapter.active),
      muted: !characterActive && ((Boolean(props.activeCharacterId)) || chapter.muted),
      path: relationshipPath(source, target, edge.edge_id),
      color: threadColor(characterId),
    };
  })
  .filter((item): item is { id: string; active: boolean; muted: boolean; path: string; color: string } => Boolean(item))
  .filter((item) => !props.activeCharacterId || item.active)
  .filter((item) => !activeChapterKey.value || item.active || !item.muted)
  .sort((left, right) => Number(right.active) - Number(left.active))
  .slice(0, props.activeCharacterId || activeChapterKey.value ? undefined : 5));

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

function chapterCentroids(nodes: SpatialNarrativeNode[], anchors: Record<string, Anchor>): SpineCluster[] {
  const scenes = nodes.filter((node) => node.type === "scene").sort((left, right) => left.order - right.order);
  const clusters = new Map<string, SpatialNarrativeNode[]>();
  for (const scene of scenes) {
    const chapterId = String(scene.metrics.chapter_id || scene.parent_id || "");
    // Legacy projects with no chapter metadata retain a scene-by-scene route
    // rather than collapsing their entire manuscript into one artificial dot.
    const key = chapterId || scene.node_id;
    const bucket = clusters.get(key) || [];
    bucket.push(scene);
    clusters.set(key, bucket);
  }
  const centered = [...clusters.values()].map((cluster) => {
    const available = cluster.map((node) => ({ node, anchor: anchors[node.node_id] })).filter((item): item is SpinePoint => Boolean(item.anchor));
    if (!available.length) return null;
    const divisor = available.length;
    const anchor = available.reduce<Anchor>((total, item) => ({
      x: total.x + item.anchor.x / divisor,
      y: total.y + item.anchor.y / divisor,
      scale: total.scale + item.anchor.scale / divisor,
      visible: total.visible || item.anchor.visible,
    }), { x: 0, y: 0, scale: 0, visible: false });
    return { id: String(cluster[0].metrics.chapter_id || cluster[0].parent_id || cluster[0].node_id), node: cluster[0], anchor, members: available };
  }).filter((item): item is SpineCluster => Boolean(item));
  if (centered.length) return centered.sort((left, right) => left.node.order - right.node.order);
  return nodes
    .filter((node) => node.type === "chapter")
    .sort((left, right) => left.order - right.order)
    .map((node) => ({ node, anchor: anchors[node.node_id] }))
    .filter((item): item is SpinePoint => Boolean(item.anchor))
    .map((item) => ({ id: item.node.node_id, node: item.node, anchor: item.anchor, members: [item] }));
}

function chapterKey(value: unknown): string {
  return String(value || "").replace(/^chapter:/, "").trim();
}

function nodeChapterKey(node: SpatialNarrativeNode | undefined, visited = new Set<string>()): string {
  if (!node || visited.has(node.node_id)) return "";
  visited.add(node.node_id);
  if (node.type === "chapter") return chapterKey(node.source_id || node.node_id);
  const declared = chapterKey(node.metrics.chapter_id);
  if (declared) return declared;
  return node.parent_id ? nodeChapterKey(nodesById.value.get(node.parent_id), visited) : "";
}

function edgeChapterState(edge: SpatialNarrativeEdge): { active: boolean; muted: boolean } {
  if (!activeChapterKey.value) return { active: false, muted: false };
  const sourceChapter = nodeChapterKey(nodesById.value.get(edge.source));
  const targetChapter = nodeChapterKey(nodesById.value.get(edge.target));
  // A line is internal only when both resolved narrative endpoints share the
  // focused chapter, or when its non-narrative endpoint is an unscoped asset
  // attached directly to that chapter. Cross-chapter hand-offs stay visible
  // but never impersonate internal evidence.
  const chapters = [sourceChapter, targetChapter].filter(Boolean);
  const active = chapters.length
    ? chapters.every((chapter) => chapter === activeChapterKey.value)
    : false;
  return { active, muted: !active };
}

function chapterState(id: string): { active: boolean; muted: boolean } {
  const active = Boolean(activeChapterKey.value) && chapterKey(id) === activeChapterKey.value;
  return { active, muted: Boolean(activeChapterKey.value) && !active };
}

function chapterCompletion(cluster: SpineCluster): SpatialCompletionState {
  const states = cluster.members.map((member) => member.node.completion_state);
  if (states.includes("active")) return "active";
  if (states.includes("blocked")) return "blocked";
  if (states.length && states.every((state) => state === "completed")) return "completed";
  return cluster.node.completion_state || "planned";
}

function buildPath(points: Anchor[]): string {
  if (!points.length) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  // Chord-length weighted tangents are the practical, centripetal form of a
  // Catmull-Rom spline. They avoid the sharp corners and overshoot of a
  // uniform spline when chapters are deliberately spaced far apart.
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    const tangentA = breathingTangent(points, index);
    const tangentB = breathingTangent(points, index + 1);
    const controlA = { x: start.x + tangentA.x / 3, y: start.y + tangentA.y / 3 };
    const controlB = { x: end.x - tangentB.x / 3, y: end.y - tangentB.y / 3 };
    path += ` C ${controlA.x} ${controlA.y}, ${controlB.x} ${controlB.y}, ${end.x} ${end.y}`;
  }
  return path;
}

function breathingTangent(points: Anchor[], index: number): { x: number; y: number } {
  const tangent = centripetalTangent(points, index);
  // Rotate each shared spline tangent by a small harmonic phase. Adjacent
  // segments reuse the same tangent at their joint, so the curve breathes as
  // one continuous route instead of becoming a decorated zigzag.
  const angle = Math.sin(index * 0.86 + 0.32) * 0.17;
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  return { x: tangent.x * cosine - tangent.y * sine, y: tangent.x * sine + tangent.y * cosine };
}

function centripetalTangent(points: Anchor[], index: number): { x: number; y: number } {
  const current = points[index];
  const previous = points[Math.max(0, index - 1)];
  const next = points[Math.min(points.length - 1, index + 1)];
  if (index === 0) return { x: next.x - current.x, y: next.y - current.y };
  if (index === points.length - 1) return { x: current.x - previous.x, y: current.y - previous.y };
  const previousDistance = Math.max(1, Math.hypot(current.x - previous.x, current.y - previous.y));
  const nextDistance = Math.max(1, Math.hypot(next.x - current.x, next.y - current.y));
  const previousWeight = Math.sqrt(nextDistance) / (Math.sqrt(previousDistance) + Math.sqrt(nextDistance));
  const nextWeight = Math.sqrt(previousDistance) / (Math.sqrt(previousDistance) + Math.sqrt(nextDistance));
  return {
    x: ((current.x - previous.x) / previousDistance * previousWeight + (next.x - current.x) / nextDistance * nextWeight) * (previousDistance + nextDistance) * 0.5,
    y: ((current.y - previous.y) / previousDistance * previousWeight + (next.y - current.y) / nextDistance * nextWeight) * (previousDistance + nextDistance) * 0.5,
  };
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

function evidencePriority(nodeType: string, edgeType: string): number {
  if (nodeType === "branch") return 0;
  if (nodeType === "promise" || nodeType === "reader-question" || edgeType === "raises") return 1;
  if (nodeType === "canon") return 2;
  if (nodeType === "review") return 3;
  if (nodeType === "task") return 4;
  return 5;
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
    <path
      v-for="spoke in chapterSpokes"
      :key="spoke.id"
      class="narrative-chapter-spoke"
      :class="{ active: spoke.active, muted: spoke.muted }"
      :data-completion="spoke.completion"
      :d="`M ${spoke.start.x} ${spoke.start.y} L ${spoke.end.x} ${spoke.end.y}`"
    />
    <path v-if="spinePath" class="narrative-spine-foundation" :class="{ detail: isDetailView, 'chapter-muted': hasChapterFocus }" :d="spinePath" />
    <g v-for="segment in spineSegments" :key="segment.id" class="narrative-spine-segment" :class="{ active: segment.active, muted: segment.muted }" :data-completion="segment.completion">
      <path class="narrative-spine-glow" :class="{ detail: isDetailView }" :d="segment.path" />
      <path class="narrative-spine-track" :class="{ detail: isDetailView }" :d="segment.path" />
      <path class="narrative-spine-signal" :class="{ detail: isDetailView }" :d="segment.path" />
    </g>
    <g v-for="(cluster, index) in spineClusters" :key="cluster.id" class="narrative-chapter-anchor" :class="chapterState(cluster.id)" :data-completion="chapterCompletion(cluster)">
      <circle class="narrative-chapter-anchor-halo" :cx="cluster.anchor.x" :cy="cluster.anchor.y" r="12" />
      <circle class="narrative-chapter-anchor-core" :cx="cluster.anchor.x" :cy="cluster.anchor.y" r="4" />
      <text v-if="cluster.anchor.visible && cluster.anchor.scale >= 0.56" class="narrative-chapter-anchor-label" :x="cluster.anchor.x + 10" :y="cluster.anchor.y - 10">{{ String(index + 1).padStart(2, "0") }}</text>
    </g>
    <path
      v-for="connection in localFlowPaths"
      :key="connection.id"
      class="narrative-local-flow"
      :class="{ active: connection.active, muted: connection.muted }"
      :data-level="projection.level"
      :data-type="connection.type"
      :d="connection.path"
    />
    <path
      v-for="connection in sceneEvidencePaths"
      :key="connection.id"
      class="narrative-evidence-flow"
      :class="{ active: connection.active, muted: connection.muted }"
      :data-type="connection.type"
      :data-node-type="connection.nodeType"
      :d="connection.path"
    />
    <path
      v-for="relation in characterPaths"
      :key="relation.id"
      class="narrative-character-thread"
      :class="{ active: relation.active, muted: relation.muted }"
      :stroke="relation.color"
      :d="relation.path"
    />
  </svg>
</template>
