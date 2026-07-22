<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Activity, ArrowUpRight, BookOpenText, CircleAlert, CircleCheck, Download, FileCheck2, Focus, GitBranch, PackageOpen, PauseCircle, PlayCircle, RefreshCw, Route, ScanSearch } from "lucide-vue-next";
import SpatialWindowFrame from "@/features/orrery/SpatialWindowFrame.vue";
import QualityView from "@/features/quality/QualityView.vue";
import ManuscriptReader from "@/components/ManuscriptReader.vue";
import SafeMarkdown from "@/components/SafeMarkdown.vue";
import { useSpatialWindowsStore } from "@/stores/spatialWindows";
import { useAppStore } from "@/stores/app";
import type { SpatialNarrativeProjection } from "@/types/spatial";
import type { ProjectProgress } from "@/types/api";
import { asList, asRecord, describeGate, labelFor } from "@/services/presentation";
import { api, authorizedFetch, query } from "@/services/api";

const props = defineProps<{ projection: SpatialNarrativeProjection | null; dashboard: Record<string, unknown> | null; choices: Record<string, unknown>[]; delivery: Record<string, unknown> | null; progress: ProjectProgress | null; prose: Record<string, unknown>[] }>();
const emit = defineEmits<{ advance: []; inspectTask: []; openReader: []; focusNode: [nodeId: string]; choose: [choice: Record<string, unknown>] }>();
const windows = useSpatialWindowsStore();
const app = useAppStore();
const formalChars = computed(() => Number(props.projection?.summary.formal_prose_chars || 0));
const routeAudits = computed(() => asList<Record<string, unknown>>(props.dashboard?.route_audits));
const currentTask = computed(() => asRecord(props.dashboard?.current_task));
const libraryCounts = computed(() => asRecord(app.library?.counts));
const librarySections = computed(() => asRecord(app.library?.sections));
const activeRun = computed(() => asRecord(app.autopilotStatus?.run));
const activeRunStatus = computed(() => String(activeRun.value.status || ""));
const observedTask = computed(() => app.agentObservability?.active_task || null);
const observedEvents = computed(() => (app.agentObservability?.recent_events || []).slice(-4).reverse());
const deliveryReady = computed(() => String(props.delivery?.status || "") === "ready");
const progressParts = computed(() => asList<Record<string, unknown>>(props.progress?.parts));
const progressPercent = computed(() => Number(props.progress?.overall_percent));
const progressCalibrated = computed(() => String(props.progress?.status || "") === "calibrated");
const deliveryFiles = computed(() => asList<Record<string, unknown>>(props.delivery?.files));
const deliveryPreparing = ref(false);
const deliveryMessage = ref("");

function statusLabel(status: string): string {
  return ({ formal: "已晋升", current: "正在推进", blocked: "需要处理", alternative: "候选分支", memory: "已写回" } as Record<string, string>)[status] || "已登记";
}

function runStatusLabel(status: string): string {
  return ({ running: "正在执行", paused: "等待继续", blocked: "等待处理", failed: "本轮停止", complete: "本轮完成" } as Record<string, string>)[status] || "等待任务";
}

function choiceOptions(choice: Record<string, unknown>): Record<string, unknown>[] {
  return asList<Record<string, unknown>>(choice.options).slice(0, 2);
}

function deliveryFileLabel(file: Record<string, unknown>): string {
  const path = String(file.path || "");
  return String(file.name || path.split("/").at(-1) || "正式交付文件");
}

function deliveryFileMeta(file: Record<string, unknown>): string {
  const format = String(file.format || String(file.path || "").split(".").at(-1) || "文件").toUpperCase();
  const size = Number(file.size || 0);
  if (!size) return format;
  if (size < 1024) return `${format} · ${size} B`;
  if (size < 1024 * 1024) return `${format} · ${Math.round(size / 1024)} KB`;
  return `${format} · ${(size / 1024 / 1024).toFixed(1)} MB`;
}

async function refreshDelivery(): Promise<void> {
  deliveryMessage.value = "";
  try {
    await app.loadDelivery();
  } catch (cause) {
    deliveryMessage.value = cause instanceof Error ? cause.message : "暂时无法刷新交付资料。";
  }
}

async function prepareDelivery(): Promise<void> {
  if (!app.currentProjectPath || deliveryPreparing.value) return;
  deliveryPreparing.value = true;
  deliveryMessage.value = "";
  try {
    const result = await api<Record<string, unknown>>("/worker/run", {
      method: "POST",
      body: JSON.stringify({ project_root: app.currentProjectPath, route: "export-and-release", runtime: "opencode" }),
    });
    deliveryMessage.value = String(result.message || "交付任务已开始；完成后文件会出现在这里。");
    await Promise.allSettled([app.loadDelivery(), app.loadDashboard(), app.loadAgentObservability(), app.loadAutopilotStatus()]);
  } catch (cause) {
    deliveryMessage.value = cause instanceof Error ? cause.message : "暂时无法准备交付。";
  } finally {
    deliveryPreparing.value = false;
  }
}

