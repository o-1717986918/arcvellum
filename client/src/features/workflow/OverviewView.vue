<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ArrowRight, CircleAlert, CircleCheck, Clock3, Eye, EyeOff, Image, Maximize2, Minimize2, Palette, Play, Route, X } from "lucide-vue-next";
import ManuscriptReader from "@/components/ManuscriptReader.vue";
import AutopilotPanel from "@/components/AutopilotPanel.vue";
import ImmersiveConsole from "@/components/ImmersiveConsole.vue";
import StoryTrace from "@/components/StoryTrace.vue";
import { api, query } from "@/services/api";
import { asList, asRecord, describeGate, describeWorkflowAction, formatCount, labelFor, manuscriptItems, targetLabel, workflowStepLabel } from "@/services/presentation";
import { backgroundForTheme, normalizeInstrumentVisibility, normalizeOrreryBackground, normalizeOrreryMode, normalizeOrreryTheme, type OrreryBackground, type OrreryMode, type OrreryTheme } from "@/services/orreryPreferences";
import { useAppStore } from "@/stores/app";
import type { ImmersivePanel } from "@/types/immersive";

const store = useAppStore();
const choices = ref<Record<string, unknown>[]>([]);
const working = ref(false);
const actionMessage = ref("");
const narrow = window.matchMedia("(max-width: 760px)").matches;
const mode = ref<OrreryMode>(normalizeOrreryMode(localStorage.getItem("arcvellum.orreryMode"), narrow));
const background = ref<OrreryBackground>(normalizeOrreryBackground(localStorage.getItem("arcvellum.orreryBackground")));
const theme = ref<OrreryTheme>(normalizeOrreryTheme(localStorage.getItem("arcvellum.visualTheme")));
const instrumentsVisible = ref(normalizeInstrumentVisibility(localStorage.getItem("arcvellum.orreryInstruments")));
const immersivePanels = ref<ImmersivePanel[]>([]);
const selectedChoice = ref<Record<string, unknown> | null>(null);
const choiceRationale = ref("");
const choiceBusy = ref(false);
const immersive = computed(() => mode.value === "immersive");

const dashboard = computed(() => (store.dashboard || null) as Record<string, unknown> | null);
const summary = computed(() => asRecord(dashboard.value?.summary));
const routeAudits = computed(() => asList<Record<string, unknown>>(dashboard.value?.route_audits));
const nextActions = computed(() => asList<Record<string, unknown>>(dashboard.value?.next_actions));
const prose = computed(() => manuscriptItems((store.library || null) as Record<string, unknown> | null));
const firstAction = computed(() => nextActions.value[0] || null);
const readyRoutes = computed(() => routeAudits.value.filter((item) => Number(item.blocking_count || 0) === 0).length);
const activeRun = computed(() => {
  const run = store.autopilotStatus?.run || null;
  return run && ["running", "paused", "blocked", "failed"].includes(run.status) ? run : null;
});
const activeRunTitle = computed(() => {
  const labels: Record<string, string> = {
    "source-ingest": "正在整理已有素材",
    "longform-planning": "正在规划全书结构",
    "style-engineering": "正在校准叙事文风",
    "character-and-world-assets": "正在完善人物与世界",
    "scene-development": "正在推演并创作正文",
    "review-and-audit": "正在审读作品质量",
    "export-and-release": "正在整理正式交付",
  };
  return labels[activeRun.value?.current_route || ""] || "正在推进当前创作任务";
});

onMounted(async () => {
  window.addEventListener("arcvellum:orrery-mode", handleGlobalModeRequest as EventListener);
  if (window.matchMedia("(max-width: 760px)").matches) mode.value = "workbench";
  await store.refreshWorkspace();
  await loadChoices();
});
onBeforeUnmount(() => {
  document.documentElement.classList.remove("orrery-immersive");
  window.removeEventListener("arcvellum:orrery-mode", handleGlobalModeRequest as EventListener);
});
watch(mode, (value) => {
  localStorage.setItem("arcvellum.orreryMode", value);
  document.documentElement.classList.toggle("orrery-immersive", value === "immersive");
}, { immediate: true });
watch(background, (value) => localStorage.setItem("arcvellum.orreryBackground", value));
watch(theme, (value, previous) => {
  localStorage.setItem("arcvellum.visualTheme", value);
  document.documentElement.dataset.arcvellumTheme = value;
  if (previous && previous !== value) background.value = backgroundForTheme(value);
}, { immediate: true });
watch(instrumentsVisible, (value) => localStorage.setItem("arcvellum.orreryInstruments", value ? "visible" : "hidden"));

