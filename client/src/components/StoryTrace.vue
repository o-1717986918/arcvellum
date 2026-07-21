<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { BookOpenText, ChevronRight, Focus, Layers3, List, Minus, Network, Plus, ScanSearch, X } from "lucide-vue-next";
import { api, connectEventStream, query, type EventStreamConnection } from "@/services/api";
import { asList } from "@/services/presentation";
import { useAppStore } from "@/stores/app";
import type { NarrativeEdge, NarrativeNode, NarrativeProjection } from "@/types/api";

defineProps<{ dashboard: Record<string, unknown> | null; immersive?: boolean }>();
const emit = defineEmits<{ inspectTask: [] }>();
const store = useAppStore();
const router = useRouter();
const level = ref<"book" | "chapter" | "scene">("book");
const focus = ref("");
const projection = ref<NarrativeProjection | null>(null);
const selected = ref<NarrativeNode | null>(null);
const listMode = ref(false);
const loading = ref(false);
const zoom = ref(1);
const recentMotion = ref(new Set<string>());
let stream: EventStreamConnection | null = null;
let motionTimer = 0;

const sceneOptions = computed(() =>
  asList<Record<string, unknown>>(store.library?.sections && (store.library.sections as Record<string, unknown>).scenes),
);
const chapterOptions = computed(() =>
  [...new Set(sceneOptions.value.map((item) => String(item.subtitle || "")).filter(Boolean))],
);
const nodes = computed(() => projection.value?.nodes || []);
const edges = computed(() => projection.value?.edges || []);
const primaryNodes = computed(() => nodes.value.filter((node) => ["chapter", "scene"].includes(node.type)).sort((a, b) => a.order - b.order));
const taskNode = computed(() => nodes.value.find((node) => node.type === "task"));
const formalChars = computed(() => Number(projection.value?.summary.formal_prose_chars || 0));
const positions = computed(() => layoutNodes(nodes.value, edges.value));
const manuscriptPath = computed(() => {
  const items = primaryNodes.value;
  if (!items.length) return "";
  return items.map((node, index) => {
    const point = position(node.node_id);
    return `${index ? "L" : "M"} ${point.x} ${point.y}`;
  }).join(" ");
});
const selectedGrowth = computed(() => {
  const target = Number(selected.value?.metrics.word_target || 0);
  const actual = Number(selected.value?.metrics.formal_chars || 0);
  return { target, actual, width: target ? Math.min(100, actual / target * 100) : 0 };
});

watch([level, focus, () => store.currentProjectPath], () => void connectProjection(), { flush: "post" });
onMounted(() => void connectProjection());
onBeforeUnmount(() => {
  stream?.close();
  window.clearTimeout(motionTimer);
});

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
  stream = connectEventStream(`/narrative/stream?${path}&interval_seconds=2`, (event, data) => {
    if (event !== "narrative.projection") return;
    const next = data as unknown as NarrativeProjection;
    projection.value = next;
    recentMotion.value = new Set(next.motion_events.map((item) => item.node_id));
    window.clearTimeout(motionTimer);
    motionTimer = window.setTimeout(() => (recentMotion.value = new Set()), 2400);
  });
}

function changeLevel(value: "book" | "chapter" | "scene"): void {
  level.value = value;
  focus.value = "";
  zoom.value = 1;
}

function position(nodeId: string): { x: number; y: number } {
  return positions.value.get(nodeId) || { x: 700, y: 360 };
}

function edgePath(edge: NarrativeEdge): string {
  const start = position(edge.source);
  const end = position(edge.target);
  const curve = Math.max(40, Math.abs(end.x - start.x) * 0.34);
  return `M ${start.x} ${start.y} C ${start.x + curve} ${start.y}, ${end.x - curve} ${end.y}, ${end.x} ${end.y}`;
}

function openNode(node: NarrativeNode): void {
  selected.value = node;
}

function drillInto(node: NarrativeNode): void {
  if (node.type === "chapter") {
    level.value = "chapter";
    focus.value = node.source_id;
  } else if (node.type === "scene") {
    level.value = "scene";
    focus.value = node.node_id.replace("scene:", "");
  }
}

function navigateToSource(node: NarrativeNode): void {
  if (node.type === "task") emit("inspectTask");
  else if (node.navigate === "library") void router.push("/library");
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
    planned: "规划中", queued: "等待推进", current: "正在推进", formal: "已进入正文", memory: "已记入作品",
    blocked: "需要处理", alternative: "备选方向",
  };
  return labels[value] || "已记录";
}

