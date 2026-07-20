<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ArrowRight, CircleAlert, CircleCheck, Clock3, Play, RefreshCw, Route } from "lucide-vue-next";
import ManuscriptReader from "@/components/ManuscriptReader.vue";
import AutopilotPanel from "@/components/AutopilotPanel.vue";
import StoryTrace from "@/components/StoryTrace.vue";
import { api, query } from "@/services/api";
import { asList, asRecord, describeGate, describeWorkflowAction, formatCount, labelFor, manuscriptItems, targetLabel, workflowStepLabel } from "@/services/presentation";
import { useAppStore } from "@/stores/app";

const store = useAppStore();
const choices = ref<Record<string, unknown>[]>([]);
const working = ref(false);
const actionMessage = ref("");

const dashboard = computed(() => (store.dashboard || null) as Record<string, unknown> | null);
const summary = computed(() => asRecord(dashboard.value?.summary));
const routeAudits = computed(() => asList<Record<string, unknown>>(dashboard.value?.route_audits));
const nextActions = computed(() => asList<Record<string, unknown>>(dashboard.value?.next_actions));
const prose = computed(() => manuscriptItems((store.library || null) as Record<string, unknown> | null));
const firstAction = computed(() => nextActions.value[0] || null);
const readyRoutes = computed(() => routeAudits.value.filter((item) => Number(item.blocking_count || 0) === 0).length);

onMounted(async () => {
  await store.refreshWorkspace();
  await loadChoices();
});

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
    const result = await api<Record<string, unknown>>("/worker/prepare", {
      method: "POST",
      body: JSON.stringify({ project_root: store.currentProjectPath, route: "scene-development", runtime: "opencode" }),
    });
    actionMessage.value = String(result.message || result.status || "下一项创作任务已经准备好。 ");
    await store.loadDashboard();
  } catch (cause) {
    actionMessage.value = cause instanceof Error ? cause.message : "暂时无法准备下一项任务。";
  } finally {
    working.value = false;
  }
}
</script>

<template>
  <div class="view overview-view">
    <section class="overview-header">
      <div>
        <span class="eyebrow">创作总控</span>
        <h1>{{ store.currentProject?.title }}</h1>
        <p>{{ store.currentProject?.premise || "作品方向仍在形成。" }}</p>
      </div>
      <button class="secondary-button" @click="store.refreshWorkspace"><RefreshCw :size="17" />刷新作品</button>
    </section>

    <section class="pulse-strip">
      <div><span class="pulse-icon jade"><Route :size="18" /></span><p>创作路线<strong>{{ readyRoutes }} / {{ routeAudits.length || 0 }} 就绪</strong></p></div>
      <div><span class="pulse-icon brass"><Clock3 :size="18" /></span><p>待处理任务<strong>{{ formatCount(summary.pending_task_count) }} 项</strong></p></div>
      <div><span class="pulse-icon cinnabar"><CircleAlert :size="18" /></span><p>需要补齐<strong>{{ formatCount(summary.blocking_count) }} 处</strong></p></div>
      <div><span class="pulse-icon iris"><CircleCheck :size="18" /></span><p>正式正文<strong>{{ prose.length }} 节</strong></p></div>
    </section>

    <div class="overview-grid">
      <StoryTrace :dashboard="dashboard" />
      <aside class="now-panel">
        <span class="eyebrow">现在最值得做</span>
        <template v-if="firstAction">
          <span class="route-chip">{{ labelFor(firstAction.route) }}</span>
          <h2>{{ targetLabel(firstAction.target) }}</h2>
          <p>{{ describeWorkflowAction(firstAction.next_action) }}</p>
          <div class="task-evidence"><span>当前阶段</span><strong>{{ workflowStepLabel(firstAction.current_step) }}</strong></div>
          <button class="primary-button wide" :disabled="working" @click="prepareNextTask">
            <Play :size="16" />{{ working ? "正在准备……" : "准备下一项任务" }}<ArrowRight :size="16" />
          </button>
        </template>
        <template v-else>
          <span class="completion-seal"><CircleCheck :size="22" /></span>
          <h2>当前没有待办</h2>
          <p>作品路线暂时没有发现需要立刻补齐的环节。</p>
        </template>
        <small v-if="actionMessage" class="action-message">{{ actionMessage }}</small>
      </aside>
    </div>

    <AutopilotPanel />

    <section v-if="choices.length" class="decision-inbox">
      <header><div><span class="eyebrow">等待你的判断</span><h2>几个方向需要你来定</h2></div><span>{{ choices.length }} 项</span></header>
      <div class="decision-row">
        <article v-for="choice in choices.slice(0, 4)" :key="String(choice.choice_id || choice.id)">
          <span>{{ labelFor(choice.kind || choice.choice_type) }}</span>
          <h3>{{ choice.title || choice.prompt || "创作方向选择" }}</h3>
          <p>{{ choice.summary || choice.description || "打开后查看候选方向和影响。" }}</p>
          <button class="text-button">查看选择<ArrowRight :size="15" /></button>
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
</template>
