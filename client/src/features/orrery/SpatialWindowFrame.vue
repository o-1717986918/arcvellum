<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ChevronDown, ChevronUp, GripHorizontal, LocateFixed, PinOff, RotateCcw, X } from "lucide-vue-next";
import type { SpatialWindow, SpatialWindowPosition, SpatialWindowSize } from "@/types/spatialWindows";

const props = defineProps<{ item: SpatialWindow }>();
const emit = defineEmits<{ move: [position: SpatialWindowPosition]; resize: [size: SpatialWindowSize]; close: []; toggle: []; reset: []; activate: [] }>();

const root = ref<HTMLElement | null>(null);
const compactViewport = ref(false);
let dragOffset = { x: 0, y: 0 };
let resizeOrigin = { x: 0, y: 0, width: 0, height: 0 };
const style = computed(() => {
  if (compactViewport.value) {
    const maxHeight = props.item.kind === "reader" ? "min(72dvh, 620px)" : `min(58dvh, ${props.item.size.height}px)`;
    return {
      left: "12px",
      right: "12px",
      top: "auto",
      bottom: "72px",
      width: "auto",
      height: props.item.collapsed ? "auto" : maxHeight,
      zIndex: props.item.layer,
    };
  }
  return {
    left: `${props.item.position.left}px`,
    top: `${props.item.position.top}px`,
    width: `${props.item.size.width}px`,
    height: props.item.collapsed ? "auto" : `${props.item.size.height}px`,
    zIndex: props.item.layer,
  };
});

function bounded(left: number, top: number): SpatialWindowPosition {
  const width = props.item.size.width;
  const height = props.item.collapsed ? 48 : props.item.size.height;
  const margin = 12;
  return {
    left: Math.min(Math.max(margin, left), Math.max(margin, window.innerWidth - width - margin)),
    top: Math.min(Math.max(margin, top), Math.max(margin, window.innerHeight - height - margin)),
  };
}

function move(event: PointerEvent): void {
  emit("move", bounded(event.clientX - dragOffset.x, event.clientY - dragOffset.y));
}

function stopDrag(): void {
  window.removeEventListener("pointermove", move);
  window.removeEventListener("pointerup", stopDrag);
  document.body.classList.remove("dragging-spatial-window");
}

function startDrag(event: PointerEvent): void {
  if (event.button !== 0 || compactViewport.value) return;
  if ((event.target as HTMLElement).closest(".spatial-window-actions")) return;
  const rect = root.value?.getBoundingClientRect();
  if (!rect) return;
  dragOffset = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  emit("activate");
  document.body.classList.add("dragging-spatial-window");
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", stopDrag, { once: true });
  event.preventDefault();
}

function resize(event: PointerEvent): void {
  emit("resize", {
    width: resizeOrigin.width + event.clientX - resizeOrigin.x,
    height: resizeOrigin.height + event.clientY - resizeOrigin.y,
  });
}

function stopResize(): void {
  window.removeEventListener("pointermove", resize);
  window.removeEventListener("pointerup", stopResize);
  document.body.classList.remove("resizing-spatial-window");
}

function startResize(event: PointerEvent): void {
  if (event.button !== 0 || compactViewport.value || props.item.collapsed) return;
  resizeOrigin = { x: event.clientX, y: event.clientY, width: props.item.size.width, height: props.item.size.height };
  emit("activate");
  document.body.classList.add("resizing-spatial-window");
  window.addEventListener("pointermove", resize);
  window.addEventListener("pointerup", stopResize, { once: true });
  event.preventDefault();
  event.stopPropagation();
}

function windowKicker(): string {
  const labels: Record<SpatialWindow["kind"], string> = {
    node: "NARRATIVE SIGNAL",
    progress: "LIVE EXECUTION",
    reader: "READING ROOM",
    decisions: "CHOICE GATE",
    rules: "WRITING CONSTITUTION",
    health: "ROUTE HEALTH",
    delivery: "RELEASE PROOF",
  };
  return labels[props.item.kind];
}

function syncViewport(): void {
  compactViewport.value = window.matchMedia("(max-width: 760px)").matches;
}

onMounted(() => {
  syncViewport();
  window.addEventListener("resize", syncViewport);
});
onBeforeUnmount(() => {
  stopDrag();
  stopResize();
  window.removeEventListener("resize", syncViewport);
});
</script>

<template>
  <article ref="root" class="spatial-window" :class="{ collapsed: item.collapsed, compact: compactViewport }" :data-kind="item.kind" :data-spatial-window-id="item.id" :style="style" tabindex="-1" @pointerdown.capture="emit('activate')">
    <header class="spatial-window-header">
      <button class="spatial-window-drag" title="拖动窗口；双击复位" @pointerdown="startDrag" @dblclick="emit('reset')">
        <GripHorizontal :size="15" />
        <span><small>{{ windowKicker() }}</small><strong>{{ item.title }}</strong></span>
      </button>
      <div class="spatial-window-actions">
        <span v-if="item.anchor?.enabled" class="spatial-window-anchor" title="正跟随节点"><LocateFixed :size="13" /></span>
        <span v-else-if="item.anchor" class="spatial-window-anchor free" title="窗口已脱离节点"><PinOff :size="13" /></span>
        <button class="orrery-v3-icon" :title="item.collapsed ? '展开窗口' : '折叠窗口'" @click="emit('toggle')"><ChevronDown v-if="item.collapsed" :size="15" /><ChevronUp v-else :size="15" /></button>
        <button class="orrery-v3-icon" :title="item.anchor ? '回到节点旁' : '复位窗口'" @click="emit('reset')"><RotateCcw :size="14" /></button>
        <button class="orrery-v3-icon" title="关闭窗口" @click="emit('close')"><X :size="16" /></button>
      </div>
    </header>
    <div v-show="!item.collapsed" class="spatial-window-scroll"><slot /></div>
    <button v-if="!compactViewport && !item.collapsed" class="spatial-window-resize" title="调整窗口尺寸" aria-label="调整窗口尺寸" @pointerdown="startResize"><i></i></button>
  </article>
</template>
