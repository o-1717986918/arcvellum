<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowRight,
  CheckCircle2,
  CirclePause,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Square,
} from "lucide-vue-next";
import type {
  ArchaeologyState,
  ArchaeologyWorkerEvent,
  ArchaeologyWorkerJob,
} from "../types";

const props = defineProps<{
  state: ArchaeologyState;
  job: ArchaeologyWorkerJob | null;
  events: ArchaeologyWorkerEvent[];
  busy: boolean;
  streamError: string;
}>();

const emit = defineEmits<{
  run: [];
  approve: [];
  reject: [];
  retry: [];
  stop: [];
}>();

const active = computed(() => ["queued", "running", "stopping"].includes(props.job?.status || ""));
const waitingWriteback = computed(() => props.job?.status === "waiting_writeback");
const failed = computed(() => {
  const status = props.job?.status || "";
  return status.includes("failed") || status.startsWith("blocked") || status === "waiting_host_agent";
});

function stepLabel(value: string): string {
  return {
    "source-manifest": "保全来源与结构",
    "chunk-extraction-agent-task": "逐块理解人物、事件与设定",
    "archaeology-fan-in": "汇合全书证据",
    "archaeology-resolution-agent-task": "解析身份、别名与冲突",
    "archaeology-reconstruction-agent-task": "重建候选项目",
    "archaeology-domain-review-agent-task": "分领域复核",
    "archaeology-materialize": "写入档案候选区",
    ready: "作品整理完成",
  }[value] || "准备下一项整理任务";
}

function statusLabel(value: string): string {
  return {
    queued: "排队等待",
    running: "Agent 正在整理",
    stopping: "正在安全停止",
    complete: "当前步骤已完成",
    route_ready: "全部整理完成",
    waiting_writeback: "等待确认写回",
    waiting_host_agent: "需要更换 Agent",
    runtime_failed: "Agent 连接失败",
    blocked_by_core_gate: "资料未通过校验",
    failed: "任务没有完成",
  }[value] || "等待开始";
}

function eventLabel(value: string): string {
  if (value.includes("sandbox")) return "已建立隔离工作区";
  if (value.includes("runtime")) return "Agent 正在理解资料";
  if (value.includes("preflight")) return "正在核对候选产物";
  if (value.includes("writeback")) return "正在准备安全写回";
  if (value.includes("task")) return "正式任务已领取";
  return "任务状态已更新";
}
</script>

<template>
  <section class="archaeology-extraction-console" :data-active="active">
    <div class="archaeology-task-signal">
      <LoaderCircle v-if="active" :size="21" />
      <CheckCircle2 v-else-if="state.status === 'ready'" :size="21" />
      <CirclePause v-else :size="21" />
    </div>
    <div class="archaeology-task-copy">
      <span>{{ statusLabel(job?.status || "") }}</span>
      <strong>{{ stepLabel(state.current_step) }}</strong>
      <p>{{ state.status === "ready" ? "证据、冲突与候选资料已经走完正式路线。" : "每次只推进一个可验证步骤，结果写回前仍会经过预检。" }}</p>
      <small v-if="streamError">{{ streamError }}</small>
    </div>
    <ol v-if="events.length" class="archaeology-task-events" aria-label="最近任务动态">
      <li v-for="event in events.slice(-4)" :key="`${event.sequence}-${event.event}`">
        <i></i>
        <span><strong>{{ eventLabel(event.event) }}</strong><small>{{ event.at ? new Date(event.at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : "刚刚" }}</small></span>
      </li>
    </ol>
    <div class="archaeology-task-actions">
      <button v-if="active" :disabled="busy" @click="emit('stop')"><Square :size="13" />停止</button>
      <template v-else-if="waitingWriteback">
        <button :disabled="busy" @click="emit('reject')"><RotateCcw :size="13" />退回</button>
        <button class="primary" :disabled="busy" @click="emit('approve')"><ShieldCheck :size="13" />确认写回</button>
      </template>
      <button v-else-if="failed" :disabled="busy" @click="emit('retry')"><RefreshCw :size="13" />保留进度重试</button>
      <button v-else-if="state.status !== 'ready'" class="primary" :disabled="busy" @click="emit('run')">
        {{ job ? "继续下一层" : "开始整理" }}<ArrowRight :size="13" />
      </button>
    </div>
  </section>
</template>
