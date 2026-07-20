<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Bot, CircleCheck, CirclePause, Gauge, Pause, Play, RefreshCw, ShieldAlert, Sparkles } from "lucide-vue-next";
import { api, query, sseUrl } from "@/services/api";
import { friendlyError, useAppStore } from "@/stores/app";
import type { AutopilotMode, AutopilotRun, AutopilotStatus, DelegationPolicy } from "@/types/api";

const store = useAppStore();
const snapshot = ref<AutopilotStatus | null>(null);
const busy = ref(false);
const authorized = ref(false);
let events: EventSource | null = null;

const run = computed(() => snapshot.value?.run || null);
const running = computed(() => run.value?.status === "running");
const mode = computed(() => snapshot.value?.policy.mode || "collaborative");
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

onMounted(load);
watch(() => store.currentProjectPath, load);
onBeforeUnmount(stopStream);

async function load(): Promise<void> {
  stopStream();
  snapshot.value = null;
  if (!store.currentProjectPath) return;
  try {
    snapshot.value = await api<AutopilotStatus>(`/autopilot/status?${query({ project_root: store.currentProjectPath })}`);
    if (snapshot.value.run?.status === "running") startStream(snapshot.value.run.run_id);
  } catch (cause) {
    store.error = friendlyError(cause, "暂时无法读取连续创作状态。");
  }
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
      body: JSON.stringify({ project_root: store.currentProjectPath, runtime: "opencode" }),
    });
    if (snapshot.value) snapshot.value.run = result.run;
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
    startStream(result.run.run_id);
  } catch (cause) {
    store.error = friendlyError(cause, "暂时无法继续创作。");
  } finally {
    busy.value = false;
  }
}

function startStream(runId: string): void {
  stopStream();
  events = new EventSource(sseUrl(`/autopilot/runs/${encodeURIComponent(runId)}/stream`));
  events.addEventListener("autopilot.status", (event) => {
    const payload = JSON.parse((event as MessageEvent).data) as { run: AutopilotRun };
    if (snapshot.value) snapshot.value.run = payload.run;
    if (["complete", "paused", "blocked", "cancelled", "failed"].includes(payload.run.status)) {
      stopStream();
      void store.refreshWorkspace();
    }
  });
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
  <section class="autopilot-panel">
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

    <div class="autopilot-console">
      <div class="autopilot-progress-mark" :class="run?.status || 'idle'">
        <Gauge v-if="running" :size="25" />
        <CirclePause v-else-if="run?.status === 'paused'" :size="25" />
        <CircleCheck v-else :size="25" />
      </div>
      <div class="autopilot-copy">
        <span>{{ running ? routeText(run?.current_route || '') : '当前状态' }}</span>
        <strong>{{ statusText }}</strong>
        <small v-if="run">已经完成 {{ run.tasks_completed }} 项创作任务 · 预计费用 ${{ run.estimated_cost.toFixed(2) }}</small>
        <small v-else>你可以随时暂停、改变方向，再从原处继续。</small>
      </div>
      <div class="autopilot-controls">
        <button v-if="running" class="secondary-button" :disabled="busy" @click="pause"><Pause :size="16" />暂停</button>
        <button v-else-if="run && run.status !== 'complete'" class="primary-button" :disabled="busy" @click="resume"><RefreshCw :size="16" />继续</button>
        <button v-else-if="run?.status !== 'complete'" class="primary-button" :disabled="busy || (mode === 'full_auto' && !authorized)" @click="start"><Play :size="16" />开始</button>
      </div>
    </div>

    <label v-if="mode === 'full_auto' && !running && run?.status !== 'complete'" class="autopilot-authorization">
      <input v-model="authorized" type="checkbox" />
      <ShieldAlert :size="16" />
      <span>我授权创作代理处理日常选择并生成最终交付；遇到设定冲突、质量反复失败或预算上限时必须停下。</span>
    </label>
  </section>
</template>
