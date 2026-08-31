<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { ArrowLeft, BookOpenText, BookPlus, ChevronDown, Clock3, Focus, Layers3, List, Maximize2, Network, RotateCcw, Settings2 } from "lucide-vue-next";
import { useRouter } from "vue-router";
import ChapterRail from "@/features/orrery/ChapterRail.vue";
import CharacterThreadRail from "@/features/orrery/CharacterThreadRail.vue";
import NarrativeSpineLayer from "@/features/orrery/NarrativeSpineLayer.vue";
import OrreryAccessibleView from "@/features/orrery/OrreryAccessibleView.vue";
import NarrativeParallaxStage from "@/features/orrery/NarrativeParallaxStage.vue";
import NarrativeHealthRail from "@/features/orrery/NarrativeHealthRail.vue";
import CreativeProgressionLayer from "@/features/orrery/CreativeProgressionLayer.vue";
import OrreryExplorationLayer from "@/features/orrery/OrreryExplorationLayer.vue";
import OrreryNavigationLayer from "@/features/orrery/OrreryNavigationLayer.vue";
import OrreryNodeOverlay from "@/features/orrery/OrreryNodeOverlay.vue";
import RelationLensBar from "@/features/orrery/RelationLensBar.vue";
import SpatialWindowLayer from "@/features/orrery/SpatialWindowLayer.vue";
import WorkspaceDock from "@/features/orrery/WorkspaceDock.vue";
import { chapterClusterFocusPoint, chapterRailFocusTarget } from "@/features/orrery/chapterFocus";
import { buildSpatialLayout } from "@/features/orrery/layout/layoutEngine";
import { useOrreryCreativeLive } from "@/features/orrery/live/useOrreryCreativeLive";
import { buildCreativeProgression } from "@/features/orrery/model/creativeProgression";
import { grammarLabel } from "@/features/orrery/model/grammarPresentation";
import { buildNarrativeSignalHierarchy, type OrrerySignalMode } from "@/features/orrery/model/narrativeSignalHierarchy";
import { applyRelationLens } from "@/features/orrery/model/relationLens";
import { viewBookmarkLabel, type OrreryHeatLens } from "@/features/orrery/model/exploration";
import { nodeForReaderUnit, readerUnitForNode } from "@/features/orrery/model/readerLink";
import type { RelationFamily } from "@/features/orrery/model/relations";
import { orreryClient } from "@/features/orrery/services/orreryClient";
import { manuscriptItems } from "@/services/presentation";
import { useAppStore } from "@/stores/app";
import { useHumanChoicesStore } from "@/stores/humanChoices";
import { useOrreryExplorationStore, type OrreryViewBookmark } from "@/stores/orreryExploration";
import { useReaderNavigationStore } from "@/stores/readerNavigation";
import { useSpatialProjectionStore } from "@/stores/spatialProjection";
import { useSpatialWindowsStore } from "@/stores/spatialWindows";
import type { SpatialGrammar, SpatialNarrativeNode, SpatialNarrativeProjection, SpatialNodeDetail } from "@/types/spatial";

const props = defineProps<{ dashboard: Record<string, unknown> | null; immersive?: boolean }>();

const emit = defineEmits<{ advance: []; inspectTask: []; openReader: []; choose: [choice: Record<string, unknown>] }>();
const app = useAppStore();
const router = useRouter();
const spatial = useSpatialProjectionStore();
const windows = useSpatialWindowsStore();
const humanChoices = useHumanChoicesStore();
const exploration = useOrreryExplorationStore();
const readerNavigation = useReaderNavigationStore();
const stage = ref<InstanceType<typeof NarrativeParallaxStage> | null>(null);
const listMode = ref(false);
const anchors = ref<Record<string, { x: number; y: number; visible: boolean; scale: number }>>({});
const choices = computed(() => humanChoices.choices);
const healthExpanded = ref(false);
const projectBandOpen = ref(false);
const activeCharacterId = ref("");
const hiddenRelationFamilies = ref<RelationFamily[]>([]);
const soloRelationFamily = ref<RelationFamily | "">("");
const staticStage = ref(false);
const forcedNodeIds = ref<string[]>([]);
const showAllLabels = ref(false);
const signalMode = ref<OrrerySignalMode>("narrative");
const navigationNodeId = ref("");
const heatLens = ref<OrreryHeatLens>("");
const comparedNodeIds = ref<string[]>([]);
let appliedReaderUnitId = "";

