<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { BookOpenText, BookPlus, ChevronDown, Focus, Gauge, GitBranch, Layers3, List, Maximize2, Network, PackageCheck, Settings2, SlidersHorizontal } from "lucide-vue-next";
import { useRouter } from "vue-router";
import ChapterRail from "@/features/orrery/ChapterRail.vue";
import CharacterThreadRail from "@/features/orrery/CharacterThreadRail.vue";
import NarrativeSpineLayer from "@/features/orrery/NarrativeSpineLayer.vue";
import OrreryAccessibleView from "@/features/orrery/OrreryAccessibleView.vue";
import NarrativeParallaxStage from "@/features/orrery/NarrativeParallaxStage.vue";
import NarrativeHealthRail from "@/features/orrery/NarrativeHealthRail.vue";
import OrreryNodeOverlay from "@/features/orrery/OrreryNodeOverlay.vue";
import SpatialWindowLayer from "@/features/orrery/SpatialWindowLayer.vue";
import { buildSpatialLayout } from "@/features/orrery/layout/layoutEngine";
import { api, query } from "@/services/api";
import { manuscriptItems } from "@/services/presentation";
import { useAppStore } from "@/stores/app";
import { useSpatialProjectionStore } from "@/stores/spatialProjection";
import { useSpatialWindowsStore } from "@/stores/spatialWindows";
import type { SpatialGrammar, SpatialNarrativeNode, SpatialNarrativeProjection, SpatialNodeDetail } from "@/types/spatial";

const props = defineProps<{ dashboard: Record<string, unknown> | null; immersive?: boolean }>();

const emit = defineEmits<{ advance: []; inspectTask: []; openReader: []; choose: [choice: Record<string, unknown>] }>();
const app = useAppStore();
const router = useRouter();
const spatial = useSpatialProjectionStore();
const windows = useSpatialWindowsStore();
const stage = ref<InstanceType<typeof NarrativeParallaxStage> | null>(null);
const listMode = ref(false);
const anchors = ref<Record<string, { x: number; y: number; visible: boolean; scale: number }>>({});
const choices = ref<Record<string, unknown>[]>([]);
const healthExpanded = ref(false);
const projectBandOpen = ref(false);
const activeCharacterId = ref("");
const staticStage = ref(false);
const bookChapterNodes = ref<SpatialNarrativeNode[]>([]);
let chapterRailRequest = 0;

const projection = computed(() => spatial.projection);
const layout = computed(() => projection.value ? buildSpatialLayout(projection.value.spatial_grammar, projection.value.revision, projection.value.nodes, projection.value.layout_seed) : null);
const deliveryReady = computed(() => String(app.delivery?.status || "") === "ready");
const prose = computed(() => manuscriptItems((app.library || null) as Record<string, unknown> | null));
const progress = computed(() => app.projectProgress);
const overallProgress = computed(() => Number(progress.value?.overall_percent));
const chapterNodes = computed(() => [...bookChapterNodes.value].sort((left, right) => left.order - right.order));
const activeChapterRailNodeId = computed(() => {
  if (!projection.value) return windows.selectedNodeId;
  if (projection.value.level === "chapter") {
    return chapterNodes.value.find((node) => node.source_id === projection.value?.focus)?.node_id || windows.selectedNodeId;
  }
  if (projection.value.level === "scene") {
    const selected = projection.value.nodes.find((node) => node.node_id === `scene:${projection.value?.focus}`);
    const chapterId = String(selected?.metrics.chapter_id || "");
    return chapterNodes.value.find((node) => node.source_id === chapterId)?.node_id || windows.selectedNodeId;
  }
  return windows.selectedNodeId;
});