function layoutNodes(items: NarrativeNode[], graphEdges: NarrativeEdge[]): Map<string, { x: number; y: number }> {
  const result = new Map<string, { x: number; y: number }>();
  const primary = items.filter((item) => ["chapter", "scene"].includes(item.type)).sort((a, b) => a.order - b.order);
  const count = Math.max(1, primary.length);
  primary.forEach((item, index) => {
    const ratio = count === 1 ? 0.5 : index / (count - 1);
    result.set(item.node_id, { x: 150 + ratio * 1100, y: 350 + Math.sin(ratio * Math.PI * 2.2) * 76 });
  });
  const satellites = items.filter((item) => !["chapter", "scene"].includes(item.type));
  satellites.forEach((item, index) => {
    const link = graphEdges.find((edge) => edge.target === item.node_id || edge.source === item.node_id);
    const anchorId = link?.source === item.node_id ? link.target : link?.source;
    const anchor = anchorId ? result.get(anchorId) : undefined;
    const angle = ((index * 137.5) % 360) * Math.PI / 180;
    const radius = item.type === "task" ? (items.length <= 3 ? 230 : 150) : 104 + (index % 3) * 22;
    result.set(item.node_id, {
      x: Math.max(70, Math.min(1330, (anchor?.x || 700) + Math.cos(angle) * radius)),
      y: Math.max(88, Math.min(612, (anchor?.y || 350) + Math.sin(angle) * radius)),
    });
  });
  return result;
}
</script>

