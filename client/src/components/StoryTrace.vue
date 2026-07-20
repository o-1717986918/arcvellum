<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { GitBranch, List, Network, ScanSearch, X } from "lucide-vue-next";
import { useRouter } from "vue-router";
import { api, connectEventStream, query, type EventStreamConnection } from "@/services/api";
import { asList } from "@/services/presentation";
import { useAppStore } from "@/stores/app";
import type { NarrativeEdge, NarrativeNode, NarrativeProjection } from "@/types/api";

const props = defineProps<{ dashboard: Record<string, unknown> | null }>();
const store = useAppStore();
const router = useRouter();
const level = ref<"book" | "chapter" | "scene">("book");
const focus = ref("");
const projection = ref<NarrativeProjection | null>(null);
const selected = ref<NarrativeNode | null>(null);
const listMode = ref(false);
const loading = ref(false);
let stream: EventStreamConnection | null = null;

const sceneOptions = computed(() =>
  asList<Record<string, unknown>>(store.library?.sections && (store.library.sections as Record<string, unknown>).scenes),
);
const chapterOptions = computed(() =>
  [...new Set(sceneOptions.value.map((item) => String(item.subtitle || "")).filter(Boolean))],
);
const nodes = computed(() => projection.value?.nodes || []);
const edges = computed(() => projection.value?.edges || []);
const sequenceNodes = computed(() => nodes.value.filter((node) => ["chapter", "scene"].includes(node.type)).sort((a, b) => a.order - b.order));
const graphWidth = computed(() => Math.max(900, sequenceNodes.value.length * 150 + 120));
const positions = computed(() => layoutNodes(nodes.value, edges.value));
const selectedGrowth = computed(() => {
  const target = Number(selected.value?.metrics.word_target || 0);
  const actual = Number(selected.value?.metrics.formal_chars || 0);
  return { target, actual, width: target ? Math.min(100, actual / target * 100) : 0 };
});

watch([level, focus, () => store.currentProjectPath], () => void connectProjection(), { flush: "post" });
onMounted(() => void connectProjection());
onBeforeUnmount(() => stream?.close());

async function connectProjection(): Promise<void> {
  stream?.close();
  stream = null;
  selected.value = null;
  if (!store.currentProjectPath) return;
  loading.value = true;
  const path = query({ project_root: store.currentProjectPath, level: level.value, focus: focus.value });
  try {
    projection.value = await api<NarrativeProjection>(`/narrative/projection?${path}`);
    if (!focus.value && projection.value.focus && level.value !== "book") focus.value = projection.value.focus;
  } finally {
    loading.value = false;
  }
  stream = connectEventStream(`/narrative/stream?${path}&interval_seconds=6`, (event, data) => {
    if (event === "narrative.projection") projection.value = data as unknown as NarrativeProjection;
  });
}

function changeLevel(value: "book" | "chapter" | "scene"): void {
  level.value = value;
  focus.value = "";
}

function position(nodeId: string): { x: number; y: number } {
  return positions.value.get(nodeId) || { x: 60, y: 180 };
}

function edgePath(edge: NarrativeEdge): string {
  const start = position(edge.source);
  const end = position(edge.target);
  const sx = start.x + 58;
  const sy = start.y + 28;
  const ex = end.x + 58;
  const ey = end.y + 28;
  return `M ${sx} ${sy} C ${(sx + ex) / 2} ${sy}, ${(sx + ex) / 2} ${ey}, ${ex} ${ey}`;
}

async function openNode(node: NarrativeNode): Promise<void> {
  selected.value = node;
  if (node.type === "chapter") {
    level.value = "chapter";
    focus.value = node.source_id;
  } else if (node.type === "scene") {
    level.value = "scene";
    focus.value = node.source_id.includes("/") ? node.node_id.replace("scene:", "") : node.source_id.replace(/^.*[\\/]/, "").replace(/\.yaml$/, "");
  }
}

function navigateToSource(node: NarrativeNode): void {
  if (node.navigate === "library") void router.push("/library");
  else if (node.status === "formal") void router.push("/reader");
}

function nodeTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    chapter: "章节", scene: "场景", character: "人物", branch: "分支", review: "审查",
    canon: "世界设定", promise: "叙事承诺", "reader-question": "读者问题", task: "当前任务",
  };
  return labels[value] || "叙事节点";
}

function statusLabel(value: string): string {
  const labels: Record<string, string> = {
    planned: "规划中", queued: "待推进", current: "正在推进", formal: "已正式", memory: "已登记",
    blocked: "待处理", alternative: "备选",
  };
  return labels[value] || "已记录";
}

function sourceLabel(value: string): string {
  const labels: Record<string, string> = {
    "scene-catalog": "场景规划", scene: "场景资料", character: "人物档案", branch: "分支推演",
    review: "审查记录", "canon-patch": "设定写回", "workflow-action": "创作状态机",
  };
  return labels[value] || "作品事实";
}

function layoutNodes(items: NarrativeNode[], graphEdges: NarrativeEdge[]): Map<string, { x: number; y: number }> {
  const result = new Map<string, { x: number; y: number }>();
  const primary = items.filter((item) => ["chapter", "scene"].includes(item.type)).sort((a, b) => a.order - b.order);
  primary.forEach((item, index) => result.set(item.node_id, { x: 44 + index * 150, y: 155 }));
  const characters = items.filter((item) => item.type === "character");
  characters.forEach((item, index) => result.set(item.node_id, { x: 60 + index * 138, y: 292 }));
  const satellites = items.filter((item) => !["chapter", "scene", "character"].includes(item.type));
  satellites.forEach((item, index) => {
    const link = graphEdges.find((edge) => edge.target === item.node_id || edge.source === item.node_id);
    const anchorId = link?.source === item.node_id ? link.target : link?.source;
    const anchor = anchorId ? result.get(anchorId) : undefined;
    result.set(item.node_id, {
      x: Math.max(12, (anchor?.x || 70 + index * 130) + ((index % 3) - 1) * 45),
      y: item.type === "reader-question" || item.type === "branch" ? 40 + (index % 2) * 55 : 285,
    });
  });
  return result;
}
</script>

