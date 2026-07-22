<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { NarrativeParallaxRenderer, type StageAnchor } from "@/features/orrery/engine/parallaxRenderer";
import type { SpatialLayout, SpatialNarrativeProjection, WorldPoint } from "@/types/spatial";

const props = defineProps<{
  projection: SpatialNarrativeProjection;
  layout: SpatialLayout;
  selectedNodeId?: string;
}>();
const emit = defineEmits<{ anchors: [value: Record<string, StageAnchor>]; degraded: [] }>();

const host = ref<HTMLElement | null>(null);
let renderer: NarrativeParallaxRenderer | null = null;
let resizeObserver: ResizeObserver | null = null;
let themeObserver: MutationObserver | null = null;
let rendererGeneration = 0;
let observedQuality = "";
const staticProjection = ref(false);
const staticCamera = { x: 0, y: 0, scale: 0.78 };
let staticCameraReady = false;
let staticDrag: { pointerId: number; clientX: number; clientY: number; x: number; y: number } | null = null;

const selectedPoint = computed<WorldPoint | null>(() => props.selectedNodeId ? props.layout.points.get(props.selectedNodeId) || null : null);

async function mountRenderer(): Promise<void> {
  await nextTick();
  const target = host.value;
  if (!target) return;
  const generation = ++rendererGeneration;
  let nextRenderer: NarrativeParallaxRenderer;
  const rendererPromise = NarrativeParallaxRenderer.create(target);
  try {
    nextRenderer = await Promise.race([
      rendererPromise,
      new Promise<never>((_, reject) => window.setTimeout(() => reject(new Error("renderer-init-timeout")), 1600)),
    ]);
  } catch {
    // A spatial workbench must remain legible on remote desktop sessions,
    // old integrated GPUs and headless visual checks. The DOM overlay is the
    // authoritative interaction layer, so it receives a deterministic 2.5D
    // projection instead of disappearing with the WebGL atmosphere.
    staticProjection.value = true;
    renderer?.dispose();
    renderer = null;
    // Pixi may finish creating after the deadline. It is no longer the active
    // renderer, so release it immediately rather than leaving a late canvas
    // above the deterministic DOM projection.
    void rendererPromise.then((lateRenderer) => lateRenderer.dispose()).catch(() => undefined);
    resetStaticCamera();
    emitStaticAnchors();
    emit("degraded");
    return;
  }
  if (generation !== rendererGeneration || target !== host.value) {
    nextRenderer.dispose();
    return;
  }
  staticProjection.value = false;
  renderer?.dispose();
  renderer = nextRenderer;
  renderer.onAnchors((anchors) => emit("anchors", anchors));
    renderer.onContextLost(() => {
    renderer?.dispose();
      renderer = null;
      staticProjection.value = true;
      resetStaticCamera();
      emitStaticAnchors();
    emit("degraded");
  });
  const rect = target.getBoundingClientRect();
  renderer.resize(rect.width, rect.height);
  renderer.update(props.projection, props.layout);
  renderer.showOpeningSegment();
}

onMounted(async () => {
  await mountRenderer();
  if (!host.value) return;
  resizeObserver = new ResizeObserver(() => {
    if (!host.value) return;
    const rect = host.value.getBoundingClientRect();
    if (renderer) renderer.resize(rect.width, rect.height);
    else if (staticProjection.value) emitStaticAnchors();
  });
  resizeObserver.observe(host.value);
  observedQuality = document.documentElement.dataset.arcvellumQuality || "auto";
  themeObserver = new MutationObserver(() => {
    const nextQuality = document.documentElement.dataset.arcvellumQuality || "auto";
    if (nextQuality !== observedQuality) {
      observedQuality = nextQuality;
      void mountRenderer();
      return;
    }
    renderer?.update(props.projection, props.layout);
  });
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-arcvellum-theme", "data-arcvellum-motion", "data-arcvellum-depth", "data-arcvellum-quality"],
  });
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  themeObserver?.disconnect();
  rendererGeneration += 1;
  renderer?.dispose();
  renderer = null;
});

watch(() => [props.projection.revision, props.layout.revision] as const, () => {
  if (renderer) renderer.update(props.projection, props.layout);
  else if (staticProjection.value) {
    resetStaticCamera();
    emitStaticAnchors();
  }
  const motion = document.documentElement.dataset.arcvellumMotion || "full";
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches && motion !== "still") {
    host.value?.animate(
      [{ opacity: 0.52, filter: "saturate(.78) blur(.8px)" }, { opacity: 1, filter: "saturate(1) blur(0)" }],
      { duration: motion === "reduced" ? 170 : 420, easing: "cubic-bezier(.2,.8,.2,1)" },
    );
  }
});