const projection = computed(() => spatial.projection);
const { creativeLive, liveNodeIds, creativeLiveLabel, openCreativeLive } = useOrreryCreativeLive({
  projectRoot: () => app.currentProjectPath, nodes: () => projection.value?.nodes || [],
  openWorkspace: () => windows.openInstrument("observatory"), navigate: navigateNode,
});
const displayProjection = computed(() => projection.value
  ? applyRelationLens(projection.value, { hidden: hiddenRelationFamilies.value, solo: soloRelationFamily.value })
  : null);
const layout = computed(() => displayProjection.value
  ? buildSpatialLayout(displayProjection.value.spatial_grammar, displayProjection.value.revision, displayProjection.value.nodes, displayProjection.value.layout_seed, displayProjection.value.layout_hints)
  : null);
const viewBookmarks = computed(() => exploration.forProject(app.currentProjectPath));
const deliveryReady = computed(() => String(app.delivery?.status || "") === "ready");
const prose = computed(() => manuscriptItems((app.library || null) as Record<string, unknown> | null));
const progress = computed(() => app.projectProgress);
const overallProgress = computed(() => Number(progress.value?.overall_percent));
const chapterNodes = computed(() => (projection.value?.nodes || [])
  .filter((node) => (node.creative_kind || node.type) === "chapter")
  .sort((left, right) => left.order - right.order));
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
const activeChapterId = computed(() => {
  if (!projection.value) return "";
  if (projection.value.level === "chapter" && projection.value.focus) return projection.value.focus;
  if (projection.value.level === "scene") {
    const focusedScene = projection.value.nodes.find((node) => node.node_id === `scene:${projection.value?.focus}`);
    const chapterId = String(focusedScene?.metrics.chapter_id || "");
    if (chapterId) return chapterId;
  }
  const selected = projection.value.nodes.find((node) => node.node_id === windows.selectedNodeId);
  if (selected?.type === "chapter") return selected.source_id || selected.node_id;
  return selected?.type === "scene" ? String(selected.metrics.chapter_id || "") : "";
});
const timeBounds = computed(() => {
  const bands = projection.value?.nodes
    .filter((node) => node.type === "chapter" || node.type === "scene")
    .map((node) => Number(node.time_band || 0)) || [0];
  return { min: Math.min(...bands), max: Math.max(...bands) };
});
const creativeProgression = computed(() => displayProjection.value ? buildCreativeProgression(displayProjection.value) : null);
const signalHierarchy = computed(() => displayProjection.value
  ? buildNarrativeSignalHierarchy(displayProjection.value.nodes, {
      mode: signalMode.value,
      edges: displayProjection.value.edges,
      characterReferences: displayProjection.value.character_references,
      level: displayProjection.value.level,
      activeChapterId: activeChapterId.value,
      pinnedNodeIds: [windows.selectedNodeId, navigationNodeId.value, ...forcedNodeIds.value],
    })
  : null);
const stageNodes = computed(() => signalHierarchy.value?.nodes || []);
const stageNodeIds = computed(() => [...(signalHierarchy.value?.nodeIds || [])]);
const stageProjection = computed<SpatialNarrativeProjection | null>(() => {
  if (!displayProjection.value || !signalHierarchy.value) return null;
  const ids = signalHierarchy.value.nodeIds;
  return {
    ...displayProjection.value,
    nodes: signalHierarchy.value.nodes,
    edges: displayProjection.value.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)),
  };
});