async function downloadDelivery(file: Record<string, unknown>): Promise<void> {
  const path = String(file.path || "");
  if (!path || !app.currentProjectPath) return;
  deliveryMessage.value = "";
  try {
    const response = await authorizedFetch(`/project/delivery/download?${query({ project_root: app.currentProjectPath, path })}`);
    if (!response.ok) throw new Error(`下载失败（${response.status}）`);
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = deliveryFileLabel(file);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  } catch (cause) {
    deliveryMessage.value = cause instanceof Error ? cause.message : "暂时无法下载交付文件。";
  }
}

function archiveFor(node: SpatialNarrativeProjection["nodes"][number]): Record<string, unknown> | null {
  const section = ({ character: "characters", canon: "world", scene: "scenes", branch: "branches", review: "reviews" } as Record<string, string>)[node.type];
  if (!section) return null;
  const entries = asList<Record<string, unknown>>(librarySections.value[section]);
  return entries.find((entry) => String(entry.id || entry.scene_id || "") === node.source_id)
    || entries.find((entry) => String(entry.title || "") === node.label)
    || null;
}

function handleShortcut(event: KeyboardEvent): void {
  const target = event.target as HTMLElement | null;
  if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
  if (event.key === "Escape") {
    windows.closeActive();
    event.preventDefault();
    return;
  }
  if (!event.altKey || event.ctrlKey || event.metaKey) return;
  if (event.key.toLowerCase() === "m") {
    windows.toggleActive();
    event.preventDefault();
  } else if (event.key.toLowerCase() === "r") {
    windows.resetActive();
    event.preventDefault();
  } else if (event.key === "Tab") {
    const id = windows.focusNext();
    if (id) document.querySelector<HTMLElement>(`[data-spatial-window-id="${CSS.escape(id)}"]`)?.focus();
    event.preventDefault();
  }
}

onMounted(() => window.addEventListener("keydown", handleShortcut));
onBeforeUnmount(() => window.removeEventListener("keydown", handleShortcut));
</script>