function toggleMode(): void {
  if (!immersive.value && window.matchMedia("(max-width: 760px)").matches) return;
  mode.value = immersive.value ? "workbench" : "immersive";
  if (!immersive.value) immersivePanels.value = [];
}

function handleGlobalModeRequest(event: CustomEvent<OrreryMode>): void {
  mode.value = normalizeOrreryMode(event.detail, narrow);
}


function openChoice(choice: Record<string, unknown>): void {
  selectedChoice.value = choice;
  choiceRationale.value = "";
}

async function submitChoice(option: Record<string, unknown>): Promise<void> {
  if (!store.currentProjectPath || !selectedChoice.value || choiceBusy.value) return;
  choiceBusy.value = true;
  try {
    await api("/workflow/human-choice", {
      method: "POST",
      body: JSON.stringify({
        project_root: store.currentProjectPath,
        choice_id: selectedChoice.value.choice_id,
        route: selectedChoice.value.route,
        task_id: selectedChoice.value.task_id || "",
        decision_type: selectedChoice.value.decision_type,
        target: selectedChoice.value.target || {},
        options: selectedChoice.value.options || [],
        selected: option.id,
        rationale: choiceRationale.value || `用户在 ArcVellum 中确认“${String(option.label || option.id)}”。`,
        actor: "arcvellum-user",
      }),
    });
    selectedChoice.value = null;
    await Promise.all([loadChoices(), store.refreshWorkspace()]);
    store.notice = "你的选择已经进入正式创作流程。";
  } catch (cause) {
    store.error = cause instanceof Error ? cause.message : "暂时无法记录这项选择。";
  } finally {
    choiceBusy.value = false;
  }
}

async function loadChoices(): Promise<void> {
  if (!store.currentProjectPath) return;
  const result: { items?: Record<string, unknown>[]; choices?: Record<string, unknown>[] } = await api<{
    items?: Record<string, unknown>[];
    choices?: Record<string, unknown>[];
  }>(`/workflow/current-choice?${query({ project_root: store.currentProjectPath })}`).catch(() => ({ items: [] }));
  choices.value = result.items || result.choices || [];
}

async function prepareNextTask(): Promise<void> {
  if (!store.currentProjectPath) return;
  working.value = true;
  actionMessage.value = "";
  try {
    const result = await api<Record<string, unknown>>("/worker/run", {
      method: "POST",
      body: JSON.stringify({ project_root: store.currentProjectPath, route: String(firstAction.value?.route || "auto"), runtime: "opencode" }),
    });
    actionMessage.value = result.job_id
      ? "下一项创作任务已经启动，进度会持续显示在活动记录中。"
      : String(result.message || result.status || "下一项创作任务已经启动。");
    await store.loadDashboard();
  } catch (cause) {
    actionMessage.value = cause instanceof Error ? cause.message : "暂时无法启动下一项任务。";
  } finally {
    working.value = false;
  }
}