watch(() => app.currentProjectPath, (root) => {
  windows.clear();
  staticStage.value = false;
  activeCharacterId.value = "";
  hiddenRelationFamilies.value = [];
  soloRelationFamily.value = "";
  forcedNodeIds.value = [];
  showAllLabels.value = false;
  signalMode.value = "narrative";
  navigationNodeId.value = "";
  heatLens.value = "";
  comparedNodeIds.value = [];
  appliedReaderUnitId = "";
  readerNavigation.reset();
  if (root) {
    void spatial.open(root, { level: "book", focus: "" });
    void loadChoices();
  }
  else {
    spatial.close();
  }
}, { immediate: true });
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
  if (next?.level === "character") {
    const focusId = String(next.focus || "").replace(/^character:/, "");
    activeCharacterId.value = next.nodes.find((node) => node.type === "character"
      && (node.node_id === next.focus || node.source_id === focusId || node.node_id === `character:${focusId}`))?.node_id || "";
    return;
  }
  if (activeCharacterId.value && !next?.nodes.some((node) => node.node_id === activeCharacterId.value && node.type === "character")) {
    activeCharacterId.value = "";
  }
});
watch(anchors, (value) => windows.syncNodeAnchors(value), { deep: false });
watch(() => readerNavigation.activeUnitId, (unitId) => {
  if (!unitId || unitId === appliedReaderUnitId || !windows.windows.some((item) => item.kind === "reader")) return;
  const unit = app.readerManifest?.units.find((item) => item.unit_id === unitId);
  const sceneId = String(unit?.scene_id || "");
  if (!sceneId) return;
  appliedReaderUnitId = unitId;
  void focusReaderScene(sceneId);
});
onBeforeUnmount(() => {
  windows.clear();
  spatial.close();
});

async function selectNode(node: SpatialNarrativeNode): Promise<void> {
  if (!app.currentProjectPath || !projection.value) return;
  let detail: SpatialNodeDetail | null = null;
  try {
    detail = await orreryClient.nodeDetail(node.detail_endpoint, {
      projectRoot: app.currentProjectPath,
      level: projection.value.level,
      focus: projection.value.focus,
      grammar: projection.value.spatial_grammar,
    });
  } catch { /* Details are an enhancement, not a reason to block node inspection. */ }
  windows.openNode(node, detail, anchors.value[node.node_id]);
}

function setLevel(level: "book" | "chapter" | "scene"): void {
  activeCharacterId.value = "";
  void spatial.setView({ level, focus: "" });
}

async function goBack(): Promise<void> {
  activeCharacterId.value = "";
  await spatial.goBack();
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
  navigationNodeId.value = node.node_id;
  const point = layout.value?.points.get(node.node_id);
  if (point) stage.value?.focus(point, node.node_id);
  void selectNode(node);
}

function navigateNode(node: SpatialNarrativeNode): void {
  navigationNodeId.value = node.node_id;
  const point = layout.value?.points.get(node.node_id);
  if (point) stage.value?.focus(point, node.node_id);
}

function replayNode(node: SpatialNarrativeNode): void {
  navigationNodeId.value = node.node_id;
  const point = layout.value?.points.get(node.node_id);
  if (point) stage.value?.focus(point, node.node_id);
}

function focusProgressionNode(nodeId: string): void {
  const node = projection.value?.nodes.find((item) => item.node_id === nodeId);
  if (node) focusNodeObject(node);
}

function saveViewBookmark(): void {
  if (!app.currentProjectPath || !projection.value) return;
  exploration.save({
    projectRoot: app.currentProjectPath,
    label: viewBookmarkLabel(
      projection.value.nodes,
      projection.value.level,
      projection.value.focus,
      grammarLabel(spatial.grammar),
    ),
    level: spatial.level,
    focus: spatial.focus,
    grammar: spatial.grammar,
    timeCursor: spatial.timeCursor,
    timeWindow: spatial.timeWindow,
    heatLens: heatLens.value,
    nodeId: navigationNodeId.value || windows.selectedNodeId,
  });
}

async function restoreViewBookmark(bookmark: OrreryViewBookmark): Promise<void> {
  heatLens.value = bookmark.heatLens;
  spatial.setObservation({ cursor: bookmark.timeCursor, window: bookmark.timeWindow });
  await spatial.setView({ level: bookmark.level, focus: bookmark.focus, grammar: bookmark.grammar });
  await nextTick();
  const node = projection.value?.nodes.find((item) => item.node_id === bookmark.nodeId);
  if (node) replayNode(node);
}