<template>
  <div class="spatial-window-layer" aria-label="打开的叙事仪表">
    <SpatialWindowFrame
      v-for="item in windows.expandedWindows"
      :key="item.id"
      :item="item"
      @activate="windows.bringForward(item.id)"
      @move="windows.updatePosition(item.id, $event)"
      @resize="windows.updateSize(item.id, $event)"
      @toggle="windows.toggleCollapsed(item.id)"
      @reset="windows.resetPosition(item.id)"
      @close="windows.close(item.id)"
    >
      <template v-if="item.kind === 'node' && item.node">
        <div class="spatial-node-window" :data-status="item.node.status">
          <SafeMarkdown class="spatial-node-subtitle" :source="item.node.subtitle || '这个节点来自已经进入正式项目的作品事实。'" />
          <dl class="spatial-node-metrics">
            <div><dt>类型</dt><dd>{{ item.node.type }}</dd></div><div><dt>状态</dt><dd>{{ statusLabel(item.node.status) }}</dd></div>
            <div v-if="item.node.metrics.word_target"><dt>目标</dt><dd>{{ item.node.metrics.word_target.toLocaleString() }} 字</dd></div>
            <div v-if="item.node.metrics.formal_chars"><dt>正文</dt><dd>{{ item.node.metrics.formal_chars.toLocaleString() }} 字</dd></div>
          </dl>
          <section v-if="archiveFor(item.node)" class="spatial-archive-preview"><header><BookOpenText :size="14" /><strong>{{ archiveFor(item.node)?.subtitle || '作品档案摘录' }}</strong></header><SafeMarkdown :source="archiveFor(item.node)?.excerpt || archiveFor(item.node)?.body || ''" /><ul v-if="asList(archiveFor(item.node)?.key_points).length"><li v-for="point in asList(archiveFor(item.node)?.key_points).slice(0, 3)" :key="String(point)">{{ point }}</li></ul></section>
          <section class="spatial-node-relations"><header><Route :size="14" /><strong>它正在影响什么</strong></header><p v-if="!item.detail">正在读取这段作品关系……</p><ul v-else-if="item.detail.relationships.length"><li v-for="edge in item.detail.relationships.slice(0, 5)" :key="`${edge.source}-${edge.target}-${edge.type}`"><span>{{ edge.type }}</span><p>{{ edge.source }} <ArrowUpRight :size="12" /> {{ edge.target }}</p></li></ul><p v-else>暂时还没有可见的关联记录。</p></section>
            <div class="spatial-window-commands"><button class="primary-button wide" @click="emit('focusNode', item.node!.node_id)"><Focus :size="15" />聚焦这一段</button><button v-if="item.node.type === 'task'" class="text-button" @click="windows.openInstrument('progress')"><ScanSearch :size="15" />查看推进任务</button><button v-else-if="item.node.status === 'formal'" class="text-button" @click="windows.openInstrument('reader')"><BookOpenText :size="15" />阅读正式正文</button></div>
        </div>
      </template>
      <template v-else-if="item.kind === 'progress'">
        <div class="spatial-progress-window">
          <header class="progress-signal" :data-status="activeRunStatus || 'waiting'">
            <span class="progress-signal-orb"><Activity :size="16" /></span>
            <div><small>当前执行信号</small><strong>{{ runStatusLabel(activeRunStatus) }}</strong></div>
            <i v-if="activeRunStatus === 'running'">LIVE</i>
          </header>
          <div class="progress-body">
            <span class="instrument-overline">PROJECT MOTION</span>
            <strong class="instrument-number">{{ formalChars.toLocaleString() }} <small>字</small></strong>
            <p>{{ observedTask?.message || currentTask.label || currentTask.title || '当前没有等待执行的正式任务；作品仍会保留全部路线证据。' }}</p>
            <section class="progress-scroll" :class="{ 'is-calibrated': progressCalibrated }">
              <header><span>作品总体进度</span><strong>{{ progressCalibrated ? `${progressPercent.toFixed(1)}%` : '待校准' }}</strong></header>
              <div class="progress-scroll-track"><i v-for="part in progressParts" :key="String(part.id)" :style="{ height: `${Number(part.percent || 0)}%` }" :data-part="part.id"></i></div>
              <ul><li v-for="part in progressParts" :key="String(part.id)"><span>{{ part.label }}</span><strong>{{ part.percent === null ? '待定' : `${Number(part.percent).toFixed(0)}%` }}</strong></li></ul>
            </section>
            <dl class="progress-run-facts">
              <div><dt>路线</dt><dd>{{ observedTask?.route || activeRun.current_route || currentTask.route || '等待下一步' }}</dd></div>
              <div><dt>已完成</dt><dd>{{ Number(observedTask?.tasks_completed || activeRun.tasks_completed || 0) }} 项</dd></div>
              <div><dt>节点</dt><dd>{{ projection?.summary.node_count || 0 }}</dd></div>
            </dl>
            <section v-if="observedTask || observedEvents.length" class="agent-pulse"><header><span><Activity :size="14" />{{ observedTask?.role || '执行观察' }}</span><small>{{ observedTask?.stage || '等待新的任务事件' }}</small></header><ol v-if="observedEvents.length"><li v-for="event in observedEvents" :key="event.sequence"><i></i><div><strong>{{ event.stage }}</strong><p>{{ event.message }}</p></div></li></ol></section>
            <p v-if="activeRun.last_error" class="progress-warning">{{ activeRun.last_error }}</p>
            <button class="primary-button wide" @click="emit('advance')"><PauseCircle v-if="['paused', 'blocked', 'failed'].includes(activeRunStatus)" :size="15" /><PlayCircle v-else :size="15" />{{ activeRunStatus === 'running' ? '正在观察这项推进' : (activeRunStatus ? '继续这一轮任务' : '启动下一项任务') }}</button>
          </div>
        </div>
      </template>
      <template v-else-if="item.kind === 'reader'">
        <ManuscriptReader :items="props.prose" compact immersive />
      </template>
      <template v-else-if="item.kind === 'health'">
        <div class="spatial-instrument-content"><span class="instrument-overline">WORK HEALTH</span><strong class="instrument-title">正式路线检查</strong><p>健康仪表会把缺少的证据和阻塞项归还到可理解的创作语言中。</p><div class="spatial-health-list"><article v-for="audit in routeAudits.slice(0, 6)" :key="String(audit.route)"><i :class="Number(audit.blocking_count || 0) ? 'blocked' : 'ready'"></i><div><strong>{{ labelFor(audit.route) }}</strong><p v-if="Number(audit.blocking_count || 0)">{{ describeGate(asRecord(asList(audit.top_blocking_gates)[0]).message) }}</p><p v-else>已具备继续推进条件。</p></div></article><span v-if="!routeAudits.length"><CircleAlert :size="15" />等待项目健康数据。</span></div></div>
      </template>
      <template v-else-if="item.kind === 'delivery'">
        <div class="spatial-delivery-window" :class="{ ready: deliveryReady }">
          <div class="spatial-delivery-heading">
            <div class="delivery-seal"><FileCheck2 :size="24" /><i></i></div>
            <div><span class="instrument-overline">DELIVERY PROOF</span><strong>{{ deliveryReady ? '交付条件已满足' : '交付仍在准备中' }}</strong></div>
            <button class="orrery-v3-icon" title="刷新交付状态" @click="refreshDelivery"><RefreshCw :size="14" /></button>
          </div>
          <p>{{ deliveryReady ? '正式正文与证据可被收束为阅读和发布文件。' : '完成正文、审查、状态写回与导出门禁后，交付信标会亮起。' }}</p>
          <ul v-if="!deliveryReady && asList(delivery?.blockers).length" class="delivery-blockers"><li v-for="blocker in asList<Record<string, unknown>>(delivery?.blockers).slice(0, 3)" :key="String(blocker.code || blocker.message)">{{ blocker.message || blocker.code }}</li></ul>
          <section v-else-if="deliveryFiles.length" class="spatial-delivery-files" aria-label="可下载的交付文件">
            <button v-for="file in deliveryFiles.slice(0, 4)" :key="String(file.path)" class="spatial-delivery-file" @click="downloadDelivery(file)"><FileCheck2 :size="14" /><span><strong>{{ deliveryFileLabel(file) }}</strong><small>{{ deliveryFileMeta(file) }}</small></span><Download :size="14" /></button>
          </section>
          <div class="spatial-delivery-actions">
            <button class="primary-button" :disabled="!deliveryReady || deliveryPreparing" @click="prepareDelivery"><PackageOpen :size="14" />{{ deliveryPreparing ? '正在准备' : '准备交付' }}</button>
            <button v-if="deliveryFiles.length" class="text-button" @click="downloadDelivery(deliveryFiles[0])"><Download :size="14" />下载主文件</button>
          </div>
          <small v-if="deliveryMessage" class="spatial-delivery-message">{{ deliveryMessage }}</small>
        </div>
      </template>
      <template v-else-if="item.kind === 'decisions'">
        <div class="spatial-decision-window"><header><span class="instrument-overline">HUMAN CHOICE</span><strong class="instrument-title">由你决定的创作分岔</strong></header><div v-if="choices.length" class="spatial-decision-list"><article v-for="choice in choices" :key="String(choice.choice_id || choice.id)"><GitBranch :size="16" /><div><span v-if="choice.recommended" class="decision-recommendation">建议方向</span><strong>{{ choice.title || choice.prompt || '创作方向选择' }}</strong><SafeMarkdown :source="choice.summary || choice.description || '查看候选方向和它对后续创作的影响。'" /><ul v-if="choiceOptions(choice).length"><li v-for="option in choiceOptions(choice)" :key="String(option.id)">{{ option.label || option.id }}</li></ul></div><button class="text-button" @click="emit('choose', choice)">比较</button></article></div><p v-else>当前没有需要你决定的分支、设定或修订方向。正在运行的任务会出现在“推进”中，不会被误当成人工选择。</p></div>
      </template>
      <template v-else-if="item.kind === 'rules'">
        <div class="spatial-rules-window"><div class="spatial-instrument-content"><span class="instrument-overline">NARRATIVE CONSTRAINTS</span><strong class="instrument-title">创作规则与叙事呼吸</strong><p>文风、Canon、字数预算、标点与表达规则会写入正式任务包，并在审查与晋升前复核。</p><div class="rule-signal-grid"><span :class="{ ready: Number(libraryCounts.style || 0) > 0 }">文风挂载 <b>{{ Number(libraryCounts.style || 0) > 0 ? '已就绪' : '待补齐' }}</b></span><span :class="{ ready: Number(libraryCounts.word_budget || 0) > 0 }">字数预算 <b>{{ Number(libraryCounts.word_budget || 0) > 0 ? '已就绪' : '待补齐' }}</b></span><span :class="{ ready: Number(libraryCounts.rhythm || 0) > 0 }">节奏合同 <b>{{ Number(libraryCounts.rhythm || 0) > 0 ? '已就绪' : '待补齐' }}</b></span></div></div><QualityView instrument /></div>
      </template>
      <template v-else>
        <div class="spatial-instrument-content"><span class="instrument-overline">COMING INTO VIEW</span><strong class="instrument-title">{{ item.title }}</strong><p>这个仪表正在迁入新的空间工作台；它不会替代任何正式流程。</p></div>
      </template>
    </SpatialWindowFrame>
    <nav v-if="windows.minimizedWindows.length" class="spatial-minimized-rail" aria-label="已收起的仪表窗口">
      <span>已收起 {{ windows.minimizedWindows.length }}</span>
      <button v-for="item in windows.minimizedWindows" :key="item.id" :title="`恢复 ${item.title}`" @click="windows.restore(item.id)">{{ item.title }}</button>
    </nav>
  </div>
</template>
