<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Bot, CircleCheck, CirclePause, Gauge, Pause, Play, RefreshCw, ShieldAlert, Sparkles, Timer, Wrench } from "lucide-vue-next";
import { api, connectEventStream, query, type EventStreamConnection } from "@/services/api";
import { friendlyError, useAppStore } from "@/stores/app";
import type { AutopilotMode, AutopilotRun, AutopilotStatus, DelegationPolicy } from "@/types/api";

const props = withDefaults(defineProps<{ compact?: boolean }>(), { compact: false });
const store = useAppStore();
const snapshot = ref<AutopilotStatus | null>(null);
const busy = ref(false);
const authorized = ref(false);
const liveStage = ref("等待开始");
const liveDetail = ref("ArcVellum 会在这里显示真实推进阶段。 ");
const lastActivityAt = ref("");
const repairCount = ref(0);
const tick = ref(Date.now());
const streamStartedAt = ref(0);
const renewalLimits = ref({ max_tasks: 500, max_runtime_hours: 24, max_consecutive_revisions: 3, max_failures_per_task: 2, max_cost: 100 });
let events: EventStreamConnection | null = null;
let clock = 0;

const run = computed(() => snapshot.value?.run || null);
const running = computed(() => run.value?.status === "running");
const mode = computed(() => snapshot.value?.policy.mode || "collaborative");
const authorizationLimit = computed(() => {
  const reason = String(run.value?.stop_reason || "");
  return ["task-limit", "runtime-limit", "cost-limit", "revision-limit", "authorization-expired"].includes(reason) ? reason : "";
});
const authorizationLimitText = computed(() => ({
  "task-limit": "本轮完成任务数已达到你的授权上限。",
  "runtime-limit": "本轮连续运行时长已达到你的授权上限。",
  "cost-limit": "本轮预估费用已达到你的授权上限。",
  "revision-limit": "连续修订次数已达到你的授权上限。",
  "authorization-expired": "本轮授权已到期。",
} as Record<string, string>)[authorizationLimit.value] || "");
const elapsedText = computed(() => {
  tick.value;
  const started = streamStartedAt.value;
  if (!started || !running.value) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - started) / 1000));
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} 分 ${seconds % 60} 秒`;
});
const statusText = computed(() => {
  if (!run.value) return "还没有开始连续创作";
  if (run.value.status === "running") return "作品正在持续向前推进";
  if (run.value.status === "complete") return "完整作品已经交付";
  if (run.value.status === "paused") return run.value.last_error || "已暂停，等待你的决定";
  return run.value.last_error || "遇到需要处理的问题";
});

const modes: Array<{ id: AutopilotMode; title: string; text: string }> = [
  { id: "collaborative", title: "一起创作", text: "每个重要选择都由你决定，ArcVellum 负责准备和检查。" },
  { id: "supervised_auto", title: "监督创作", text: "顾问处理日常取舍，冲突和最终发布仍会等你。" },
  { id: "full_auto", title: "全自动交付", text: "授权后持续推进到完整作品，触发质量红线会自动停下。" },
];

onMounted(() => {
  clock = window.setInterval(() => (tick.value = Date.now()), 1000);
  void load();
});
watch(() => store.currentProjectPath, load);
onBeforeUnmount(() => {
  stopStream();
  window.clearInterval(clock);
});

async function load(): Promise<void> {
  stopStream();
  snapshot.value = null;
  if (!store.currentProjectPath) return;
  try {
    snapshot.value = await api<AutopilotStatus>(`/autopilot/status?${query({ project_root: store.currentProjectPath })}`);
    syncRenewalLimits();
    store.setAutopilotStatus(snapshot.value);
    if (snapshot.value.run?.status === "running") startStream(snapshot.value.run.run_id);
  } catch (cause) {
    store.error = friendlyError(cause, "暂时无法读取连续创作状态。");
  }
}

function syncRenewalLimits(): void {
  const limits = snapshot.value?.policy.limits;
  if (!limits) return;
  renewalLimits.value = {
    max_tasks: Number(limits.max_tasks || 500),
    max_runtime_hours: Number(limits.max_runtime_hours || 24),
    max_consecutive_revisions: Number(limits.max_consecutive_revisions || 3),
    max_failures_per_task: Number(limits.max_failures_per_task || 2),
    max_cost: Number(limits.max_cost || 0),
  };
}

async function selectMode(next: AutopilotMode): Promise<void> {
  if (!snapshot.value || running.value || busy.value) return;
  busy.value = true;
  try {
    const policy: DelegationPolicy = {
      ...snapshot.value.policy,
      mode: next,
      delegated_decisions: next === "collaborative" ? [] : [
        "branch_selection", "style_mount", "revision_direction", "budget_expansion",
        "asset_approval", "canon_patch_approval", "state_patch_confirmation",
      ],
      release_policy: next === "full_auto" ? "delegated" : "require_user",
    };
    await api("/autopilot/policy", {
      method: "PUT",
      body: JSON.stringify({ project_root: store.currentProjectPath, policy }),
    });
    authorized.value = false;
    await load();
  } catch (cause) {
    store.error = friendlyError(cause, "暂时无法更改创作模式。");
  } finally {
    busy.value = false;
  }
}

async function start(): Promise<void> {
  if (!store.currentProjectPath || busy.value || (mode.value === "full_auto" && !authorized.value)) return;
  busy.value = true;
  try {
    const result = await api<{ run: AutopilotRun }>("/autopilot/start", {
      method: "POST",
      body: JSON.stringify({ project_root: store.currentProjectPath, runtime: "opencode", authorized: mode.value !== "full_auto" || authorized.value }),
    });
    if (snapshot.value) snapshot.value.run = result.run;
    store.setAutopilotRun(result.run);
    startStream(result.run.run_id);
  } catch (cause) {
    store.error = friendlyError(cause, "连续创作暂时无法启动。");
  } finally {
    busy.value = false;
  }
}

async function pause(): Promise<void> {
  if (!run.value || busy.value) return;
  busy.value = true;
  try {
    const result = await api<{ run: AutopilotRun }>(`/autopilot/runs/${run.value.run_id}/pause`, {
      method: "POST",
      body: JSON.stringify({ reason: "user-request" }),
    });
    if (snapshot.value) snapshot.value.run = result.run;
    store.setAutopilotRun(result.run);
    stopStream();
  } finally {
    busy.value = false;
  }
}

async function resume(): Promise<void> {
  if (!run.value || busy.value) return;
  busy.value = true;
  try {
    const result = await api<{ run: AutopilotRun }>(`/autopilot/runs/${run.value.run_id}/resume`, { method: "POST" });
    if (snapshot.value) snapshot.value.run = result.run;
    store.setAutopilotRun(result.run);
    startStream(result.run.run_id);
  } catch (cause) {
    store.error = friendlyError(cause, "暂时无法继续创作。");
  } finally {
    busy.value = false;
  }
}

async function renewAuthorization(): Promise<void> {
  if (!snapshot.value || !run.value || busy.value) return;
  busy.value = true;
  try {
    const policy: DelegationPolicy = {
      ...snapshot.value.policy,
      limits: {
        max_tasks: Math.max(1, Math.trunc(renewalLimits.value.max_tasks || 1)),
        max_runtime_hours: Math.max(0.1, Number(renewalLimits.value.max_runtime_hours || 0.1)),
        max_consecutive_revisions: Math.max(1, Math.trunc(renewalLimits.value.max_consecutive_revisions || 1)),
        max_failures_per_task: Math.max(0, Math.trunc(renewalLimits.value.max_failures_per_task || 0)),
        max_cost: Math.max(0, Number(renewalLimits.value.max_cost || 0)),
      },
    };
    const saved = await api<{ policy: DelegationPolicy; run?: AutopilotRun }>("/autopilot/policy", {
      method: "PUT",
      body: JSON.stringify({ project_root: store.currentProjectPath, policy }),
    });
    snapshot.value.policy = saved.policy;
    const result = await api<{ run: AutopilotRun }>(`/autopilot/runs/${run.value.run_id}/resume`, { method: "POST" });
    snapshot.value.run = result.run;
    store.setAutopilotRun(result.run);
    startStream(result.run.run_id);
  } catch (cause) {
    store.error = friendlyError(cause, "新的授权范围暂时无法生效。");
  } finally {
    busy.value = false;
  }
}

function startStream(runId: string): void {
  stopStream();
  streamStartedAt.value = Date.now();
  lastActivityAt.value = "";
  events = connectEventStream(`/autopilot/runs/${encodeURIComponent(runId)}/stream`, (event, data) => {
    if (event === "autopilot.status") {
      const payload = data as unknown as { run: AutopilotRun };
      if (snapshot.value) snapshot.value.run = payload.run;
      store.setAutopilotRun(payload.run);
      lastActivityAt.value = new Date().toISOString();
      if (["complete", "paused", "blocked", "cancelled", "failed"].includes(payload.run.status)) {
        stopStream();
        void store.refreshWorkspace();
      }
      return;
    }
    const envelope = data as unknown as { at?: string; data?: Record<string, unknown> };
    applyWorkerActivity(event, envelope.data || (data as Record<string, unknown>));
    lastActivityAt.value = envelope.at || new Date().toISOString();
  });
}

function applyWorkerActivity(event: string, data: Record<string, unknown>): void {
  const stages: Record<string, [string, string]> = {
    "worker.task.opened": ["正在理解任务", "已领取当前路线的正式任务和约束。"],
    "worker.sandbox.prepared": ["正在准备资料", "已建立隔离工作区，只允许写入本次产物。"],
    "worker.core.command_started": ["正在整理确定性资料", "先由文学内核准备结构和检查依据。"],
    "worker.runner.process.started": ["创作能力已就绪", data.reused ? "复用已连接的 Agent，开始本次工作。" : "Agent 已连接，开始本次工作。"],
    "worker.runner.session.started": ["正在思考与创作", "模型已经收到完整任务合同。"],
    "worker.runner.first_event": ["已经开始产出", "Agent 正在读取资料并形成结果。"],
    "worker.tool.started": toolStage(data),
    "worker.validation.started": ["正在检查成果", "先做格式、范围与门禁预检。"],
    "worker.validation.canonicalized": ["正在整理交付格式", "只校准机器门禁标记，不改变 Agent 的判断结论。"],
    "worker.validation.failed": ["正在纠正问题", "预检发现了可修复问题，Agent 会在当前上下文中修改。"],
    "worker.repair.started": ["正在同会话修订", `第 ${Number(data.attempt || 1)} 次修订，不会重新开始整项任务。`],
    "worker.repair.completed": ["修订已完成", "正在重新执行确定性预检。"],
    "worker.writeback.preview_ready": ["成果等待写回", "候选差异已经准备好，尚未改变正式作品。"],
    "worker.file.imported": ["正在写入正式项目", "已通过策略确认，正在交给文学内核验收。"],
    "worker.validation.passed": ["检查已经通过", "当前阶段的确定性门禁已确认。"],
    "task.recovery_started": ["正在接管已有成果", "上一轮虽已超时，ArcVellum 会先检查现有产物，不从头重写。"],
    "task.recovery_succeeded": ["已有成果已恢复", "有效产物已经通过预检，正在继续正式写回。"],
    "task.recovery_rejected": ["已有成果还不完整", "只在无法安全接管时才会重新执行当前任务。"],
  };
  const value = stages[event];
  if (!value) return;
  liveStage.value = value[0];
  liveDetail.value = value[1];
  if (event === "worker.repair.started") repairCount.value = Math.max(repairCount.value, Number(data.attempt || 1));
}

function toolStage(data: Record<string, unknown>): [string, string] {
  const tool = String(data.tool || data.name || "").toLowerCase();
  if (tool.includes("read") || tool.includes("glob") || tool.includes("list") || tool.includes("search")) {
    return ["正在阅读任务资料", "Agent 正在隔离工作区内核对本次允许读取的作品信息。"];
  }
  if (tool.includes("write") || tool.includes("edit") || tool.includes("patch")) {
    return ["正在写入候选成果", "所有改动仍停留在隔离工作区。"];
  }
  return ["正在执行当前步骤", "Agent 正在使用任务允许的工具推进产物。"];
}

function stopStream(): void {
  events?.close();
  events = null;
}

function routeText(route: string): string {
  const labels: Record<string, string> = {
    "source-ingest": "整理已有素材",
    "longform-planning": "规划全书结构",
    "style-engineering": "校准叙事文风",
    "character-and-world-assets": "完善人物与世界",
    "scene-development": "推演并创作正文",
    "review-and-audit": "审读全书质量",
    "export-and-release": "整理正式交付",
  };
  return labels[route] || "准备下一步";
}
</script>

<template>
  <section class="autopilot-panel" :class="{ compact: props.compact }">
    <header>
      <div><span class="eyebrow">创作模式</span><h2>你想怎样和 ArcVellum 一起写</h2></div>
      <span class="autopilot-state" :data-state="run?.status || 'idle'">
        <i></i>{{ running ? "正在创作" : run?.status === "complete" ? "已交付" : "待命" }}
      </span>
    </header>

    <div class="mode-selector">
      <button v-for="item in modes" :key="item.id" :class="{ active: mode === item.id }" :disabled="running" @click="selectMode(item.id)">
        <Bot v-if="item.id === 'full_auto'" :size="18" />
        <Sparkles v-else-if="item.id === 'supervised_auto'" :size="18" />
        <CircleCheck v-else :size="18" />
        <span><strong>{{ item.title }}</strong><small>{{ item.text }}</small></span>
      </button>
    </div>

    <section v-if="authorizationLimit && !running" class="autopilot-renewal-urgent" aria-live="polite">
      <div><ShieldAlert :size="16" /><span><small>授权窗口已暂停</small><strong>{{ authorizationLimitText }}</strong></span></div>
      <button class="secondary-button" :disabled="busy" @click="renewAuthorization"><RefreshCw :size="15" />按当前范围续期并继续</button>
    </section>

    <div class="autopilot-console">
      <div class="autopilot-progress-mark" :class="run?.status || 'idle'">
        <Gauge v-if="running" :size="25" />
        <CirclePause v-else-if="run?.status === 'paused'" :size="25" />
        <CircleCheck v-else :size="25" />
      </div>
      <div class="autopilot-copy">
        <span>{{ running ? routeText(run?.current_route || '') : '当前状态' }}</span>
        <strong>{{ running ? liveStage : statusText }}</strong>
        <p v-if="running">{{ liveDetail }}</p>
        <small v-if="run">已经完成 {{ run.tasks_completed }} 项创作任务 · 预计费用 ${{ run.estimated_cost.toFixed(2) }}</small>
        <small v-else>你可以随时暂停、改变方向，再从原处继续。</small>
      </div>
      <div class="autopilot-controls">
        <button v-if="running" class="secondary-button" :disabled="busy" @click="pause"><Pause :size="16" />暂停</button>
        <button v-else-if="run && run.status !== 'complete'" class="primary-button" :disabled="busy" @click="resume"><RefreshCw :size="16" />继续</button>
        <button v-else-if="run?.status !== 'complete'" class="primary-button" :disabled="busy || (mode === 'full_auto' && !authorized)" @click="start"><Play :size="16" />开始</button>
      </div>
    </div>

    <div v-if="running" class="autopilot-live-evidence" aria-live="polite">
      <span><Timer :size="14" />本次连续运行 {{ elapsedText }}</span>
      <span v-if="repairCount"><Wrench :size="14" />自动修订 {{ repairCount }} 次</span>
      <span><i></i>{{ lastActivityAt ? '连接活跃' : '正在建立连接' }}</span>
    </div>

    <label v-if="mode === 'full_auto' && !running && run?.status !== 'complete'" class="autopilot-authorization">
      <input v-model="authorized" type="checkbox" />
      <ShieldAlert :size="16" />
      <span>我授权创作代理处理日常选择并生成最终交付；遇到设定冲突、质量反复失败或预算上限时必须停下。</span>
    </label>
    <section v-if="authorizationLimit && !running" class="autopilot-renewal" aria-live="polite">
      <header><ShieldAlert :size="17" /><div><span>授权需要续期</span><strong>{{ authorizationLimitText }}</strong></div></header>
      <p>这不是系统故障。调整以下范围后，ArcVellum 会把你的新授权写入当前这轮任务，再从暂停点继续。</p>
      <div class="autopilot-renewal-fields">
        <label>最多任务<input v-model.number="renewalLimits.max_tasks" min="1" step="1" type="number" /></label>
        <label>最长运行时数<input v-model.number="renewalLimits.max_runtime_hours" min="0.1" step="0.5" type="number" /></label>
        <label>连续修订上限<input v-model.number="renewalLimits.max_consecutive_revisions" min="1" step="1" type="number" /></label>
        <label>单任务失败上限<input v-model.number="renewalLimits.max_failures_per_task" min="0" step="1" type="number" /></label>
        <label>预算上限（USD，0 为不限制）<input v-model.number="renewalLimits.max_cost" min="0" step="1" type="number" /></label>
      </div>
      <button class="primary-button" :disabled="busy" @click="renewAuthorization"><RefreshCw :size="15" />保存新授权范围并继续</button>
    </section>
  </section>
</template>
