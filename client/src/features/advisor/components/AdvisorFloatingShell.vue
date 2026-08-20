<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { GripVertical, MessageCircleMore, Minimize2 } from "lucide-vue-next";

const props = defineProps<{
  open: boolean;
  disabled?: boolean;
  unreadCount?: number;
}>();
const emit = defineEmits<{ "update:open": [value: boolean] }>();

const DEFAULT_DOCK_SIZE = { width: 390, height: 680 };
const MIN_DOCK_SIZE = { width: 336, height: 460 };
const dockSide = ref<"left" | "right">((localStorage.getItem("arcvellum.advisorSide") as "left" | "right") || "right");
const orbPosition = ref(readPosition("arcvellum.advisorOrbPosition"));
const dockPosition = ref(readPosition("arcvellum.advisorDockPosition"));
const dockSize = ref(readSize("arcvellum.advisorDockSize"));
const orbStyle = computed(() => orbPosition.value
  ? { left: `${orbPosition.value.left}px`, top: `${orbPosition.value.top}px`, right: "auto", bottom: "auto" }
  : undefined);
const dockStyle = computed(() => {
  const size = currentDockSize();
  return {
    width: `${size.width}px`,
    height: `${size.height}px`,
    ...(dockPosition.value
      ? { left: `${dockPosition.value.left}px`, top: `${dockPosition.value.top}px`, right: "auto", bottom: "auto" }
      : {}),
  };
});
let dragKind: "orb" | "dock" | null = null;
let dragStart = { x: 0, y: 0, left: 0, top: 0 };
let resizeStart = { x: 0, y: 0, width: 0, height: 0 };
let dragged = false;

onMounted(() => {
  window.addEventListener("keydown", globalKeydown);
  window.addEventListener("resize", keepInView);
});
onBeforeUnmount(() => {
  window.removeEventListener("keydown", globalKeydown);
  window.removeEventListener("resize", keepInView);
  stopDrag();
  stopResize();
});

function onOrbClick(): void {
  if (dragged) {
    dragged = false;
    return;
  }
  emit("update:open", !props.open);
}

function startOrbDrag(event: PointerEvent): void {
  if (!canUsePointer(event)) return;
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  beginDrag("orb", event, rect.left, rect.top);
}

function startDockDrag(event: PointerEvent): void {
  if (!canUsePointer(event) || (event.target as HTMLElement).closest("button, select, input, textarea, label")) return;
  const element = (event.currentTarget as HTMLElement).closest(".advisor-dock") as HTMLElement | null;
  if (!element) return;
  const rect = element.getBoundingClientRect();
  beginDrag("dock", event, rect.left, rect.top);
}

function canUsePointer(event: PointerEvent): boolean {
  return event.button === 0 && !window.matchMedia("(max-width: 760px)").matches;
}

function beginDrag(kind: "orb" | "dock", event: PointerEvent, left: number, top: number): void {
  dragKind = kind;
  dragged = false;
  dragStart = { x: event.clientX, y: event.clientY, left, top };
  document.body.classList.add("dragging-advisor");
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", stopDrag, { once: true });
  event.preventDefault();
}

function move(event: PointerEvent): void {
  if (!dragKind) return;
  const dx = event.clientX - dragStart.x;
  const dy = event.clientY - dragStart.y;
  if (Math.abs(dx) + Math.abs(dy) > 5) dragged = true;
  const size = currentDockSize();
  const next = boundedPosition(
    dragStart.left + dx,
    dragStart.top + dy,
    dragKind === "orb" ? 58 : size.width,
    dragKind === "orb" ? 58 : size.height,
  );
  if (dragKind === "orb") orbPosition.value = next;
  else dockPosition.value = next;
}

function stopDrag(): void {
  if (dragKind === "orb" && orbPosition.value) persist("arcvellum.advisorOrbPosition", orbPosition.value);
  if (dragKind === "dock" && dockPosition.value) persist("arcvellum.advisorDockPosition", dockPosition.value);
  dragKind = null;
  document.body.classList.remove("dragging-advisor");
  window.removeEventListener("pointermove", move);
  window.removeEventListener("pointerup", stopDrag);
}

function startResize(event: PointerEvent): void {
  if (!canUsePointer(event)) return;
  const size = currentDockSize();
  resizeStart = { x: event.clientX, y: event.clientY, width: size.width, height: size.height };
  document.body.classList.add("resizing-advisor");
  window.addEventListener("pointermove", resize);
  window.addEventListener("pointerup", stopResize, { once: true });
  event.preventDefault();
  event.stopPropagation();
}