<template>
  <section class="narrative-orrery" :class="{ immersive }" aria-label="叙事星仪">
    <header class="orrery-heading">
      <div>
        <span class="orrery-kicker">THE NARRATIVE ORRERY</span>
        <h1>{{ store.currentProject?.title || "一部正在形成的作品" }}</h1>
        <p>{{ projection?.accessibility_summary || "正在从正式作品资料建立叙事脉络。" }}</p>
      </div>
      <div class="orrery-heading-meta">
        <span class="orrery-live"><i></i>实时观测</span>
        <strong>{{ formalChars.toLocaleString() }}</strong>
        <small>正式正文字符</small>
      </div>
    </header>

    <div class="orrery-controls" aria-label="叙事星仪控制">
      <div class="orrery-levels" role="tablist">
        <button :class="{ active: level === 'book' }" @click="changeLevel('book')">全书</button>
        <button :class="{ active: level === 'chapter' }" @click="changeLevel('chapter')">章节</button>
        <button :class="{ active: level === 'scene' }" @click="changeLevel('scene')">场景</button>
      </div>
      <select v-if="level === 'chapter'" v-model="focus" aria-label="选择章节">
        <option value="">当前章节</option><option v-for="chapter in chapterOptions" :key="chapter" :value="chapter">{{ chapter }}</option>
      </select>
      <select v-if="level === 'scene'" v-model="focus" aria-label="选择场景">
        <option value="">当前场景</option><option v-for="scene in sceneOptions" :key="String(scene.id)" :value="scene.id">{{ scene.title }}</option>
      </select>
      <span class="orrery-control-spacer"></span>
      <button class="orrery-icon" title="缩小" @click="zoom = Math.max(.72, zoom - .12)"><Minus :size="15" /></button>
      <button class="orrery-icon" title="恢复视野" @click="zoom = 1"><Focus :size="15" /></button>
      <button class="orrery-icon" title="放大" @click="zoom = Math.min(1.45, zoom + .12)"><Plus :size="15" /></button>
      <button class="orrery-icon" :title="listMode ? '显示星仪' : '显示无障碍列表'" @click="listMode = !listMode">
        <Network v-if="listMode" :size="15" /><List v-else :size="15" />
      </button>
    </div>

    <div v-if="loading && !projection" class="orrery-empty"><span></span><strong>正在校准故事轨迹</strong><p>只读取作品中已经存在的事实。</p></div>

    <div v-else-if="listMode" class="orrery-accessible-list" role="list">
      <button v-for="node in nodes" :key="node.node_id" :data-status="node.status" @click="selected = node">
        <i></i><span><strong>{{ node.label }}</strong><small>{{ node.subtitle || nodeTypeLabel(node.type) }}</small></span><em>{{ statusLabel(node.status) }}</em>
      </button>
    </div>

    <div v-else-if="nodes.length" class="orrery-stage" :class="{ sparse: nodes.length <= 3 }" tabindex="0">
      <svg viewBox="0 0 1400 700" preserveAspectRatio="xMidYMid meet" role="img" :aria-label="projection?.accessibility_summary">
        <defs>
          <radialGradient id="orrery-field" cx="50%" cy="50%" r="62%"><stop offset="0" stop-color="#21483e" stop-opacity=".34" /><stop offset="1" stop-color="#0b1c18" stop-opacity="0" /></radialGradient>
          <filter id="soft-glow"><feGaussianBlur stdDeviation="4" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          <pattern id="instrument-grid" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M 48 0 L 0 0 0 48" fill="none" stroke="#a6c0b7" stroke-opacity=".045" stroke-width="1" /></pattern>
        </defs>
        <rect width="1400" height="700" fill="url(#orrery-field)" />
        <rect width="1400" height="700" fill="url(#instrument-grid)" />
        <g class="orrery-calibration"><circle cx="700" cy="350" r="260" /><circle cx="700" cy="350" r="172" /><path d="M80 350 H1320 M700 55 V645" /></g>
        <g :style="{ transform: `scale(${zoom})`, transformOrigin: '700px 350px' }" class="orrery-zoom-layer">
          <path v-if="manuscriptPath" class="manuscript-spine-shadow" :d="manuscriptPath" />
          <path v-if="manuscriptPath" class="manuscript-spine" :d="manuscriptPath" />
          <g class="orrery-edges">
            <path v-for="edge in edges" :key="edge.edge_id" :d="edgePath(edge)" :data-type="edge.type"><title>{{ edge.label }}</title></path>
          </g>
          <g
            v-for="node in nodes"
            :key="node.node_id"
            class="orrery-node"
            :class="[{ selected: selected?.node_id === node.node_id, recent: recentMotion.has(node.node_id) }, `node-${node.type}`]"
            :data-status="node.status"
            :transform="`translate(${position(node.node_id).x}, ${position(node.node_id).y})`"
            tabindex="0"
            role="button"
            @click="openNode(node)"
            @dblclick="drillInto(node)"
            @keydown.enter="openNode(node)"
          >
            <circle class="node-orbit" :r="nodes.length <= 3 ? 38 : 30" />
            <circle class="node-core" :r="node.type === 'chapter' || node.type === 'scene' ? (nodes.length <= 3 ? 17 : 13) : (nodes.length <= 3 ? 11 : 8)" />
            <circle v-if="node.type === 'task'" class="task-wave" :r="nodes.length <= 3 ? 30 : 23" />
            <text class="node-label" :y="nodes.length <= 3 ? 55 : 45" text-anchor="middle">{{ node.label.slice(0, 12) }}</text>
            <text class="node-kind" :y="nodes.length <= 3 ? 72 : 61" text-anchor="middle">{{ nodeTypeLabel(node.type) }}</text>
          </g>
        </g>
      </svg>
      <div class="orrery-stage-caption"><Layers3 :size="14" /><span>{{ projection?.summary.node_count }} 个真实节点</span><i></i><span>{{ projection?.summary.edge_count }} 条叙事关系</span></div>
    </div>

    <div v-else class="orrery-empty"><span></span><strong>等待第一条故事轨迹</strong><p>场景、人物或正文形成后，星仪会从真实资料中生长。</p></div>

    <aside v-if="selected" class="orrery-inspector">
      <header><div><span>{{ nodeTypeLabel(selected.type) }}</span><strong>{{ selected.label }}</strong></div><button class="orrery-icon" title="关闭详情" @click="selected = null"><X :size="15" /></button></header>
      <p>{{ selected.subtitle || "这个节点来自作品的正式资料。" }}</p>
      <dl>
        <div><dt>当前状态</dt><dd>{{ statusLabel(selected.status) }}</dd></div>
        <div v-if="selected.metrics.word_target"><dt>本段目标</dt><dd>{{ selected.metrics.word_target.toLocaleString() }} 字</dd></div>
        <div v-if="selected.metrics.formal_chars"><dt>已进入正文</dt><dd>{{ selected.metrics.formal_chars.toLocaleString() }} 字</dd></div>
      </dl>
      <div v-if="selectedGrowth.target" class="orrery-growth"><span :style="{ width: `${selectedGrowth.width}%` }"></span><small>{{ selectedGrowth.actual.toLocaleString() }} / {{ selectedGrowth.target.toLocaleString() }}</small></div>
      <button v-if="['chapter', 'scene'].includes(selected.type)" class="orrery-drill" @click="drillInto(selected)"><ScanSearch :size="15" />聚焦这段脉络<ChevronRight :size="15" /></button>
      <button class="orrery-source" @click="navigateToSource(selected)"><BookOpenText :size="15" />查看对应作品资料</button>
    </aside>

    <nav v-if="projection?.timeline.length" class="orrery-timeline" aria-label="作品时间轴">
      <button
        v-for="item in projection.timeline"
        :key="item.node_id"
        :data-status="item.status"
        :class="{ active: selected?.node_id === item.node_id }"
        @click="selected = nodes.find((node) => node.node_id === item.node_id) || null"
      >
        <i></i><span>{{ item.label }}</span><small v-if="item.formal_chars">{{ item.formal_chars.toLocaleString() }} 字</small>
      </button>
    </nav>
  </section>
</template>
