<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { Bookmark, BookmarkPlus, Flame, Pause, Play, ScanSearch, Trash2, X } from "lucide-vue-next";
import {
  heatLabel,
  narrativePath,
  nodesInScreenRect,
  viewBookmarkMeta,
  type OrreryHeatLens,
  type ScreenRect,
} from "@/features/orrery/model/exploration";
import type { OrreryViewBookmark } from "@/stores/orreryExploration";
import type { SpatialNarrativeNode } from "@/types/spatial";

const props = defineProps<{
  nodes: SpatialNarrativeNode[];
  anchors: Record<string, { x: number; y: number; visible: boolean; scale: number }>;
  level: string;
  heatLens: OrreryHeatLens;
  comparedNodeIds: string[];
  bookmarks: OrreryViewBookmark[];
}>();
const emit = defineEmits<{
  heatLens: [lens: OrreryHeatLens];
  compare: [nodeIds: string[]];
  replay: [node: SpatialNarrativeNode];
  saveBookmark: [];
  restoreBookmark: [bookmark: OrreryViewBookmark];
  removeBookmark: [id: string];
}>();

const root = ref<HTMLElement | null>(null);
const lassoActive = ref(false);
const bookmarkOpen = ref(false);
const replaying = ref(false);
const replayIndex = ref(0);
const drag = ref<{ pointerId: number; startX: number; startY: number; currentX: number; currentY: number } | null>(null);
let replayTimer = 0;

const route = computed(() => narrativePath(props.nodes, props.level));
const lassoStyle = computed(() => {
  if (!drag.value) return {};
  const left = Math.min(drag.value.startX, drag.value.currentX);
  const top = Math.min(drag.value.startY, drag.value.currentY);
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${Math.abs(drag.value.currentX - drag.value.startX)}px`,
    height: `${Math.abs(drag.value.currentY - drag.value.startY)}px`,
  };
});
const compared = computed(() => props.comparedNodeIds
  .map((id) => props.nodes.find((node) => node.node_id === id))
  .filter((node): node is SpatialNarrativeNode => Boolean(node)));

onBeforeUnmount(stopReplay);

function setLens(event: Event): void {
  emit("heatLens", (event.target as HTMLSelectElement).value as OrreryHeatLens);
}

function toggleLasso(): void {
  lassoActive.value = !lassoActive.value;
  if (!lassoActive.value) drag.value = null;
}

function startLasso(event: PointerEvent): void {
  if (!lassoActive.value || !root.value || event.button !== 0) return;
  const rect = root.value.getBoundingClientRect();
  drag.value = {
    pointerId: event.pointerId,
    startX: event.clientX - rect.left,
    startY: event.clientY - rect.top,
    currentX: event.clientX - rect.left,
    currentY: event.clientY - rect.top,
  };
  root.value.setPointerCapture(event.pointerId);
}

function moveLasso(event: PointerEvent): void {
  if (!drag.value || drag.value.pointerId !== event.pointerId || !root.value) return;
  const rect = root.value.getBoundingClientRect();
  drag.value.currentX = event.clientX - rect.left;
  drag.value.currentY = event.clientY - rect.top;
}

function finishLasso(event: PointerEvent): void {
  if (!drag.value || drag.value.pointerId !== event.pointerId) return;
  const area: ScreenRect = {
    left: drag.value.startX,
    top: drag.value.startY,
    right: drag.value.currentX,
    bottom: drag.value.currentY,
  };
  const wideEnough = Math.abs(area.right - area.left) > 8 && Math.abs(area.bottom - area.top) > 8;
  emit("compare", wideEnough ? nodesInScreenRect(props.nodes, props.anchors, area).map((node) => node.node_id) : []);
  drag.value = null;
  lassoActive.value = false;
  root.value?.releasePointerCapture(event.pointerId);
}

function toggleReplay(): void {
  if (replaying.value) {
    stopReplay();
    return;
  }
  if (!route.value.length) return;
  replaying.value = true;
  replayIndex.value = 0;
  emitReplayNode();
  replayTimer = window.setInterval(() => {
    replayIndex.value += 1;
    if (replayIndex.value >= route.value.length) {
      stopReplay();
      return;
    }
    emitReplayNode();
  }, 1050);
}

function emitReplayNode(): void {
  const node = route.value[replayIndex.value];
  if (node) emit("replay", node);
}

function stopReplay(): void {
  replaying.value = false;
  if (replayTimer) window.clearInterval(replayTimer);
  replayTimer = 0;
}

function describe(node: SpatialNarrativeNode): string {
  const labels: Record<string, string> = {
    chapter: "章节", scene: "场景", character: "人物", branch: "分支",
    review: "审查", promise: "承诺", "reader-question": "问题", canon: "设定", task: "任务",
  };
  return `${labels[node.type] || "资料"} · ${node.status}`;
}
</script>

<template>
  <div
    ref="root"
    class="orrery-exploration-layer"
    :class="{ selecting: lassoActive }"
    @pointerdown="startLasso"
    @pointermove="moveLasso"
    @pointerup="finishLasso"
    @pointercancel="finishLasso"
  >
    <div class="orrery-exploration-tools">
      <button :class="{ active: lassoActive }" title="框选节点进行并列观察" @click.stop="toggleLasso">
        <ScanSearch :size="14" />
      </button>
      <button :class="{ active: replaying }" title="沿当前叙事粒度回放路径" @click.stop="toggleReplay">
        <Pause v-if="replaying" :size="14" /><Play v-else :size="14" />
      </button>
      <label title="切换只读创作信号热力层" @pointerdown.stop>
        <Flame :size="14" />
        <select :value="heatLens" aria-label="叙事信号热力层" @change="setLens">
          <option value="">信号</option>
          <option value="rhythm">呼吸</option>
          <option value="tension">张力</option>
          <option value="promise">承诺</option>
          <option value="review">审查</option>
        </select>
      </label>
      <button :class="{ active: bookmarkOpen }" title="查看视图书签" @click.stop="bookmarkOpen = !bookmarkOpen">
        <Bookmark :size="14" />
      </button>
    </div>

    <div v-if="drag" class="orrery-lasso-rectangle" :style="lassoStyle"></div>

    <aside v-if="heatLens" class="orrery-heat-legend">
      <Flame :size="12" /><span>{{ heatLabel(heatLens) }}</span><i></i><small>弱</small><b></b><small>强</small>
    </aside>

    <aside v-if="bookmarkOpen" class="orrery-bookmark-panel" @pointerdown.stop>
      <header><span>视图书签</span><button title="保存当前观察状态" @click="emit('saveBookmark')"><BookmarkPlus :size="13" /></button></header>
      <button v-for="item in bookmarks" :key="item.id" class="orrery-bookmark-row" @click="emit('restoreBookmark', item)">
        <span><strong>{{ item.label }}</strong><small>{{ viewBookmarkMeta(item.level, item.grammar) }}</small></span>
        <i title="删除书签" @click.stop="emit('removeBookmark', item.id)"><Trash2 :size="11" /></i>
      </button>
      <p v-if="!bookmarks.length">保存当前焦点、构型、时点和信号镜头。</p>
    </aside>

    <aside v-if="compared.length" class="orrery-comparison-tray" @pointerdown.stop>
      <header><span>并列观察 · {{ compared.length }}</span><button title="清除框选" @click="emit('compare', [])"><X :size="12" /></button></header>
      <div>
        <article v-for="node in compared" :key="node.node_id">
          <strong>{{ node.label }}</strong><small>{{ describe(node) }}</small><p>{{ node.subtitle || "暂无补充说明" }}</p>
        </article>
      </div>
    </aside>
  </div>
</template>
