<script setup lang="ts">
import { onMounted } from "vue";
import { ChevronDown, CircleAlert, RefreshCw } from "lucide-vue-next";
import { useAppStore } from "@/stores/app";

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
  return ({ active: "正在执行", idle: "当前待命", stalled: "推进停滞" } as Record<string, string>)[value] || value;
}

function eventLabel(value: string): string {
  return ({
    "task.started": "任务已开始",
    "task.completed": "任务已完成",
    "task.failed": "任务未通过",
    "runner.session.reuse_assessed": "会话边界已检查",
  } as Record<string, string>)[value] || value;
}
</script>

<template>
  <div class="view observatory-view">
    <details class="observatory-diagnostics" open>
      <summary><ChevronDown :size="14" /><span>高级运行诊断</span><small>上下文、任务与会话的安全摘要</small></summary>
      <div v-if="!app.agentObservability" class="observatory-empty">
        <CircleAlert :size="22" /><strong>观测数据暂不可用</strong><p>打开作品后，Worker 会话与最近事件会出现在这里。</p>
      </div>
      <template v-else>
        <header class="diagnostic-heading">
          <div><span class="eyebrow">运行诊断</span><h2>{{ statusLabel(app.agentObservability.status) }}</h2></div>
          <button class="secondary-button" @click="app.loadAgentObservability"><RefreshCw :size="14" />重新读取</button>
        </header>
        <section class="strategy-grid">
          <article class="strategy-card">
            <header><span class="eyebrow">当前任务</span><h2>{{ roleLabel(app.agentObservability.active_task?.role || '') }}</h2></header>
            <dl v-if="app.agentObservability.active_task">
              <div><dt>角色</dt><dd>{{ roleLabel(app.agentObservability.active_task.role) }} <small>{{ app.agentObservability.active_task.role }}</small></dd></div>
              <div><dt>路线</dt><dd>{{ app.agentObservability.active_task.route }}</dd></div>
              <div><dt>任务</dt><dd class="observatory-task-identity" :title="app.agentObservability.active_task.task_id">{{ app.agentObservability.active_task.task_id }}</dd></div>
              <div><dt>阶段</dt><dd>{{ app.agentObservability.active_task.stage }}</dd></div>
            </dl>
          </article>
          <article class="strategy-card">
            <header><span class="eyebrow">当前活动</span><h2>{{ app.agentObservability.activity?.label || '等待运行时活动' }}</h2></header>
            <dl v-if="app.agentObservability.activity">
              <div><dt>连接</dt><dd>{{ app.agentObservability.activity.runtime_active ? '保持活动' : '当前待命' }}</dd></div>
              <div><dt>可见产出</dt><dd>{{ app.agentObservability.activity.productive_progress_observed ? '已经出现' : '尚未出现' }}</dd></div>
              <div><dt>最近信号</dt><dd>{{ app.agentObservability.activity.last_event || '等待首个信号' }}</dd></div>
            </dl>
          </article>
          <article class="strategy-card">
            <header><span class="eyebrow">上下文合同</span><h2>{{ app.agentObservability.context_diagnostics?.available ? '资料已编译' : '等待任务资料' }}</h2></header>
            <dl v-if="app.agentObservability.context_diagnostics?.available">
              <div><dt>模式</dt><dd>{{ app.agentObservability.context_diagnostics.mode || '未记录' }}</dd></div>
              <div><dt>任务类型</dt><dd>{{ app.agentObservability.context_diagnostics.task_kind || '未记录' }}</dd></div>
              <div><dt>资料分层</dt><dd>{{ app.agentObservability.context_diagnostics.tiers.must_inline }} 直接 / {{ app.agentObservability.context_diagnostics.tiers.exact_on_demand }} 按需 / {{ app.agentObservability.context_diagnostics.tiers.excluded }} 排除</dd></div>
              <div><dt>摘要指纹</dt><dd>{{ app.agentObservability.context_diagnostics.digest }}</dd></div>
              <div><dt>重复读取</dt><dd>{{ app.agentObservability.context_diagnostics.access.available ? `${app.agentObservability.context_diagnostics.access.redundant_read_calls} 次` : '执行完成后可用' }}</dd></div>
            </dl>
          </article>
          <article class="strategy-card">
            <header><span class="eyebrow">会话</span><h2>{{ app.agentObservability.sessions?.length ?? 0 }} 个 Worker 会话</h2></header>
            <ul class="observatory-sessions"><li v-for="session in app.agentObservability.sessions ?? []" :key="session.session_id"><strong>{{ roleLabel(session.role) }}</strong><span>{{ session.status }}</span><small>{{ session.role }} · {{ session.route }}</small></li></ul>
          </article>
        </section>
        <section class="strategy-events">
          <header><div><span class="eyebrow">最近事件</span><h2>按审计顺序</h2></div></header>
          <div class="strategy-event-log">
            <article v-for="event in app.agentObservability.recent_events" :key="`${event.sequence}-${event.task_id}`"><span class="event-dot"></span><strong>{{ eventLabel(event.event) }}</strong><code>{{ event.route }}</code><code class="observatory-event-task" :title="event.task_id">{{ event.task_id }}</code><small>{{ event.event }}</small><small>{{ event.stage }}</small><time>{{ event.at }}</time></article>
          </div>
        </section>
      </template>
    </details>
  </div>
</template>
