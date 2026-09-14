<script setup lang="ts">
import { onMounted } from "vue";
import { ChevronDown, CircleAlert, RefreshCw } from "lucide-vue-next";
import { useAppStore } from "@/stores/app";
import { labelFor, workflowStepLabel } from "@/services/presentation";

const app = useAppStore();

onMounted(() => {
  if (app.hasProject && !app.agentObservability) void app.loadAgentObservability().catch(() => undefined);
});

function roleLabel(value: string): string {
  return ({
    "main-creative-agent": "主创 Agent",
    "main-review-agent": "审读 Agent",
    reviewer: "审读 Agent",
    writer: "主创 Agent",
    planner: "规划 Agent",
  } as Record<string, string>)[value] || value || "等待分派";
}

function statusLabel(value: string): string {
  return ({
    active: "正在执行",
    running: "正在执行",
    queued: "等待执行",
    idle: "当前待命",
    paused: "暂时停下",
    interrupted: "会话已中断",
    complete: "已经完成",
    completed: "已经完成",
    failed: "执行未完成",
    stalled: "推进停滞",
  } as Record<string, string>)[value] || "等待状态更新";
}

function contextModeLabel(value: string): string {
  return ({ bounded: "按任务精简", full: "完整资料", cached: "复用已编译资料" } as Record<string, string>)[value] || "按任务准备";
}

function eventLabel(value: string): string {
  return ({
    "task.started": "任务已开始",
    "task.completed": "任务已完成",
    "task.failed": "任务未通过",
    "runner.reasoning.started": "正在组织判断",
    "runner.session.reuse_assessed": "会话边界已检查",
    "mutation.receipt": "项目变化已记录",
    "worker.file.imported": "任务资料已导入",
    "worker.validation.passed": "产物检查已通过",
    "worker.task.selecting": "正在选择执行任务",
    "worker.task.opened": "任务资料已打开",
    "worker.sandbox.prepared": "安全工作区已准备",
    "worker.core.command_started": "核心任务已开始",
    "worker.core.outputs_protected": "正式产物已保护",
    "worker.core.command_completed": "核心任务已完成",
    "worker.runner.skipped": "本轮无需调用模型",
    "worker.core.outputs_restored": "正式产物已恢复",
    "worker.mutation.receipt": "项目变化已记录",
    "worker.validation.started": "正在检查任务产物",
    "worker.writeback.preview_ready": "写回预览已准备",
    "decision.delegated": "决策已交给项目 Agent",
  } as Record<string, string>)[value] || value;
}
</script>

<template>
  <div class="view observatory-view">
    <details class="observatory-diagnostics" open>
      <summary><ChevronDown :size="14" /><span>Agent 运行现场</span><small>任务、资料与会话的可恢复记录</small></summary>
      <div v-if="!app.agentObservability" class="observatory-empty">
        <CircleAlert :size="22" /><strong>观测数据暂不可用</strong><p>打开作品后，Worker 会话与最近事件会出现在这里。</p>
      </div>
      <template v-else>
        <header class="diagnostic-heading">
          <div><span class="eyebrow">运行状态</span><h2>{{ statusLabel(app.agentObservability.status) }}</h2></div>
          <button class="secondary-button" @click="app.loadAgentObservability"><RefreshCw :size="14" />重新读取</button>
        </header>
        <section class="strategy-grid">
          <article class="strategy-card">
            <header><span class="eyebrow">当前任务</span><h2>{{ roleLabel(app.agentObservability.active_task?.role || '') }}</h2></header>
            <dl v-if="app.agentObservability.active_task">
              <div><dt>角色</dt><dd>{{ roleLabel(app.agentObservability.active_task.role) }}</dd></div>
              <div><dt>路线</dt><dd>{{ labelFor(app.agentObservability.active_task.route) }}</dd></div>
              <div><dt>任务</dt><dd class="observatory-task-identity" :title="app.agentObservability.active_task.task_id"><span>{{ workflowStepLabel(app.agentObservability.active_task.task_id) }}</span><small>{{ app.agentObservability.active_task.task_id }}</small></dd></div>
              <div><dt>阶段</dt><dd>{{ workflowStepLabel(app.agentObservability.active_task.stage) }}</dd></div>
            </dl>
          </article>
          <article class="strategy-card">
            <header><span class="eyebrow">当前活动</span><h2>{{ app.agentObservability.activity?.label || '等待运行时活动' }}</h2></header>
            <dl v-if="app.agentObservability.activity">
              <div><dt>连接</dt><dd>{{ app.agentObservability.activity.runtime_active ? '保持活动' : '当前待命' }}</dd></div>
              <div><dt>可见产出</dt><dd>{{ app.agentObservability.activity.productive_progress_observed ? '已经出现' : '尚未出现' }}</dd></div>
              <div><dt>最近信号</dt><dd>{{ app.agentObservability.activity.last_event ? eventLabel(app.agentObservability.activity.last_event) : '等待首个信号' }}</dd></div>
            </dl>
          </article>
          <article class="strategy-card">
            <header><span class="eyebrow">上下文合同</span><h2>{{ app.agentObservability.context_diagnostics?.available ? '资料已编译' : '等待任务资料' }}</h2></header>
            <dl v-if="app.agentObservability.context_diagnostics?.available">
              <div><dt>模式</dt><dd>{{ contextModeLabel(app.agentObservability.context_diagnostics.mode) }}</dd></div>
              <div><dt>任务类型</dt><dd>{{ workflowStepLabel(app.agentObservability.context_diagnostics.task_kind) }}</dd></div>
              <div><dt>资料分层</dt><dd>{{ app.agentObservability.context_diagnostics.tiers.must_inline }} 直接 / {{ app.agentObservability.context_diagnostics.tiers.exact_on_demand }} 按需 / {{ app.agentObservability.context_diagnostics.tiers.excluded }} 排除</dd></div>
              <div><dt>摘要指纹</dt><dd>{{ app.agentObservability.context_diagnostics.digest }}</dd></div>
              <div><dt>重复读取</dt><dd>{{ app.agentObservability.context_diagnostics.access.available ? `${app.agentObservability.context_diagnostics.access.redundant_read_calls} 次` : '执行完成后可用' }}</dd></div>
            </dl>
            <p v-else class="strategy-empty">当前没有需要编译的任务资料。新任务开始后，这里会显示直接资料、按需资料与排除项。</p>
          </article>
          <article class="strategy-card">
            <header><span class="eyebrow">会话</span><h2>{{ app.agentObservability.sessions?.length ?? 0 }} 个 Worker 会话</h2></header>
            <ul class="observatory-sessions"><li v-for="session in app.agentObservability.sessions ?? []" :key="session.session_id"><strong>{{ roleLabel(session.role) }}</strong><span>{{ statusLabel(session.status) }}</span><small>{{ labelFor(session.route) }}</small></li></ul>
          </article>
        </section>
        <section class="strategy-events">
          <header><div><span class="eyebrow">最近事件</span><h2>运行记录</h2></div></header>
          <div class="strategy-event-log">
            <article v-for="event in app.agentObservability.recent_events" :key="`${event.sequence}-${event.task_id}`"><span class="event-dot"></span><strong>{{ eventLabel(event.event) }}</strong><span>{{ labelFor(event.route) }}</span><code class="observatory-event-task" :title="event.task_id">{{ workflowStepLabel(event.task_id) }}</code><small>{{ event.event }}</small><small>{{ workflowStepLabel(event.stage) }}</small><time>{{ event.at }}</time></article>
          </div>
        </section>
      </template>
    </details>
  </div>
</template>