async function handleActiveRun(): Promise<void> {
  const run = activeRun.value;
  if (!run || working.value) return;
  if (run.status === "running") {
    if (immersive.value && !immersivePanels.value.includes("progress")) {
      immersivePanels.value = ["progress", ...immersivePanels.value];
    } else if (!immersive.value) {
      document.querySelector(".autopilot-panel")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    return;
  }
  working.value = true;
  try {
    const result = await api<{ run: NonNullable<typeof run> }>(`/autopilot/runs/${run.run_id}/resume`, { method: "POST" });
    store.setAutopilotRun(result.run);
    actionMessage.value = "已经从原处继续，实时进度会显示在推进仪表中。";
    if (immersive.value && !immersivePanels.value.includes("progress")) immersivePanels.value = ["progress", ...immersivePanels.value];
  } catch (cause) {
    actionMessage.value = cause instanceof Error ? cause.message : "暂时无法继续当前任务。";
  } finally {
    working.value = false;
  }
}
</script>

<template>
  <div class="overview-view" :class="{ 'is-immersive': immersive, 'instruments-hidden': immersive && !instrumentsVisible, 'console-open': immersive && immersivePanels.length }" :data-orrery-background="background">
    <section class="orrery-hero">
      <StoryTrace :dashboard="dashboard" :immersive="immersive" />

      <div class="orrery-view-tools" aria-label="叙事星仪视图">
        <label title="选择整体观测主题"><Palette :size="15" /><select v-model="theme" aria-label="选择整体观测主题"><option value="moss">苔夜星仪</option><option value="iris">靛紫航图</option><option value="obsidian">黑曜黄铜</option><option value="bookcase">米白书柜</option><option value="modern">冷峻现代</option></select></label>
        <label title="选择星仪背景材质"><Image :size="15" /><select v-model="background" aria-label="选择星仪背景材质"><option value="plain">纯净夜色</option><option value="mineral">绿色矿物星仪</option><option value="iris">靛紫天文制图</option><option value="obsidian">黑曜黄铜机芯</option><option value="bookcase">米白书柜档案</option><option value="modern">冷灰现代观测</option><option value="archive">夜航档案</option><option value="ink">活墨宇宙</option></select></label>
        <button v-if="immersive" class="orrery-icon" :title="instrumentsVisible ? '隐藏边缘仪表' : '显示边缘仪表'" @click="instrumentsVisible = !instrumentsVisible">
          <EyeOff v-if="instrumentsVisible" :size="16" /><Eye v-else :size="16" />
        </button>
        <button class="orrery-icon" :title="immersive ? '返回作品工作台' : '进入沉浸星图'" @click="toggleMode">
          <Minimize2 v-if="immersive" :size="16" /><Maximize2 v-else :size="16" />
        </button>
      </div>

      <div class="orrery-vitals" aria-label="作品状态摘要">
        <div><Route :size="15" /><span>路线</span><strong>{{ readyRoutes }}/{{ routeAudits.length || 0 }}</strong></div>
        <div><Clock3 :size="15" /><span>待办</span><strong>{{ formatCount(summary.pending_task_count) }}</strong></div>
        <div :class="{ alert: Number(summary.blocking_count || 0) }"><CircleAlert :size="15" /><span>补齐</span><strong>{{ formatCount(summary.blocking_count) }}</strong></div>
        <div><CircleCheck :size="15" /><span>正文</span><strong>{{ prose.length }}</strong></div>
      </div>

      <aside class="orrery-now-panel">
        <span class="eyebrow">现在最值得做</span>
        <template v-if="activeRun">
          <span class="route-chip">{{ labelFor(activeRun.current_route) }}</span>
          <h2>{{ activeRunTitle }}</h2>
          <p v-if="activeRun.status === 'running'">这项任务正在真实执行；可打开推进仪表查看读取、创作、修订和验收进度。</p>
          <p v-else>{{ activeRun.last_error || "任务保留在原处，处理完当前问题后可以继续。" }}</p>
          <div class="task-evidence"><span>已完成任务</span><strong>{{ activeRun.tasks_completed }} 项</strong></div>
          <button class="primary-button wide" :disabled="working" @click="handleActiveRun">
            <Play :size="16" />{{ activeRun.status === 'running' ? '查看实时推进' : (working ? '正在继续……' : '继续当前任务') }}<ArrowRight :size="16" />
          </button>
        </template>
        <template v-else-if="firstAction">
          <span class="route-chip">{{ labelFor(firstAction.route) }}</span>
          <h2>{{ targetLabel(firstAction.target) }}</h2>
          <p>{{ describeWorkflowAction(firstAction.next_action) }}</p>
          <div class="task-evidence"><span>当前阶段</span><strong>{{ workflowStepLabel(firstAction.current_step) }}</strong></div>
          <button class="primary-button wide" :disabled="working" @click="prepareNextTask">
            <Play :size="16" />{{ working ? "正在启动……" : "开始下一项任务" }}<ArrowRight :size="16" />
          </button>
        </template>
        <template v-else>
          <span class="completion-seal"><CircleCheck :size="22" /></span>
          <h2>当前没有待办</h2>
          <p>作品路线暂时没有发现需要立刻补齐的环节。</p>
        </template>
        <small v-if="actionMessage" class="action-message">{{ actionMessage }}</small>
      </aside>

      <ImmersiveConsole
        v-if="immersive"
        v-model:open="immersivePanels"
        :choices="choices"
        :prose="prose"
        :route-audits="routeAudits"
        @choose="openChoice"
      />
    </section>

    <div v-if="!immersive" class="overview-support view">
      <header class="overview-support-heading"><div><span class="eyebrow">作品工作区</span><h2>从脉络回到文字与决定</h2></div><div class="overview-heading-actions"><p>这里收纳自动推进、人工选择、正文阅读和路线健康，不与叙事星仪争夺注意力。</p><button class="enter-orrery-button" @click="toggleMode"><Maximize2 :size="17" /><span><strong>进入叙事星仪</strong><small>切换沉浸全景工作台</small></span><ArrowRight :size="15" /></button></div></header>

    <AutopilotPanel />

    <section v-if="choices.length" class="decision-inbox">
      <header><div><span class="eyebrow">等待你的判断</span><h2>几个方向需要你来定</h2></div><span>{{ choices.length }} 项</span></header>
      <div class="decision-row">
        <article v-for="choice in choices.slice(0, 4)" :key="String(choice.choice_id || choice.id)">
          <span>{{ labelFor(choice.kind || choice.choice_type) }}</span>
          <h3>{{ choice.title || choice.prompt || "创作方向选择" }}</h3>
          <p>{{ choice.summary || choice.description || "打开后查看候选方向和影响。" }}</p>
          <button class="text-button" @click="openChoice(choice)">查看选择<ArrowRight :size="15" /></button>
        </article>
      </div>
    </section>

    <ManuscriptReader :items="prose" />

    <section class="route-ledger">
      <header><div><span class="eyebrow">作品健康度</span><h2>每条创作路线是否站得住</h2></div></header>
      <div class="route-table">
        <div v-for="audit in routeAudits" :key="String(audit.route)" class="route-row">
          <span class="route-state" :class="Number(audit.blocking_count || 0) ? 'blocked' : 'ready'"></span>
          <strong>{{ labelFor(audit.route) }}</strong>
          <p v-if="Number(audit.blocking_count || 0)">{{ describeGate(asRecord(asList(audit.top_blocking_gates)[0]).message) }}</p>
          <p v-else>这一条路线已经具备继续推进的条件</p>
          <span>{{ audit.gate_count || 0 }} 项检查</span>
        </div>
      </div>
    </section>
    </div>

    <div v-if="selectedChoice" class="choice-dialog-backdrop" @click.self="selectedChoice = null">
      <section class="choice-dialog" role="dialog" aria-modal="true" :aria-label="String(selectedChoice.title || '创作方向选择')">
        <header><div><span class="eyebrow">这一步由你决定</span><h2>{{ selectedChoice.title || "创作方向选择" }}</h2><p>{{ selectedChoice.summary }}</p></div><button class="icon-button" title="关闭" @click="selectedChoice = null"><X :size="16" /></button></header>
        <div class="choice-options">
          <button
            v-for="option in asList<Record<string, unknown>>(selectedChoice.options)"
            :key="String(option.id)"
            :disabled="choiceBusy"
            @click="submitChoice(option)"
          >
            <span v-if="String(selectedChoice.recommended || '') === String(option.id)">建议</span>
            <strong>{{ option.label || option.id }}</strong>
            <p>{{ option.summary || "采用这个方向继续推进。" }}</p>
          </button>
        </div>
        <label class="choice-rationale">你还可以补一句理由<textarea v-model.trim="choiceRationale" rows="3" maxlength="2000" placeholder="这会成为后续创作判断的依据。"></textarea></label>
      </section>
    </div>
  </div>
</template>