watch(() => [props.projection.spatial_grammar, props.layout.grammar] as const, async () => {
  // A grammar owns a different coordinate vocabulary. Reframe only when the
  // user changes that vocabulary; ordinary live projection refreshes must
  // preserve the camera the reader has already navigated to.
  // Wait for the computed layout to settle first. Without that turn, a fast
  // grammar switch can reframe using the previous coordinate system and leave
  // the new constellation or loop entirely outside the viewport.
  await nextTick();
  openingSegment();
}, { flush: "post" });

function emitStaticAnchors(): void {
  const target = host.value;
  if (!target) return;
  const rect = target.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const nodes = props.projection.nodes;
  if (!nodes.length) {
    emit("anchors", {});
    return;
  }

  const primary = nodes
    .filter((node) => node.type === "chapter" || node.type === "scene")
    .sort((left, right) => left.order - right.order || left.node_id.localeCompare(right.node_id));
  const primaryIndex = new Map(primary.map((node, index) => [node.node_id, index]));
  const anchors: Record<string, StageAnchor> = {};
  const worlds = staticWorldPoints(primary);
  if (!staticCameraReady) initializeStaticCamera(primary, worlds, rect);

  const primaryAnchor = (index: number): StageAnchor => {
    const point = worlds.get(primary[index]?.node_id || "") || { x: index * 118, y: 0 };
    return staticScreenAnchor(point, rect, 1);
  };

  primary.forEach((node, index) => { anchors[node.node_id] = primaryAnchor(index); });

  for (const node of nodes) {
    if (anchors[node.node_id]) continue;
    const parentIndex = primaryIndex.get(node.parent_id || "");
    const fallbackIndex = primary.length ? Math.abs(hashNode(node.node_id)) % primary.length : 0;
    const baseIndex = parentIndex ?? fallbackIndex;
    const parentPoint = worlds.get(primary[baseIndex]?.node_id || "") || { x: baseIndex * 118, y: 0 };
    const side = hashNode(node.node_id) % 2 ? 1 : -1;
    const typeOffset = node.type === "character" ? 164 : node.type === "branch" ? 146 : node.type === "task" || node.type === "review" ? 104 : 126;
    const elevation = node.type === "canon" ? 106 : node.type === "task" || node.type === "review" ? -128 : -96;
    const world = {
      x: parentPoint.x + side * typeOffset + (hashNode(`${node.node_id}:x`) % 31) - 15,
      y: parentPoint.y + elevation + (hashNode(`${node.node_id}:y`) % 29) - 14,
    };
    anchors[node.node_id] = staticScreenAnchor(world, rect, node.type === "task" || node.type === "review" ? 0.82 : 0.9);
  }
  emit("anchors", anchors);
}

function staticWorldPoints(primary: SpatialNarrativeProjection["nodes"]): Map<string, { x: number; y: number }> {
  const worlds = new Map<string, { x: number; y: number }>();
  const first = props.layout.points.get(primary[0]?.node_id || "") || { x: 0, y: 0, z: 0 };
  primary.forEach((node, index) => {
    const point = props.layout.points.get(node.node_id);
    // Use the same rhythm-aware layout as the renderer. The fallback camera is
    // a 2.5D view of the real narrative river, not a second linear timeline.
    // Multipliers translate semantic layout units into a roomy DOM world.
    worlds.set(node.node_id, point
      ? { x: (point.x - first.x) * 164, y: -(point.y - first.y) * 188 }
      : { x: index * 118, y: -index * 5.8 });
  });
  return worlds;
}

function initializeStaticCamera(primary: SpatialNarrativeProjection["nodes"], worlds: Map<string, { x: number; y: number }>, rect: DOMRect): void {
  const currentIndex = primary.findIndex((node) => node.status === "current" || node.status === "blocked");
  const centerIndex = Math.min(primary.length - 1, Math.max(0, currentIndex >= 0 ? currentIndex + 3 : 5));
  const point = worlds.get(primary[centerIndex]?.node_id || "") || { x: 0, y: 0 };
  staticCamera.x = point.x;
  staticCamera.y = point.y;
  staticCamera.scale = Math.min(0.92, Math.max(0.62, (rect.width - 260) / Math.max(760, Math.min(1320, primary.length * 118))));
  staticCameraReady = true;
}

function staticScreenAnchor(point: { x: number; y: number }, rect: DOMRect, depthScale: number): StageAnchor {
  const x = (point.x - staticCamera.x) * staticCamera.scale + rect.width / 2;
  const y = (point.y - staticCamera.y) * staticCamera.scale + rect.height * 0.52;
  return {
    x,
    y,
    visible: x >= -110 && x <= rect.width + 110 && y >= -110 && y <= rect.height + 110,
    scale: Math.max(0.48, Math.min(1.36, staticCamera.scale * depthScale)),
  };
}

