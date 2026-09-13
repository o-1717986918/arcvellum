<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { Bot, Moon, PanelLeft, PanelRight, Settings2, Sun } from "lucide-vue-next";
import { RouterLink } from "vue-router";
import AgentComposer from "@/features/project-agent/components/AgentComposer.vue";
import AgentContextInspector from "@/features/project-agent/components/AgentContextInspector.vue";
import AgentConversation from "@/features/project-agent/components/AgentConversation.vue";
import AgentThreadRail from "@/features/project-agent/components/AgentThreadRail.vue";
import { useProjectAgentSession } from "@/features/project-agent/composables/useProjectAgentSession";
import { asList, asRecord, describeWorkflowAction, workflowStepLabel } from "@/services/presentation";
import { friendlyError, useAppStore } from "@/stores/app";

const store = useAppStore();
const railOpen = ref(false);
const inspectorOpen = ref(false);
const dark = ref(localStorage.getItem("arcvellum.projectAgentTheme") === "dark");
const projectRoot = computed(() => store.currentProjectPath || "");
const projectTitle = computed(() => store.currentProject?.title || "当前作品");
const agent = useProjectAgentSession({
  projectRoot,
  projectTitle,
  onError: (cause, fallback) => { store.error = friendlyError(cause, fallback); },
});

const dashboard = computed(() => asRecord(store.dashboard));
const currentTaskRecord = computed(() => asRecord(dashboard.value.current_task));
const currentTask = computed(() => String(
  currentTaskRecord.value.label
  || currentTaskRecord.value.title
  || currentTaskRecord.value.task_id
  || "",
));
const currentStage = computed(() => {
  const activity = store.agentObservability?.activity;
  return String(activity?.label || workflowStepLabel(currentTaskRecord.value.stage || currentTaskRecord.value.task_id || ""));
});
const agentStatus = computed(() => {
  const status = String(store.agentObservability?.status || "idle");
  if (status === "running") return "主创正在工作";
  if (status === "stalled") return "创作需要处理";
  if (status === "failed") return "最近任务未完成";
  return "主创当前待命";
});
const nextAction = computed(() => {
  const first = asList<Record<string, unknown>>(dashboard.value.next_actions)[0];
  return first ? String(first.summary || first.label || describeWorkflowAction(first.command || first.task_id || first.route)) : "";
});
const progress = computed(() => store.projectProgress?.overall_percent ?? null);
const formalChars = computed(() => Number(store.projectProgress?.formal_chinese_content_chars || 0));
const targetChars = computed(() => Number(store.projectProgress?.target_chinese_content_chars || store.currentProject?.target_length || 0));
const readerUnits = computed(() => Number(store.readerManifest?.unit_count || 0));

onMounted(async () => {
  if (projectRoot.value) {
    await store.refreshWorkspace();
    await agent.load();
  }
});

watch(projectRoot, async (root) => {
  agent.reset();
  if (!root) return;
  await store.refreshWorkspace();
  await agent.load();
});

watch(dark, (value) => localStorage.setItem("arcvellum.projectAgentTheme", value ? "dark" : "light"));

function selectProject(event: Event): void {
  store.setCurrentProject((event.target as HTMLSelectElement).value);
}
</script>

<template>
  <div class="pa-shell" :class="{ 'pa-theme-dark': dark, 'pa-rail-open': railOpen, 'pa-inspector-open': inspectorOpen }">
    <AgentThreadRail
      :sessions="agent.sessions.value"
      :active-session-id="agent.session.value?.session_id"
      :project-title="projectTitle"
      :project-progress="progress"
      :disabled="agent.sending.value || agent.loading.value || agent.creating.value"
      @create="agent.createSession"
      @select="agent.openSession"
    />

    <main class="pa-workbench">
      <header class="pa-workbench-head">
        <button class="pa-icon-button pa-rail-toggle" title="打开会话" @click="railOpen = !railOpen"><PanelLeft :size="17" /></button>
        <span class="pa-agent-avatar"><Bot :size="16" /></span>
        <div class="pa-conversation-title">
          <strong>{{ agent.session.value?.title || '项目 Agent' }}</strong>
          <small>{{ agent.sending.value ? (agent.activity.value?.statusLabel || '正在工作') : '可以继续交谈' }}</small>
        </div>
        <label class="pa-project-select">
          <select :value="store.currentProjectPath" aria-label="切换当前作品" @change="selectProject">
            <option v-for="project in store.projects" :key="project.path" :value="project.path">{{ project.title }}</option>
          </select>
        </label>
        <button class="pa-icon-button" :title="dark ? '使用浅色外观' : '使用深色外观'" @click="dark = !dark"><Sun v-if="dark" :size="17" /><Moon v-else :size="17" /></button>
        <RouterLink class="pa-icon-button" to="/settings" title="设置"><Settings2 :size="17" /></RouterLink>
        <button class="pa-icon-button pa-inspector-toggle" title="查看作品上下文" @click="inspectorOpen = !inspectorOpen"><PanelRight :size="17" /></button>
      </header>

      <AgentConversation
        :messages="agent.messages.value"
        :activity="agent.activity.value"
        :loading="agent.loading.value"
        :omitted-count="agent.omittedMessageCount.value"
        @starter="agent.ask"
      />
      <AgentComposer :disabled="agent.sending.value || agent.loading.value" @send="agent.ask" />
    </main>

    <AgentContextInspector
      :title="projectTitle"
      :premise="store.currentProject?.premise || ''"
      :progress="progress"
      :formal-chars="formalChars"
      :target-chars="targetChars"
      :current-task="currentTask"
      :current-stage="currentStage"
      :agent-status="agentStatus"
      :reader-units="readerUnits"
      :next-action="nextAction"
    />
    <button v-if="railOpen || inspectorOpen" class="pa-panel-backdrop" aria-label="关闭侧栏" @click="railOpen = false; inspectorOpen = false"></button>
  </div>
</template>
