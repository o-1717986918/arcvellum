<script setup lang="ts">
import { onMounted } from "vue";
import { CircleAlert, RefreshCw } from "lucide-vue-next";
import { useAppStore } from "@/stores/app";

const app = useAppStore();

onMounted(() => {
  if (app.hasProject && !app.agentObservability) {
    void app.loadAgentObservability().catch(() => undefined);
  }
});

function roleLabel(value: string): string {
  return {
    "main-creative-agent": "主创 Agent",
    "main-review-agent": "审读 Agent",
    reviewer: "审读 Agent",
    writer: "主创 Agent",
    planner: "规划 Agent",
  }[value] || value || "等待分派";
}

function statusLabel(value: string): string {
  return { active: "正在执行", idle: "当前待命", stalled: "推进停滞" }[value] || value;
}

function eventLabel(value: string): string {
  return {
    "task.started": "任务已开始",
    "task.completed": "任务已完成",
    "task.failed": "任务未通过",
    "runner.session.reuse_assessed": "会话边界已检查",
  }[value] || value;
}
</script>

<template>
  <div class="view observatory-view">
    <header class="quality-heading">
      <div>
        <span class="eyebrow">Agent 观测台</span>
        <h1>任务正在做什么</h1>
        <p>这里展示 Worker 会话、上下文与产物进度的安全投影；不会暴露正文、凭证或推理链。</p>
      </div>
      <button class="secondary-button" @click="app.loadAgentObservability">
        <RefreshCw :size="15" />重新读取
      </button>
    </header>

    <div v-if="!app.agentObservability" class="observatory-empty">
      <CircleAlert :size="22" />
      <strong>观测数据暂不可用</strong>
      <p>打开作品后，Worker 会话与最近事件会出现在这里。</p>
    </div>
    <template v-else>
      <section class="strategy-grid">
        <article class="strategy-card">
          <header>
            <span class="eyebrow">运行状态</span>
            <h2>{{ statusLabel(app.agentObservability.status) }}</h2>
          </header>
          <dl v-if="app.agentObservability.active_task">
            <div><dt>角色</dt><dd>{{ roleLabel(app.agentObservability.active_task.role) }} <small>{{ app.agentObservability.active_task.role }}</small></dd></div>
            <div><dt>路线</dt><dd>{{ app.agentObservability.active_task.route }}</dd></div>
            <div><dt>任务</dt><dd>{{ app.agentObservability.active_task.task_id }}</dd></div>
            <div><dt>阶段</dt><dd>{{ app.agentObservability.active_task.stage }}</dd></div>
          </dl>
          <p v-else class="strategy-empty">当前没有正在运行的任务。</p>
        </article>

        <article class="strategy-card">
          <header>
            <span class="eyebrow">会话</span>
            <h2>{{ app.agentObservability.sessions?.length ?? 0 }} 个 Worker 会话</h2>
          </header>
          <ul class="observatory-sessions">
            <li v-for="session in app.agentObservability.sessions ?? []" :key="session.session_id">
              <strong>{{ roleLabel(session.role) }}</strong>
              <span>{{ session.status }}</span>
              <small>{{ session.role }} · {{ session.route }}</small>
            </li>
          </ul>
          <p v-if="!(app.agentObservability.sessions ?? []).length" class="strategy-empty">
            还没有 Worker 会话。
          </p>
        </article>
      </section>

      <section class="strategy-events">
        <header>
          <div>
            <span class="eyebrow">最近事件</span>
            <h2>按审计顺序</h2>
          </div>
        </header>
        <div class="strategy-event-log">
          <article v-for="event in app.agentObservability.recent_events" :key="`${event.sequence}-${event.task_id}`">
            <span class="event-dot" aria-hidden="true"></span>
            <strong>{{ eventLabel(event.event) }}</strong>
            <code>{{ event.route }}</code>
            <small>{{ event.event }}</small>
            <small>{{ event.stage }}</small>
            <time>{{ event.at }}</time>
          </article>
          <p v-if="!app.agentObservability.recent_events.length" class="strategy-empty">
            还没有收到 Agent 事件。
          </p>
        </div>
      </section>
    </template>
  </div>
</template>