function resize(event: PointerEvent): void {
  dockSize.value = clampSize({
    width: resizeStart.width + event.clientX - resizeStart.x,
    height: resizeStart.height + event.clientY - resizeStart.y,
  });
  if (dockPosition.value) {
    dockPosition.value = boundedPosition(dockPosition.value.left, dockPosition.value.top, dockSize.value.width, dockSize.value.height);
  }
}

function stopResize(): void {
  if (dockSize.value) persist("arcvellum.advisorDockSize", dockSize.value);
  document.body.classList.remove("resizing-advisor");
  window.removeEventListener("pointermove", resize);
  window.removeEventListener("pointerup", stopResize);
}

function keepInView(): void {
  if (window.matchMedia("(max-width: 760px)").matches) return;
  if (orbPosition.value) orbPosition.value = boundedPosition(orbPosition.value.left, orbPosition.value.top, 58, 58);
  dockSize.value = currentDockSize();
  if (dockPosition.value) {
    dockPosition.value = boundedPosition(dockPosition.value.left, dockPosition.value.top, dockSize.value.width, dockSize.value.height);
  }
}

function switchSide(): void {
  dockSide.value = dockSide.value === "right" ? "left" : "right";
  localStorage.setItem("arcvellum.advisorSide", dockSide.value);
  resetPosition();
}

function resetPosition(): void {
  dockPosition.value = null;
  dockSize.value = { ...DEFAULT_DOCK_SIZE };
  localStorage.removeItem("arcvellum.advisorDockPosition");
  localStorage.removeItem("arcvellum.advisorDockSize");
}

function globalKeydown(event: KeyboardEvent): void {
  if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "a") {
    event.preventDefault();
    emit("update:open", !props.open);
  }
}

function currentDockSize(): { width: number; height: number } {
  return clampSize(dockSize.value || DEFAULT_DOCK_SIZE);
}

function clampSize(size: { width: number; height: number }): { width: number; height: number } {
  return {
    width: Math.round(Math.min(Math.max(MIN_DOCK_SIZE.width, size.width), Math.max(MIN_DOCK_SIZE.width, window.innerWidth - 24))),
    height: Math.round(Math.min(Math.max(MIN_DOCK_SIZE.height, size.height), Math.max(MIN_DOCK_SIZE.height, window.innerHeight - 24))),
  };
}

function boundedPosition(left: number, top: number, width: number, height: number): { left: number; top: number } {
  const margin = 10;
  return {
    left: Math.min(Math.max(margin, left), Math.max(margin, window.innerWidth - width - margin)),
    top: Math.min(Math.max(margin, top), Math.max(margin, window.innerHeight - height - margin)),
  };
}

function readPosition(key: string): { left: number; top: number } | null {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "null");
    return value && Number.isFinite(value.left) && Number.isFinite(value.top) ? value : null;
  } catch {
    return null;
  }
}

function readSize(key: string): { width: number; height: number } | null {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "null");
    return value && Number.isFinite(value.width) && Number.isFinite(value.height) ? clampSize(value) : null;
  } catch {
    return null;
  }
}

function persist(key: string, value: unknown): void {
  localStorage.setItem(key, JSON.stringify(value));
}
</script>

<template>
  <button
    class="advisor-orb"
    data-tour-id="advisor"
    :class="{ open }"
    :disabled="disabled"
    :style="orbStyle"
    :title="disabled ? '先选择一部作品' : '打开创作顾问'"
    @pointerdown="startOrbDrag"
    @click="onOrbClick"
  >
    <span class="advisor-orb-rings" aria-hidden="true"></span>
    <MessageCircleMore v-if="!open" :size="23" />
    <Minimize2 v-else :size="21" />
    <span>顾问</span>
    <i v-if="unreadCount" class="advisor-unread">{{ unreadCount > 9 ? '9+' : unreadCount }}</i>
  </button>

  <Transition name="advisor-panel">
    <aside v-if="open" class="advisor-dock" :class="dockSide" :style="dockStyle" aria-label="ArcVellum 创作顾问">
      <header class="advisor-dock-header" title="拖动顾问窗；双击复位" @pointerdown="startDockDrag" @dblclick="resetPosition">
        <span class="advisor-drag-cue"><GripVertical :size="15" /></span>
        <slot name="header" :side="dockSide" :switch-side="switchSide" :close="() => emit('update:open', false)"></slot>
      </header>
      <slot></slot>
      <button class="advisor-dock-resize" title="调整顾问窗口尺寸" aria-label="调整顾问窗口尺寸" @pointerdown="startResize"><i></i></button>
    </aside>
  </Transition>
</template>