watch(() => app.currentProjectPath, (root) => {
  windows.clear();
  staticStage.value = false;
  if (root) {
    void spatial.open(root, { level: "book", focus: "" });
    void loadChoices();
    void loadChapterRail(root);
  }
  else {
    bookChapterNodes.value = [];
    spatial.close();
  }
}, { immediate: true });
watch(() => projection.value?.source_revisions?.narrative_v2, () => {
  if (app.currentProjectPath) void loadChapterRail(app.currentProjectPath);
});
watch(
  [() => app.currentProjectPath, () => projection.value?.spatial_grammar, () => projection.value?.revision],
  ([root, grammar]) => {
    if (!root || !grammar || !projection.value) return;
    windows.setScope(`${root}::${grammar}`, projection.value.nodes);
  },
  { immediate: true },
);
watch(() => projection.value?.source_revisions?.dashboard, () => {
  // A newly opened formal decision is a dashboard fact. Refresh only when that
  // source changes, rather than polling the choice endpoint from the canvas.
  void loadChoices();
});
watch(projection, (next) => {
  if (activeCharacterId.value && !next?.nodes.some((node) => node.node_id === activeCharacterId.value && node.type === "character")) {
    activeCharacterId.value = "";
  }
});
watch(anchors, (value) => windows.syncNodeAnchors(value), { deep: false });
onBeforeUnmount(() => {
  windows.clear();
  spatial.close();
});

async function selectNode(node: SpatialNarrativeNode): Promise<void> {
  if (!app.currentProjectPath || !projection.value) return;
  let detail: SpatialNodeDetail | null = null;
  try {
    detail = await api<SpatialNodeDetail>(`${node.detail_endpoint}?${query({
      project_root: app.currentProjectPath,
      level: projection.value.level,
      focus: projection.value.focus,
      grammar: projection.value.spatial_grammar,
    })}`);
  } catch { /* Details are an enhancement, not a reason to block node inspection. */ }
  windows.openNode(node, detail, anchors.value[node.node_id]);
}

function setLevel(level: "book" | "chapter" | "scene"): void {
  void spatial.setView({ level, focus: "" });
}

async function setGrammar(event: Event): Promise<void> {
  const value = (event.target as HTMLSelectElement).value as SpatialGrammar;
  await spatial.setView({ grammar: value });
  // The grammar refresh changes the coordinate system. Reframe after the new
  // projection and its layout have reached the mounted stage, rather than
  // trusting a reactive watcher to win a race with the previous camera.
  await nextTick();
  await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
  stage.value?.openingSegment();
}

function switchProject(path: string): void {
  if (!path) return;
  projectBandOpen.value = false;
  app.setCurrentProject(path);
}

function focusNode(nodeId: string): void {
  const node = projection.value?.nodes.find((item) => item.node_id === nodeId);
  if (node) void focusNodeObject(node);
}

function focusNodeObject(node: SpatialNarrativeNode): void {
  const point = layout.value?.points.get(node.node_id);
  if (point) stage.value?.focus(point, node.node_id);
  void selectNode(node);
}

async function openChapterFromRail(nodeId: string): Promise<void> {
  const chapter = chapterNodes.value.find((item) => item.node_id === nodeId);
  if (!chapter) return;
  // The rail is a global table of contents. It never replaces the full-book
  // canvas: it changes the detailed focus and then flies the camera to that
  // chapter's first scene on the same narrative river.
  const firstScene = projection.value?.nodes
    .filter((node) => node.type === "scene" && String(node.metrics.chapter_id || "") === chapter.source_id)
    .sort((left, right) => left.order - right.order)[0];
  if (spatial.level === "scene") {
    await spatial.setView({ level: "scene", focus: firstScene?.node_id.replace(/^scene:/, "") || "" });
  } else {
    await spatial.setView({ level: "chapter", focus: chapter.source_id });
  }
  await focusChapterCluster(chapter.source_id);
}

async function focusChapterCluster(chapterId: string): Promise<void> {
  await nextTick();
  // The renderer mounts its new anchors during Vue's paint. A frame boundary
  // keeps directory navigation fluid without selecting or opening a window.
  window.requestAnimationFrame(() => {
    const target = projection.value?.nodes
      .filter((node) => node.type === "scene" && String(node.metrics.chapter_id || "") === chapterId)
      .sort((left, right) => left.order - right.order)[0];
    const point = target ? layout.value?.points.get(target.node_id) : undefined;
    if (target && point) stage.value?.focus(point, target.node_id);
  });
}

function selectCharacter(nodeId: string): void {
  activeCharacterId.value = nodeId;
}

function grammarLabel(grammar: SpatialGrammar): string {
  const labels: Record<SpatialGrammar, string> = {
    spine: "脊柱",
    braid: "编织",
    strata: "层室",
    constellation: "星簇",
    loop: "回环",
    stage: "舞台",
  };
  return labels[grammar];
}