async function focusReaderScene(sceneId: string): Promise<void> {
  if (spatial.level !== "scene" || spatial.focus !== sceneId) {
    await spatial.setView({ level: "scene", focus: sceneId });
  }
  await nextTick();
  await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
  const unit = app.readerManifest?.units.find((item) => item.scene_id === sceneId);
  const node = unit && projection.value ? nodeForReaderUnit(projection.value.nodes, unit) : undefined;
  if (node) navigateNode(node);
}

function openReaderForNode(node: SpatialNarrativeNode): void {
  const units = app.readerManifest?.units || [];
  const unit = readerUnitForNode(node, units);
  windows.openInstrument("reader");
  if (!unit) return;
  readerNavigation.request(unit.unit_id);
  windows.setReaderMode("reading");
}

function resetView(): void {
  stage.value?.resetView();
}

async function openChapterFromRail(nodeId: string): Promise<void> {
  const chapter = chapterNodes.value.find((item) => item.node_id === nodeId);
  if (!chapter) return;
  activeCharacterId.value = "";
  await spatial.setView(chapterRailFocusTarget(chapter.source_id));
  await focusChapterCluster(chapter.source_id, chapter.node_id);
}

async function focusChapterCluster(chapterId: string, chapterNodeId: string): Promise<void> {
  await nextTick();
  // The renderer mounts its new anchors during Vue's paint. Waiting for that
  // frame keeps the focus target in the newly selected coordinate system.
  await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
  const currentLayout = layout.value;
  const currentProjection = projection.value;
  if (!currentLayout || !currentProjection) return;
  const chapterProjectionNode = currentProjection.nodes.find((node) => node.type === "chapter" && node.source_id === chapterId);
  const clusterPoints = currentProjection.nodes
    .filter((node) => node.type === "scene" && String(node.metrics.chapter_id || "") === chapterId)
    .map((node) => currentLayout.points.get(node.node_id))
    .filter((point): point is NonNullable<typeof point> => Boolean(point));
  if (clusterPoints.length) {
    stage.value?.focusCluster(clusterPoints, chapterNodeId);
    return;
  }
  const point = chapterClusterFocusPoint(currentProjection.nodes, currentLayout.points, chapterId)
    || currentLayout.points.get(chapterNodeId)
    || currentLayout.points.get(chapterProjectionNode?.node_id || "");
  if (point) stage.value?.focus(point, chapterNodeId);
}

async function selectCharacter(nodeId: string): Promise<void> {
  if (!nodeId) {
    activeCharacterId.value = "";
    if (spatial.level === "character") await spatial.goBack();
    return;
  }
  activeCharacterId.value = nodeId;
  await spatial.setView({ level: "character", focus: nodeId });
}

function toggleRelationFamily(family: RelationFamily): void {
  if (soloRelationFamily.value) soloRelationFamily.value = "";
  hiddenRelationFamilies.value = hiddenRelationFamilies.value.includes(family)
    ? hiddenRelationFamilies.value.filter((item) => item !== family)
    : [...hiddenRelationFamilies.value, family];
}

function soloRelation(family: RelationFamily | ""): void {
  soloRelationFamily.value = family;
}

function resetRelationLens(): void {
  hiddenRelationFamilies.value = [];
  soloRelationFamily.value = "";
}

