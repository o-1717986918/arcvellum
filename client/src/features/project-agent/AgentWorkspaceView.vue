<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Bot, KeyRound, Orbit, PanelLeft, PanelRight, Settings2, SunMoon } from "lucide-vue-next";
import { useRoute, useRouter } from "vue-router";
import AgentComposer from "@/features/project-agent/components/AgentComposer.vue";
import AgentContextInspector from "@/features/project-agent/components/AgentContextInspector.vue";
import AgentConversation from "@/features/project-agent/components/AgentConversation.vue";
import AgentSubworkspace from "@/features/project-agent/components/AgentSubworkspace.vue";
import AgentThreadRail from "@/features/project-agent/components/AgentThreadRail.vue";
import NewConversationDialog from "@/features/project-agent/components/NewConversationDialog.vue";
import { useProjectAgentSession } from "@/features/project-agent/composables/useProjectAgentSession";
import {
  projectAgentWorkspaces,
  type ProjectAgentWorkspaceId,
} from "@/workspaces/projectAgentWorkspaceRegistry";
import { asList, asRecord, describeWorkflowAction, workflowStepLabel } from "@/services/presentation";
import { friendlyError, useAppStore } from "@/stores/app";

const store = useAppStore();
const route = useRoute();
const router = useRouter();
const railOpen = ref(false);
const inspectorOpen = ref(false);
const newConversationOpen = ref(false);
type AppearanceMode = "system" | "light" | "dark" | "contrast";
const savedAppearance = localStorage.getItem("arcvellum.projectAgentTheme");
const appearance = ref<AppearanceMode>(
  savedAppearance === "system" || savedAppearance === "light" || savedAppearance === "dark" || savedAppearance === "contrast"
    ? savedAppearance
    : "light",
);
const systemDark = ref(false);
const activeWorkspace = ref<ProjectAgentWorkspaceId | null>(null);
const workspaceFullscreen = ref(false);
let colorScheme: MediaQueryList | null = null;
const projectRoot = computed(() => store.currentProjectPath || "");
const projectTitle = computed(() => store.currentProject?.title || "作品库");
const projectRoots = computed(() => store.projects.map((project) => project.path));
const projectLabels = computed(() => Object.fromEntries(store.projects.map((project) => [project.path, project.title])));
const sessionProject = computed(() => store.projects.find((project) => project.path === agent.session.value?.project_root) || null);
const needsModelConnection = computed(() => Boolean(store.modelCatalog && !store.modelCatalog.providers.some((provider) => provider.connected)));
const workspace = computed(() => projectAgentWorkspaces.get(activeWorkspace.value));
const applicationWorkspace = computed(() => workspace.value?.scope === "application");
const dark = computed(() => appearance.value === "dark" || (appearance.value === "system" && systemDark.value));
const agent = useProjectAgentSession({
  projectRoot,
  projectTitle,
  projectRoots,
  onSessionOpened: async (opened) => {
    const root = store.projects.some((project) => project.path === opened.project_root) ? opened.project_root : "";
    if (store.currentProjectPath !== root) store.setCurrentProject(root, false);
    if (route.name === "project-agent" && route.query.session !== opened.session_id) {
      void router.replace({ name: "project-agent", query: { ...route.query, session: opened.session_id } });
    }
  },
  onError: (cause, fallback) => { store.error = friendlyError(cause, fallback); },
  onToolFinished: async (name, ok) => {
    if (ok && name === "project_create") await store.refreshProjectCatalog();
  },
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
  if (status === "active") return "主创正在工作";
  if (status === "stalled") return "创作需要处理";
  return "主创当前待命";
});
const creativePhase = computed<"active" | "waiting" | "attention" | null>(() => {
  const runStatus = store.autopilotStatus?.run?.status;
  if (runStatus === "running" || store.agentObservability?.status === "active") return "active";
  if (runStatus === "paused" || runStatus === "blocked") return "waiting";
  if (runStatus === "failed" || store.agentObservability?.status === "stalled") return "attention";
  return null;
});
const creativeStatus = computed(() => {
  if (creativePhase.value === "waiting") return "创作已暂停，等待继续";
  if (creativePhase.value === "attention") return "创作遇到问题，需要处理";
  return String(store.agentObservability?.activity?.label || currentTask.value || "主创正在处理作品");
});
const nextAction = computed(() => {
  const first = asList<Record<string, unknown>>(dashboard.value.next_actions)[0];
  return first ? String(first.summary || first.label || describeWorkflowAction(first.command || first.task_id || first.route)) : "";
});
const progress = computed(() => store.projectProgress?.overall_percent ?? null);
const formalChars = computed(() => Number(store.projectProgress?.formal_chinese_content_chars || 0));
const targetChars = computed(() => Number(store.projectProgress?.target_chinese_content_chars || store.currentProject?.target_length || 0));
const readerUnits = computed(() => Number(store.readerManifest?.unit_count || 0));