function resetStaticCamera(): void {
  staticCameraReady = false;
  staticDrag = null;
}

function hashNode(value: string): number {
  let hash = 2166136261;
  for (const character of value) hash = Math.imul(hash ^ character.charCodeAt(0), 16777619);
  return hash >>> 0;
}
watch(selectedPoint, (point) => {
  if (point) focus(point, props.selectedNodeId || "");
});

function fit(): void {
  if (renderer) {
    renderer.fit();
    return;
  }
  fitStaticCamera();
}

function openingSegment(): void {
  if (renderer) {
    renderer.update(props.projection, props.layout);
    renderer.showOpeningSegment();
    return;
  }
  if (staticProjection.value) {
    resetStaticCamera();
    emitStaticAnchors();
  }
}

function focus(point: WorldPoint, nodeId = ""): void {
  if (renderer) {
    renderer.focus(point, 0.8, nodeId);
    return;
  }
  focusStaticNode(nodeId);
}

function fitStaticCamera(): void {
  const target = host.value;
  if (!target) return;
  const rect = target.getBoundingClientRect();
  const primary = props.projection.nodes.filter((node) => node.type === "chapter" || node.type === "scene").sort((left, right) => left.order - right.order || left.node_id.localeCompare(right.node_id));
  const worlds = staticWorldPoints(primary);
  const points = [...worlds.values()];
  if (!points.length) return;
  const minX = Math.min(...points.map((point) => point.x));
  const maxX = Math.max(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  const maxY = Math.max(...points.map((point) => point.y));
  staticCamera.x = (minX + maxX) / 2;
  staticCamera.y = (minY + maxY) / 2;
  staticCamera.scale = Math.max(0.08, Math.min(0.9, Math.min((rect.width - 260) / Math.max(420, maxX - minX + 240), (rect.height - 260) / Math.max(360, maxY - minY + 200))));
  staticCameraReady = true;
  emitStaticAnchors();
}

function focusStaticNode(nodeId: string): void {
  const target = host.value;
  if (!target || !nodeId) return;
  const primary = props.projection.nodes.filter((node) => node.type === "chapter" || node.type === "scene").sort((left, right) => left.order - right.order || left.node_id.localeCompare(right.node_id));
  const worlds = staticWorldPoints(primary);
  const point = worlds.get(nodeId);
  if (!point) return;
  staticCamera.x = point.x;
  staticCamera.y = point.y;
  staticCamera.scale = Math.max(0.72, staticCamera.scale);
  staticCameraReady = true;
  emitStaticAnchors();
}

function startStaticDrag(event: PointerEvent): void {
  if (!staticProjection.value || !host.value) return;
  host.value.setPointerCapture(event.pointerId);
  staticDrag = { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, x: staticCamera.x, y: staticCamera.y };
}

function moveStaticDrag(event: PointerEvent): void {
  if (!staticDrag || staticDrag.pointerId !== event.pointerId) return;
  staticCamera.x = staticDrag.x - (event.clientX - staticDrag.clientX) / staticCamera.scale;
  staticCamera.y = staticDrag.y - (event.clientY - staticDrag.clientY) / staticCamera.scale;
  emitStaticAnchors();
}

function stopStaticDrag(event: PointerEvent): void {
  if (!staticDrag || staticDrag.pointerId !== event.pointerId) return;
  staticDrag = null;
  host.value?.releasePointerCapture(event.pointerId);
}

function zoomStatic(event: WheelEvent): void {
  if (!staticProjection.value || !host.value) return;
  const rect = host.value.getBoundingClientRect();
  const localX = event.clientX - rect.left - rect.width / 2;
  const localY = event.clientY - rect.top - rect.height * 0.52;
  const worldX = staticCamera.x + localX / staticCamera.scale;
  const worldY = staticCamera.y + localY / staticCamera.scale;
  const factor = Math.exp(-event.deltaY * 0.0014);
  staticCamera.scale = Math.max(0.08, Math.min(1.7, staticCamera.scale * factor));
  staticCamera.x = worldX - localX / staticCamera.scale;
  staticCamera.y = worldY - localY / staticCamera.scale;
  emitStaticAnchors();
}

defineExpose({ fit, focus, openingSegment });
</script>

<template>
  <div ref="host" class="narrative-parallax-stage" aria-hidden="true" @pointerdown="startStaticDrag" @pointermove="moveStaticDrag" @pointerup="stopStaticDrag" @pointercancel="stopStaticDrag" @wheel.prevent="zoomStatic"></div>
</template>