<template>
  <section class="story-trace narrative-observatory" aria-label="叙事观测仪">
    <header>
      <div><span class="eyebrow">Narrative Observatory</span><h2>故事正在怎样生长</h2></div>
      <div class="observatory-tools">
        <span class="live-pill"><i></i>实时投影</span>
        <button class="icon-button" :title="listMode ? '查看脉络图' : '使用列表视图'" @click="listMode = !listMode">
          <Network v-if="listMode" :size="16" /><List v-else :size="16" />
        </button>
      </div>
    </header>

    <div class="observatory-controls">
      <div class="level-switch" role="tablist">
        <button :class="{ active: level === 'book' }" @click="changeLevel('book')">全书</button>
        <button :class="{ active: level === 'chapter' }" @click="changeLevel('chapter')">章节</button>
        <button :class="{ active: level === 'scene' }" @click="changeLevel('scene')">当前场景</button>
      </div>
      <select v-if="level === 'chapter'" v-model="focus" aria-label="选择章节">
        <option value="">当前章节</option><option v-for="chapter in chapterOptions" :key="chapter" :value="chapter">{{ chapter }}</option>
      </select>
      <select v-if="level === 'scene'" v-model="focus" aria-label="选择场景">
        <option value="">当前场景</option><option v-for="scene in sceneOptions" :key="String(scene.id)" :value="scene.id">{{ scene.title }}</option>
      </select>
      <span v-if="projection" class="observatory-summary">{{ projection.accessibility_summary }}</span>
    </div>

    <div v-if="loading && !projection" class="trace-empty"><span class="trace-seed"></span><div><strong>正在建立叙事投影</strong><p>只读取已有的正式项目证据。</p></div></div>

    <div v-else-if="listMode" class="observatory-list" role="list">
      <button v-for="node in nodes" :key="node.node_id" :data-status="node.status" @click="selected = node">
        <span class="observatory-node-dot"></span><span><strong>{{ node.label }}</strong><small>{{ node.subtitle || nodeTypeLabel(node.type) }}</small></span><span>{{ nodeTypeLabel(node.type) }}</span>
      </button>
    </div>

    <div v-else-if="nodes.length" class="observatory-canvas" tabindex="0">
      <svg :viewBox="`0 0 ${graphWidth} 390`" :style="{ minWidth: `${graphWidth}px` }" role="img" :aria-label="projection?.accessibility_summary">
        <defs><marker id="trace-arrow" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 z" /></marker></defs>
        <g class="observatory-edges">
          <path v-for="edge in edges" :key="edge.edge_id" :d="edgePath(edge)" :data-type="edge.type"><title>{{ edge.label }}</title></path>
        </g>
        <g
          v-for="node in nodes"
          :key="node.node_id"
          class="observatory-node"
          :class="[{ selected: selected?.node_id === node.node_id }, `node-${node.type}`]"
          :data-status="node.status"
          :transform="`translate(${position(node.node_id).x}, ${position(node.node_id).y})`"
          tabindex="0"
          role="button"
          @click="openNode(node)"
          @keydown.enter="openNode(node)"
        >
          <rect width="116" height="58" rx="5" />
          <circle cx="12" cy="13" r="4" />
          <text x="22" y="16" class="node-kind">{{ nodeTypeLabel(node.type) }}</text>
          <text x="10" y="36" class="node-label">{{ node.label.slice(0, 12) }}</text>
          <text x="10" y="50" class="node-subtitle">{{ node.subtitle.slice(0, 18) }}</text>
        </g>
      </svg>
    </div>

    <div v-else class="trace-empty"><span class="trace-seed"></span><div><strong>还没有可投影的正式脉络</strong><p>场景、人物或正文形成后，节点会从真实项目证据中出现。</p></div></div>

    <aside v-if="selected" class="observatory-inspector">
      <header><div><span>{{ nodeTypeLabel(selected.type) }}</span><strong>{{ selected.label }}</strong></div><button class="icon-button" @click="selected = null"><X :size="15" /></button></header>
      <p>{{ selected.subtitle || '这个节点来自正式项目资料。' }}</p>
      <dl><div><dt>状态</dt><dd>{{ statusLabel(selected.status) }}</dd></div><div v-if="selected.metrics.word_target"><dt>字数目标</dt><dd>{{ selected.metrics.word_target }}</dd></div><div v-if="selected.metrics.formal_chars"><dt>正式正文</dt><dd>{{ selected.metrics.formal_chars }}</dd></div><div><dt>事实来源</dt><dd>{{ sourceLabel(selected.source_type) }}</dd></div></dl>
      <div v-if="selectedGrowth.target" class="observatory-scroll-growth" aria-label="章节正文长卷累积">
        <span :style="{ width: `${selectedGrowth.width}%` }"></span>
        <small>正文长卷 {{ selectedGrowth.actual.toLocaleString() }} / {{ selectedGrowth.target.toLocaleString() }} 字</small>
      </div>
      <button class="observatory-source" @click="navigateToSource(selected)"><ScanSearch :size="15" />查看对应作品资料</button>
    </aside>

    <footer v-if="projection">
      <span><GitBranch :size="13" />{{ projection.summary.node_count }} 个节点 · {{ projection.summary.edge_count }} 条关系</span>
      <p>颜色表示真实状态；图形本身不会修改作品。</p>
    </footer>
  </section>
</template>