onMounted(() => {
  colorScheme = window.matchMedia("(prefers-color-scheme: dark)");
  systemDark.value = colorScheme.matches;
  colorScheme.addEventListener("change", updateSystemAppearance);
  openWorkspaceFromQuery(route.query.workspace);
  window.addEventListener("arcvellum:onboarding", returnToConversation);
  window.addEventListener("focus", recoverAgentOnForeground);
  document.addEventListener("visibilitychange", recoverAgentOnForeground);
});

let initialSessionLoaded = false;
watch(() => store.initialized, async (ready) => {
  if (!ready || initialSessionLoaded) return;
  initialSessionLoaded = true;
  const initialRoot = projectRoot.value;
  await agent.load(String(route.query.session || ""));
  if (projectRoot.value && projectRoot.value === initialRoot) await store.refreshWorkspace();
  if (!store.modelCatalog) await store.loadModelCatalog().catch(() => undefined);
  if (needsModelConnection.value && !route.query.workspace) openWorkspace("settings");
  else if (route.query.new === "1" || (!agent.session.value && !route.query.workspace)) newConversationOpen.value = true;
}, { immediate: true });

onBeforeUnmount(() => {
  colorScheme?.removeEventListener("change", updateSystemAppearance);
  window.removeEventListener("arcvellum:onboarding", returnToConversation);
  window.removeEventListener("focus", recoverAgentOnForeground);
  document.removeEventListener("visibilitychange", recoverAgentOnForeground);
});

watch([projectRoot, activeWorkspace], async ([root, visibleWorkspace]) => {
  const boundRoot = agent.session.value?.project_root;
  if (!visibleWorkspace && boundRoot && root !== boundRoot) {
    if (agent.sending.value) {
      store.setCurrentProject(boundRoot, false);
      return;
    }
    agent.reset(true);
    newConversationOpen.value = true;
    await router.replace({ name: "project-agent", query: { new: "1" } });
    return;
  }
  if (root && activeWorkspace.value === "projects" && !agent.session.value) {
    closeWorkspace();
    newConversationOpen.value = true;
  }
  if (root) await store.refreshWorkspace();
});

watch(appearance, (value) => localStorage.setItem("arcvellum.projectAgentTheme", value));
watch(needsModelConnection, (needed, previouslyNeeded) => {
  if (!needed && previouslyNeeded && activeWorkspace.value === "settings") {
    closeWorkspace();
    if (!agent.session.value) newConversationOpen.value = true;
  }
});
watch(() => route.query.workspace, openWorkspaceFromQuery);
watch(() => route.query.new, (value) => { if (value === "1" && !needsModelConnection.value) newConversationOpen.value = true; });
watch(() => route.query.session, async (value) => {
  const id = Array.isArray(value) ? String(value[0] || "") : String(value || "");
  if (id && id !== agent.session.value?.session_id && !agent.sending.value) await agent.openSession(id);
});

async function createConversation(root: string, title: string): Promise<void> {
  const created = await agent.createSession(root, `${title}创作会话`);
  if (created) {
    newConversationOpen.value = false;
    closeWorkspace();
    void router.replace({ name: "project-agent", query: { session: created.session_id } });
  }
}

async function openHistorySession(sessionId: string): Promise<void> {
  if (await agent.openSession(sessionId)) {
    newConversationOpen.value = false;
    closeWorkspace();
    void router.replace({ name: "project-agent", query: { session: sessionId } });
  }
}

function openProjectChooser(): void {
  newConversationOpen.value = false;
  openWorkspace("projects");
}

function openOrrery(): void {
  if (!sessionProject.value) return;
  void router.push({ name: "overview", query: { session: agent.session.value?.session_id } });
}

function updateSystemAppearance(event: MediaQueryListEvent): void {
  systemDark.value = event.matches;
}

function openWorkspaceFromQuery(value: unknown): void {
  const requested = Array.isArray(value) ? String(value[0] || "") : String(value || "");
  if (projectAgentWorkspaces.has(requested)) {
    openWorkspace(requested);
    return;
  }
  activeWorkspace.value = null;
  workspaceFullscreen.value = false;
  railOpen.value = false;
  inspectorOpen.value = false;
}

function openWorkspace(next: ProjectAgentWorkspaceId): void {
  const descriptor = projectAgentWorkspaces.get(next);
  if (!descriptor || (descriptor.requiresProject && !projectRoot.value)) {
    syncWorkspaceQuery("projects");
    activeWorkspace.value = "projects";
    return;
  }
  activeWorkspace.value = next;
  syncWorkspaceQuery(next);
  workspaceFullscreen.value = false;
  railOpen.value = false;
  inspectorOpen.value = false;
}

function syncWorkspaceQuery(workspace: ProjectAgentWorkspaceId | null): void {
  if (route.name !== "project-agent") return;
  const current = Array.isArray(route.query.workspace) ? route.query.workspace[0] : route.query.workspace;
  if ((current || null) === workspace) return;
  const query = { ...route.query };
  if (workspace) query.workspace = workspace;
  else delete query.workspace;
  void router.replace({ name: "project-agent", query });
}