async function loadChoices(): Promise<void> {
  if (!app.currentProjectPath) {
    humanChoices.reset();
    return;
  }
  await humanChoices.load(app.currentProjectPath).catch(() => undefined);
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
      <button v-if="spatial.canGoBack" class="orrery-v3-icon" title="返回上一个叙事焦点" aria-label="返回上一个叙事焦点" @click="goBack"><ArrowLeft :size="15" /></button>
      <div class="orrery-v3-levels" role="tablist"><button :class="{ active: spatial.level === 'book' }" @click="setLevel('book')">全书</button><button :class="{ active: spatial.level === 'chapter' }" @click="setLevel('chapter')">章节</button><button :class="{ active: spatial.level === 'scene' }" @click="setLevel('scene')">场景</button></div>
      <div class="orrery-v3-levels orrery-signal-mode" role="group" aria-label="星仪信息密度"><button :class="{ active: signalMode === 'narrative' }" title="只显示作品主脉、主要人物和当前创作信号" @click="signalMode = 'narrative'">主脉</button><button :class="{ active: signalMode === 'all' }" title="显示项目中的全部工程事实" @click="signalMode = 'all'">全部</button></div>
      <label><Layers3 :size="14" /><select :value="spatial.grammar" aria-label="叙事空间构型" @change="setGrammar"><option v-for="grammar in projection?.available_grammars || []" :key="grammar" :value="grammar">{{ grammarLabel(grammar) }}</option></select></label>
      <label class="orrery-time-observer" title="调整观测时点；全书节点不会被删除"><Clock3 :size="14" /><input type="range" :min="timeBounds.min" :max="timeBounds.max" step="1" :value="spatial.timeCursor" aria-label="叙事观测时点" @input="spatial.setObservation({ cursor: Number(($event.target as HTMLInputElement).value) })" /><output>{{ Math.round(spatial.timeCursor) }}</output></label>
      <span></span>
      <button class="orrery-v3-icon" title="完整显示当前构型" @click="stage?.fit()"><Focus :size="16" /></button>
      <button class="orrery-v3-icon" title="复位伪 3D 视角；中键拖动可调整视角" aria-label="复位伪 3D 视角" @click="resetView"><RotateCcw :size="15" /></button>
      <button class="orrery-v3-icon" :title="listMode ? '显示空间场景' : '显示无障碍列表'" @click="listMode = !listMode"><Network v-if="listMode" :size="16" /><List v-else :size="16" /></button>
    </nav>

    <div v-if="spatial.loading && !projection" class="orrery-v3-empty"><i></i><strong>正在建立叙事场域</strong><p>只会读取已经进入正式项目的作品事实。</p></div>
    <div v-else-if="spatial.error && !projection" class="orrery-v3-empty error"><strong>暂时无法读取叙事场域</strong><p>{{ spatial.error }}</p><button class="secondary-button" @click="spatial.refresh()">重新连接</button></div>
    <OrreryAccessibleView v-else-if="displayProjection && listMode" :nodes="displayProjection.nodes" :selected-node-id="windows.selectedNodeId" @select="selectNode" />
    <div v-else-if="displayProjection && layout" class="orrery-v3-stage" :class="{ 'is-static-stage': staticStage }">
      <NarrativeParallaxStage v-if="stageProjection" ref="stage" :projection="stageProjection" :layout="layout" :selected-node-id="windows.selectedNodeId" @anchors="anchors = $event" @degraded="staticStage = true" />
      <NarrativeSpineLayer :projection="displayProjection" :anchors="anchors" :visible-node-ids="stageNodeIds" :active-character-id="activeCharacterId" :active-chapter-id="activeChapterId" :live-node-ids="liveNodeIds" />
      <CreativeProgressionLayer v-if="creativeProgression" :progression="creativeProgression" :anchors="anchors" @focus="focusProgressionNode" />
      <OrreryNodeOverlay
        :nodes="stageNodes"
        :anchors="anchors"
        :level="displayProjection.level"
        :motion-events="displayProjection.motion_events"
        :activities="displayProjection.activities"
        :live-node-ids="liveNodeIds"
        :time-cursor="spatial.timeCursor"
        :time-window="spatial.timeWindow"
        :selected-node-id="windows.selectedNodeId"
        :focus-node-id="windows.selectedNodeId"
        :navigation-node-id="navigationNodeId"
        :forced-node-ids="forcedNodeIds"
        :show-all-labels="showAllLabels"
        :heat-lens="heatLens"
        :compared-node-ids="comparedNodeIds"
        @select="selectNode"
        @focus="focusNodeObject"
      />
      <OrreryNavigationLayer
        :nodes="displayProjection.nodes"
        :points="layout.points"
        :anchors="anchors"
        :active-node-id="navigationNodeId || windows.selectedNodeId"
        @navigate="navigateNode"
        @inspect="focusNodeObject"
        @forced-labels="forcedNodeIds = $event"
        @show-all-labels="showAllLabels = $event"
      />
      <OrreryExplorationLayer
        :nodes="displayProjection.nodes"
        :anchors="anchors"
        :level="displayProjection.level"
        :heat-lens="heatLens"
        :compared-node-ids="comparedNodeIds"
        :bookmarks="viewBookmarks"
        @heat-lens="heatLens = $event"
        @compare="comparedNodeIds = $event"
        @replay="replayNode"
        @save-bookmark="saveViewBookmark"
        @restore-bookmark="restoreViewBookmark"
        @remove-bookmark="exploration.remove"
      />
      <RelationLensBar
        :profiles="projection?.relation_profiles || []"
        :hidden="hiddenRelationFamilies"
        :solo="soloRelationFamily"
        @toggle="toggleRelationFamily"
        @solo="soloRelation"
        @reset="resetRelationLens"
      />
      <NarrativeHealthRail :dashboard="props.dashboard" :expanded="healthExpanded" @toggle="healthExpanded = !healthExpanded" />
      <CharacterThreadRail
        :nodes="displayProjection.nodes"
        :references="displayProjection.character_references"
        :active-character-id="activeCharacterId"
        :active-chapter-id="activeChapterId"
        @select="selectCharacter"
      />
      <button class="orrery-creative-live-beacon" :class="{ active: creativeLive.snapshot?.status === 'active', blocked: creativeLive.snapshot?.status === 'blocked' }" title="打开创作现场并定位正在处理的作品节点" @click="openCreativeLive">
        <span><i></i>{{ creativeLive.snapshot?.status === 'active' ? 'LIVE' : '现场' }}</span>
        <strong>{{ creativeLiveLabel }}</strong>
        <small>{{ creativeLive.activeArtifact?.identity === 'streaming_preview' ? `${creativeLive.activeArtifact.content.length.toLocaleString('zh-CN')} 字符正在形成` : '查看 Agent、正文与审查轨迹' }}</small>
      </button>
      <button class="orrery-v3-progress-spindle" :class="{ 'is-calibrated': progress?.status === 'calibrated' }" title="查看作品总体进度" @click="windows.openInstrument('progress')">
        <span>WORK IN FORMATION</span>
        <strong>{{ Number.isFinite(overallProgress) ? `${overallProgress.toFixed(1)}%` : '待校准' }}</strong>
        <i><b :style="{ height: `${Math.min(100, Math.max(0, overallProgress || 0))}%` }"></b></i>
        <small>{{ progress?.status === 'calibrated' ? '准备 / 正文 / 交付' : '先设置可靠字数目标' }}</small>
      </button>
      <div class="orrery-v3-caption"><Maximize2 :size="14" /><span>{{ signalHierarchy?.nodes.length || 0 }} 个{{ signalMode === 'narrative' ? '主干' : '可见' }}节点</span><i></i><span>{{ signalHierarchy?.total || 0 }} 项作品事实</span></div>
    </div>
    <div v-else class="orrery-v3-empty"><i></i><strong>等待作品长出第一段脉络</strong><p>场景、人物或正文出现后，这里会形成可以进入的叙事场域。</p></div>
    <WorkspaceDock :pending-choices="choices.length" :delivery-ready="deliveryReady" @open="windows.openInstrument" @organize="windows.constrainToViewport" />
    <ChapterRail :chapters="chapterNodes" :selected-node-id="activeChapterRailNodeId" @select="openChapterFromRail" />
    <SpatialWindowLayer :projection="projection" :dashboard="props.dashboard" :choices="choices" :delivery="app.delivery" :progress="progress" :prose="prose" @advance="emit('advance')" @inspect-task="emit('inspectTask')" @open-reader="emit('openReader')" @read-node="openReaderForNode" @choose="emit('choose', $event)" @focus-node="focusNode" />
  </section>
</template>