async function loadChoices(): Promise<void> {
  if (!app.currentProjectPath) {
    choices.value = [];
    return;
  }
  const result: { items?: Record<string, unknown>[]; choices?: Record<string, unknown>[] } = await api<{ items?: Record<string, unknown>[]; choices?: Record<string, unknown>[] }>(
    `/workflow/current-choice?${query({ project_root: app.currentProjectPath })}`,
  ).catch(() => ({ items: [] }));
  choices.value = result.items || result.choices || [];
}

async function loadChapterRail(root: string): Promise<void> {
  const sequence = ++chapterRailRequest;
  const payload = await api<SpatialNarrativeProjection>(`/narrative/projection/v3?${query({
    project_root: root,
    level: "book",
    focus: "",
    grammar: spatial.grammar,
  })}`).catch(() => null);
  if (sequence !== chapterRailRequest || root !== app.currentProjectPath || !payload) return;
  bookChapterNodes.value = payload.nodes.filter((node) => node.type === "chapter");
}
</script>

<template>
  <section class="orrery-v3" :class="{ immersive }" :data-grammar="projection?.spatial_grammar || spatial.grammar" aria-label="活体叙事场域">
    <header class="orrery-v3-heading">
      <div><span>ARC VELLUM / NARRATIVE STAGE</span><h1>{{ app.currentProject?.title || "一部正在形成的作品" }}</h1><p>{{ projection?.accessibility_summary || "正在校准作品的空间结构。" }}</p></div>
      <dl v-if="projection"><div><dt>构型</dt><dd>{{ grammarLabel(projection.spatial_grammar) }}</dd></div><div><dt>正式正文</dt><dd>{{ Number(projection.summary.formal_prose_chars || 0).toLocaleString() }} 字</dd></div></dl>
    </header>

    <div class="orrery-v3-project-band" :class="{ open: projectBandOpen }">
      <button class="project-band-current" title="切换当前作品" @click="projectBandOpen = !projectBandOpen"><BookOpenText :size="15" /><span><small>当前作品</small><strong>{{ app.currentProject?.title || '选择作品' }}</strong></span><ChevronDown :size="15" /></button>
      <button class="orrery-v3-icon" title="建立新作品" @click="router.push('/projects')"><BookPlus :size="16" /></button>
      <button class="orrery-v3-icon" title="应用设置" @click="router.push('/settings')"><Settings2 :size="16" /></button>
      <div v-if="projectBandOpen" class="project-band-menu"><button v-for="project in app.projects" :key="project.path" :class="{ active: project.path === app.currentProjectPath }" @click="switchProject(project.path)"><span><strong>{{ project.title }}</strong><small>{{ project.genre || project.work_type || '作品' }}</small></span><i>{{ project.path === app.currentProjectPath ? '当前' : '切换' }}</i></button><button class="project-band-create" @click="router.push('/projects')"><BookPlus :size="15" />建立一部新作品</button></div>
    </div>

    <nav class="orrery-v3-controls" aria-label="叙事场域控制">
      <div class="orrery-v3-levels" role="tablist"><button :class="{ active: spatial.level === 'book' }" @click="setLevel('book')">全书</button><button :class="{ active: spatial.level === 'chapter' }" @click="setLevel('chapter')">章节</button><button :class="{ active: spatial.level === 'scene' }" @click="setLevel('scene')">场景</button></div>
      <label><Layers3 :size="14" /><select :value="spatial.grammar" aria-label="叙事空间构型" @change="setGrammar"><option v-for="grammar in projection?.available_grammars || []" :key="grammar" :value="grammar">{{ grammarLabel(grammar) }}</option></select></label>
      <span></span>
      <button class="orrery-v3-icon" title="完整显示当前构型" @click="stage?.fit()"><Focus :size="16" /></button>
      <button class="orrery-v3-icon" :title="listMode ? '显示空间场景' : '显示无障碍列表'" @click="listMode = !listMode"><Network v-if="listMode" :size="16" /><List v-else :size="16" /></button>
    </nav>

    <div v-if="spatial.loading && !projection" class="orrery-v3-empty"><i></i><strong>正在建立叙事场域</strong><p>只会读取已经进入正式项目的作品事实。</p></div>
    <div v-else-if="spatial.error && !projection" class="orrery-v3-empty error"><strong>暂时无法读取叙事场域</strong><p>{{ spatial.error }}</p><button class="secondary-button" @click="spatial.refresh()">重新连接</button></div>
    <OrreryAccessibleView v-else-if="projection && listMode" :nodes="projection.nodes" :selected-node-id="windows.selectedNodeId" @select="selectNode" />
    <div v-else-if="projection && layout" class="orrery-v3-stage" :class="{ 'is-static-stage': staticStage }">
      <NarrativeParallaxStage ref="stage" :projection="projection" :layout="layout" :selected-node-id="windows.selectedNodeId" @anchors="anchors = $event" @degraded="staticStage = true" />
      <NarrativeSpineLayer :projection="projection" :anchors="anchors" :active-character-id="activeCharacterId" />
      <OrreryNodeOverlay :nodes="projection.nodes" :anchors="anchors" :level="projection.level" :motion-events="projection.motion_events" :selected-node-id="windows.selectedNodeId" :focus-node-id="windows.selectedNodeId" @select="selectNode" @focus="focusNodeObject" />
      <NarrativeHealthRail :dashboard="props.dashboard" :expanded="healthExpanded" @toggle="healthExpanded = !healthExpanded" />
      <CharacterThreadRail :nodes="projection.nodes" :edges="projection.edges" :active-character-id="activeCharacterId" @select="selectCharacter" />
      <button class="orrery-v3-progress-spindle" :class="{ 'is-calibrated': progress?.status === 'calibrated' }" title="查看作品总体进度" @click="windows.openInstrument('progress')">
        <span>WORK IN FORMATION</span>
        <strong>{{ Number.isFinite(overallProgress) ? `${overallProgress.toFixed(1)}%` : '待校准' }}</strong>
        <i><b :style="{ height: `${Math.min(100, Math.max(0, overallProgress || 0))}%` }"></b></i>
        <small>{{ progress?.status === 'calibrated' ? '准备 / 正文 / 交付' : '先设置可靠字数目标' }}</small>
      </button>
      <div class="orrery-v3-caption"><Maximize2 :size="14" /><span>{{ projection.summary.node_count }} 个真实节点</span><i></i><span>{{ projection.summary.cluster_count }} 个叙事构件</span></div>
    </div>
    <div v-else class="orrery-v3-empty"><i></i><strong>等待作品长出第一段脉络</strong><p>场景、人物或正文出现后，这里会形成可以进入的叙事场域。</p></div>
    <nav class="orrery-v3-instrument-dock" aria-label="创作控制仪表">
      <button title="打开推进仪表" @click="windows.openInstrument('progress')"><Gauge :size="16" /><span>推进</span></button>
      <button title="查看待定决定" :data-count="choices.length || undefined" @click="windows.openInstrument('decisions')"><GitBranch :size="16" /><span>决策</span></button>
      <button title="查看创作规则" @click="windows.openInstrument('rules')"><SlidersHorizontal :size="16" /><span>规则</span></button>
    </nav>
    <button class="orrery-v3-reader-entry" title="打开正文长卷" @click="windows.openInstrument('reader')"><BookOpenText :size="16" /><span><small>MANUSCRIPT</small><strong>正文长卷</strong></span></button>
    <button class="orrery-v3-delivery-beacon" :class="{ ready: deliveryReady }" :disabled="!deliveryReady" :title="deliveryReady ? '作品已具备交付条件' : '交付条件尚未满足'" @click="windows.openInstrument('delivery')"><PackageCheck :size="17" /><span>{{ deliveryReady ? '可以交付' : '交付待命' }}</span></button>
    <ChapterRail :chapters="chapterNodes" :selected-node-id="activeChapterRailNodeId" @select="openChapterFromRail" />
    <SpatialWindowLayer :projection="projection" :dashboard="props.dashboard" :choices="choices" :delivery="app.delivery" :progress="progress" :prose="prose" @advance="emit('advance')" @inspect-task="emit('inspectTask')" @open-reader="emit('openReader')" @choose="emit('choose', $event)" @focus-node="focusNode" />
  </section>
</template>