function closeWorkspace(): void {
  activeWorkspace.value = null;
  syncWorkspaceQuery(null);
  workspaceFullscreen.value = false;
}

function returnToConversation(): void {
  closeWorkspace();
}

function recoverAgentOnForeground(): void {
  if (document.visibilityState === "visible") void agent.recover();
}
</script>

<template>
  <div
    class="pa-shell"
    :class="{
      'pa-theme-dark': dark,
      'pa-theme-contrast': appearance === 'contrast',
      'pa-rail-open': railOpen,
      'pa-inspector-open': inspectorOpen,
      'pa-workspace-active': workspace,
      'pa-workspace-fullscreen': workspaceFullscreen,
      'pa-utility-workspace': applicationWorkspace,
      'pa-no-project': !projectRoot,
    }"
  >
    <AgentThreadRail
      :sessions="agent.sessions.value"
      :active-session-id="agent.session.value?.session_id"
      :project-title="projectTitle"
      :project-progress="progress"
      :project-labels="projectLabels"
      :has-project="Boolean(sessionProject)"
      :active-workspace="activeWorkspace"
      :disabled="agent.sending.value || agent.loading.value || agent.creating.value"
      @create="newConversationOpen = true"
      @select="openHistorySession"
      @workspace="openWorkspace"
    />

    <main class="pa-workbench">
      <header class="pa-workbench-head">
        <button class="pa-icon-button pa-rail-toggle" title="打开会话" @click="railOpen = !railOpen"><PanelLeft :size="17" /></button>
        <span class="pa-agent-avatar"><Bot :size="16" /></span>
        <div class="pa-conversation-title">
          <strong>{{ workspace?.title || agent.session.value?.title || '项目 Agent' }}</strong>
          <small>{{ workspace ? workspace.description : (sessionProject?.title || '先选择作品，开始一段对话') }}</small>
        </div>
        <button v-if="sessionProject && !workspace" class="pa-orrery-entry" data-tour-id="orrery" @click="openOrrery"><Orbit :size="16" />进入 {{ sessionProject.title }} 的星仪</button>
        <span v-else class="pa-head-spacer"></span>
        <label class="pa-appearance-select" title="工作台外观">
          <SunMoon :size="16" />
          <select v-model="appearance" aria-label="工作台外观">
            <option value="system">跟随系统</option>
            <option value="light">浅色</option>
            <option value="dark">深色</option>
            <option value="contrast">高对比度</option>
          </select>
        </label>
        <button class="pa-icon-button" title="设置" @click="openWorkspace('settings')"><Settings2 :size="17" /></button>
        <button v-if="!workspaceFullscreen" class="pa-icon-button pa-inspector-toggle" title="查看作品上下文" @click="inspectorOpen = !inspectorOpen"><PanelRight :size="17" /></button>
      </header>

      <AgentSubworkspace
        v-if="workspace"
        :workspace="workspace"
        :fullscreen="workspaceFullscreen"
        @close="closeWorkspace"
        @fullscreen="workspaceFullscreen = !workspaceFullscreen"
        @navigate="openWorkspace"
      />
      <template v-else>
        <div v-if="needsModelConnection" class="pa-connection-prompt" role="status"><KeyRound :size="18" /><span><strong>先连接模型，再开始创作</strong><small>阅读演示作品无需密钥；发送消息与创作需要你自己的模型服务。</small></span><button @click="openWorkspace('settings')">配置 API Key</button></div>
        <AgentConversation
          :messages="agent.messages.value"
          :activity="agent.activity.value"
          :loading="agent.loading.value"
          :omitted-count="agent.omittedMessageCount.value"
          :has-session="Boolean(agent.session.value)"
          :creative-status="creativeStatus"
          :creative-task="currentTask"
          :creative-phase="creativePhase"
          @starter="agent.ask"
          @new-conversation="newConversationOpen = true"
          @open-live="openWorkspace('live')"
        />
        <AgentComposer
          data-tour-id="advisor"
          :disabled="agent.loading.value || !agent.session.value || needsModelConnection"
          :busy="agent.sending.value"
          @send="agent.ask"
          @stop="agent.stop"
        />
      </template>
    </main>

    <AgentContextInspector
      v-if="sessionProject && !workspace"
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
      :observability="store.agentObservability"
      @workspace="openWorkspace"
    />
    <NewConversationDialog
      v-if="newConversationOpen"
      :projects="store.projects"
      :busy="agent.creating.value"
      @choose="(project) => createConversation(project.path, project.title)"
      @create-project="openProjectChooser"
      @close="newConversationOpen = false"
    />
    <button v-if="railOpen || inspectorOpen" class="pa-panel-backdrop" aria-label="关闭侧栏" @click="railOpen = false; inspectorOpen = false"></button>
  </div>
</template>
