<script setup lang="ts">
import { computed } from "vue";
import { Activity, ArrowUpRight, BookOpenText, Radio } from "lucide-vue-next";
import type { AgentObservability } from "@/types/api";
import type { ProjectAgentWorkspaceId } from "@/workspaces/projectAgentWorkspaceRegistry";

const props = defineProps<{
  title: string;
  premise: string;
  progress: number | null;
  formalChars: number;
  targetChars: number;
  currentTask: string;
  currentStage: string;
  agentStatus: string;
  readerUnits: number;
  nextAction: string;
  observability: AgentObservability | null;
}>();
const emit = defineEmits<{ workspace: [workspace: ProjectAgentWorkspaceId] }>();
const sessions = computed(() => props.observability?.sessions || []);
const recentEvents = computed(() => (props.observability?.recent_events || []).slice(-4).reverse());

function roleName(value: string): string {
  return ({ writer: "主创", reviewer: "审读", planner: "规划", "main-creative-agent": "主创", "main-review-agent": "审读" } as Record<string, string>)[value] || "创作 Agent";
}

function runStatus(value: string): string {
  if (["active", "running"].includes(value)) return "正在工作";
  if (["complete", "completed"].includes(value)) return "已完成";
  if (["failed", "stalled"].includes(value)) return "需要处理";
  return "等待中";
}
</script>

<template>
  <aside class="pa-inspector">
    <section class="pa-inspect-focus">
      <header><span>当前作品</span><button title="打开作品档案" @click="emit('workspace', 'archive')"><ArrowUpRight :size="14" /></button></header>
      <h2>{{ title }}</h2>
      <p>{{ premise || '作品方向会随着创作逐步变得清晰。' }}</p>
      <div class="pa-progress"><i :style="{ width: `${Math.max(0, Math.min(100, progress || 0))}%` }"></i></div>
      <div class="pa-progress-meta"><span>{{ progress == null ? '等待校准' : `${Math.round(progress)}%` }}</span><span>{{ formalChars.toLocaleString('zh-CN') }} / {{ targetChars.toLocaleString('zh-CN') }} 字</span></div>
    </section>

    <section class="pa-observer-section">
      <header><span><Activity :size="14" /> Agent 工作</span><strong :class="{ active: observability?.status === 'active' }">{{ agentStatus }}</strong></header>
      <p class="pa-observer-current">{{ observability?.activity?.label || currentTask || '当前没有运行中的任务' }}</p>
      <small class="pa-observer-stage">{{ currentStage || nextAction || '下一步会出现在这里' }}</small>
      <div class="pa-observer-sessions">
        <div v-for="item in sessions" :key="item.session_id" class="pa-observer-session">
          <i :class="item.status"></i><span><strong>{{ roleName(item.role) }}</strong><small>{{ item.last_message || item.task_id || '正在等待任务' }}</small></span><em>{{ runStatus(item.status) }}</em>
        </div>
        <p v-if="!sessions.length">创作开始后，这里会出现主创与审读会话。</p>
      </div>
      <details v-if="recentEvents.length" class="pa-observer-events"><summary>最近活动 · {{ recentEvents.length }}</summary><p v-for="item in recentEvents" :key="item.sequence">{{ item.message || item.event }}</p></details>
      <button class="pa-inspector-action" @click="emit('workspace', 'live')"><Radio :size="15" />打开创作现场<ArrowUpRight :size="14" /></button>
    </section>

    <section>
      <header><span>已完成正文</span><button @click="emit('workspace', 'reader')">阅读</button></header>
      <div class="pa-context-row"><BookOpenText :size="15" /><span><strong>{{ readerUnits }} 个正式单元</strong><small>新晋升正文会自动进入长卷</small></span></div>
    </section>
  </aside>
</template>
