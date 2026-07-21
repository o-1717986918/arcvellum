<script lang="ts">
let highestLayer = 32;
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { ChevronDown, ChevronUp, GripHorizontal, RotateCcw, X } from "lucide-vue-next";
import type { ImmersiveEdge, ImmersivePanel } from "@/types/immersive";

const props = defineProps<{
  panel: ImmersivePanel;
  edge: ImmersiveEdge;
  title: string;
}>();
const emit = defineEmits<{ close: [] }>();

const root = ref<HTMLElement | null>(null);
const position = ref<{ left: number; top: number } | null>(null);
const collapsed = ref(false);
const layer = ref(++highestLayer);
let dragOffset = { x: 0, y: 0 };

const windowStyle = computed(() => ({
  zIndex: layer.value,
  ...(position.value ? {
    left: `${position.value.left}px`,
    top: `${position.value.top}px`,
    right: "auto",
    bottom: "auto",
  } : {}),
}));

function bringForward(): void {
  layer.value = ++highestLayer;
}

function bounded(left: number, top: number): { left: number; top: number } {
  const element = root.value;
  if (!element) return { left, top };
  const width = element.offsetWidth;
  const height = element.offsetHeight;
  const margin = 12;
  return {
    left: Math.min(Math.max(margin, left), Math.max(margin, window.innerWidth - width - margin)),
    top: Math.min(Math.max(margin, top), Math.max(margin, window.innerHeight - height - margin)),
  };
}

function move(event: PointerEvent): void {
  position.value = bounded(event.clientX - dragOffset.x, event.clientY - dragOffset.y);
}

function stopDrag(): void {
  window.removeEventListener("pointermove", move);
  window.removeEventListener("pointerup", stopDrag);
  document.body.classList.remove("dragging-immersive-console");
}

function startDrag(event: PointerEvent): void {
  if (event.button !== 0 || window.matchMedia("(max-width: 760px)").matches) return;
  const element = root.value;
  if (!element || (event.target as HTMLElement).closest("button")) return;
  const rect = element.getBoundingClientRect();
  dragOffset = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  position.value = bounded(rect.left, rect.top);
  bringForward();
  document.body.classList.add("dragging-immersive-console");
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", stopDrag, { once: true });
  event.preventDefault();
}

function reset(): void {
  position.value = null;
}

onBeforeUnmount(stopDrag);
</script>

<template>
  <article
    ref="root"
    class="immersive-console-panel"
    :class="{ collapsed }"
    :data-panel="panel"
    :data-edge="edge"
    :data-dragged="Boolean(position)"
    :style="windowStyle"
    :aria-label="title"
    @pointerdown.capture="bringForward"
  >
    <header class="immersive-console-header">
      <div class="immersive-console-drag" title="拖动仪表；双击复位" @pointerdown="startDrag" @dblclick="reset">
        <GripHorizontal :size="15" />
        <div><span>叙事星仪</span><h2>{{ title }}</h2></div>
      </div>
      <div class="immersive-console-window-actions">
        <button class="orrery-icon" :title="collapsed ? '展开仪表' : '折叠仪表'" @click="collapsed = !collapsed"><ChevronDown v-if="collapsed" :size="15" /><ChevronUp v-else :size="15" /></button>
        <button v-if="position" class="orrery-icon" title="复位仪表" @click="reset"><RotateCcw :size="15" /></button>
        <button class="orrery-icon" title="关闭仪表" @click="emit('close')"><X :size="16" /></button>
      </div>
    </header>
    <div v-show="!collapsed" class="immersive-console-scroll"><slot /></div>
  </article>
</template>
