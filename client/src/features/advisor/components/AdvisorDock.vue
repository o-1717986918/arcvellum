<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import {
  ArrowUp,
  Pause,
  PanelLeftClose,
  PanelRightClose,
  ShieldCheck,
  Sparkles,
  UserRoundPen,
  X,
} from "lucide-vue-next";
import AdvisorFloatingShell from "@/features/advisor/components/AdvisorFloatingShell.vue";
import AdvisorMessageThread from "@/features/advisor/components/AdvisorMessageThread.vue";
import { useAdvisorConversation } from "@/features/advisor/composables/useAdvisorConversation";
import {
  advisorClient,
  type AdvisorInboxSettings,
} from "@/features/advisor/services/advisorClient";
import { readCreativeRuntime } from "@/services/runtimePreference";
import { workspaceCommandBus, type WorkspaceCommand, type WorkspaceView } from "@/services/workspaceCommands";
import { friendlyError, useAppStore } from "@/stores/app";
import type { AdvisorAction } from "@/types/api";

const store = useAppStore();
const route = useRoute();
const open = ref(false);
const question = ref("");
const thread = ref<InstanceType<typeof AdvisorMessageThread> | null>(null);
const actionBusy = ref("");
const personas = ref<Record<string, unknown>[]>([]);
const selectedPersona = ref("chief-editor");
const personaEditorOpen = ref(false);
const customPersona = ref({ name: "", tagline: "", prompt: "" });
const inbox = ref<Record<string, unknown>[]>([]);
const unreadCount = ref(0);
const inboxSettings = ref<AdvisorInboxSettings>({ mode: "standard", quiet_start: "22:30", quiet_end: "08:00" });
const projectRoot = computed(() => store.currentProjectPath || "");
const projectTitle = computed(() => store.currentProject?.title || "当前作品");
let inboxStream: { close(): void } | null = null;

const conversation = useAdvisorConversation({
  projectRoot,
  projectTitle,
  context: () => ({ view: String(route.name || "overview"), user_intent: "free_conversation" }),
  onError: (cause, fallback) => { store.error = friendlyError(cause, fallback); },
  afterRender: () => thread.value?.scrollToEnd(),
});

watch(projectRoot, () => {
  conversation.reset();
  closeInboxStream();
  inbox.value = [];
  unreadCount.value = 0;
  if (projectRoot.value) void loadAdvisorSurface();
  if (open.value && projectRoot.value) void conversation.ensureSession();
});
watch(open, (value) => {
  if (value && projectRoot.value) void conversation.ensureSession();
});

onMounted(() => {
  if (projectRoot.value) void loadAdvisorSurface();
});
onBeforeUnmount(closeInboxStream);

async function loadAdvisorSurface(): Promise<void> {
  if (!projectRoot.value) return;
  const surface = await advisorClient.surface(projectRoot.value).catch(() => ({
    personas: { selected_persona: "chief-editor", items: [] as Record<string, unknown>[] },
    inbox: { items: [] as Record<string, unknown>[], unread_count: 0, notification_count: 0, settings: undefined },
  }));
  personas.value = [...(surface.personas.items || [])];
  selectedPersona.value = surface.personas.selected_persona || "chief-editor";
  inbox.value = [...(surface.inbox.items || [])];
  unreadCount.value = surface.inbox.notification_count ?? surface.inbox.unread_count ?? 0;
  if (surface.inbox.settings) inboxSettings.value = surface.inbox.settings;
  closeInboxStream();
  inboxStream = advisorClient.observeInbox(projectRoot.value, (data) => {
    inbox.value = data.items || [];
    unreadCount.value = Number(data.notification_count ?? data.unread_count ?? 0);
  });
}

function closeInboxStream(): void {
  inboxStream?.close();
  inboxStream = null;
}

async function choosePersona(): Promise<void> {
  if (!projectRoot.value) return;
  const result = await advisorClient.selectPersona(projectRoot.value, selectedPersona.value);
  personas.value = result.items || personas.value;
  const selected = personas.value.find((item) => item.persona_id === selectedPersona.value);
  store.notice = `顾问已切换为${String(selected?.name || "新人格")}。`;
}

async function saveCustomPersona(): Promise<void> {
  const result = await advisorClient.saveCustomPersona(customPersona.value);
  await loadAdvisorSurface();
  selectedPersona.value = String(result.persona.persona_id || "chief-editor");
  await choosePersona();
  personaEditorOpen.value = false;
}

async function saveInboxSettings(): Promise<void> {
  if (!projectRoot.value) return;
  const result = await advisorClient.saveInboxSettings(projectRoot.value, inboxSettings.value);
  inboxSettings.value = result.settings;
  store.notice = "顾问主动提醒偏好已保存。";
}

async function markNotice(item: Record<string, unknown>, run: boolean): Promise<void> {
  if (item.unread) {
    await advisorClient.markNotice(String(item.item_id));
    item.unread = false;
    unreadCount.value = Math.max(0, unreadCount.value - 1);
  }
  if (run && item.action && typeof item.action === "object") await runAction(item.action as AdvisorAction);
}

async function submitQuestion(value = question.value): Promise<void> {
  const normalized = value.trim();
  if (!normalized || conversation.thinking.value) return;
  question.value = "";
  await conversation.ask(normalized);
}

function keydown(event: KeyboardEvent): void {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void submitQuestion();
  }
}

async function runAction(action: AdvisorAction): Promise<void> {
  if (!projectRoot.value || actionBusy.value) return;
  actionBusy.value = action.label;
  try {
    const command = advisorCommand(action);
    const result = await workspaceCommandBus.dispatch(command);
    store.notice = result.message;
    if (command.type === "navigate" && result.ok) open.value = false;
  } catch (cause) {
    store.error = friendlyError(cause, "这个动作暂时无法完成。");
  } finally {
    actionBusy.value = "";
  }
}

function advisorCommand(action: AdvisorAction): WorkspaceCommand {
  if (action.type === "open_view") return { type: "navigate", view: workspaceView(action.target) };
  if (action.type === "record_direction") return { type: "record-direction", message: action.message || action.label };
  if (action.type === "run_next_task" || action.type === "prepare_next_task") {
    return { type: "run-route", route: action.route || "auto", runtime: readCreativeRuntime() };
  }
  if (action.type === "start_autopilot") return { type: "start-autopilot", runtime: readCreativeRuntime() };
  if (action.type === "pause_autopilot") return { type: "pause-autopilot", reason: "advisor-user-request" };
  if (action.type === "resume_autopilot") return { type: "resume-autopilot" };
  if (action.type === "request_revision") {
    return { type: "record-direction", message: `修订方向：${action.message || action.label}` };
  }
  throw new Error("这个顾问动作尚未接入工作区控制台。");
}

function workspaceView(value?: string): WorkspaceView {
  const candidate = String(value || "overview") as WorkspaceView;
  const allowed = new Set<WorkspaceView>([
    "projects", "overview", "reader", "archive", "archaeology", "style", "quality",
    "strategy", "observatory", "delivery", "settings", "help", "details", "legal",
  ]);
  return allowed.has(candidate) ? candidate : "overview";
}
</script>

<template>
  <AdvisorFloatingShell v-model:open="open" :disabled="!store.hasProject" :unread-count="unreadCount">
    <template #header="{ side, switchSide, close }">
      <div class="advisor-avatar"><Sparkles :size="18" /></div>
      <div class="advisor-title">
        <span>ArcVellum 创作顾问</span>
        <select v-model="selectedPersona" class="advisor-persona-select" title="选择顾问人格" @change="choosePersona">
          <option v-for="persona in personas" :key="String(persona.persona_id)" :value="persona.persona_id">{{ persona.name }}</option>
        </select>
      </div>
      <span class="advisor-readonly"><ShieldCheck :size="13" />受控操作</span>
      <button class="icon-button dock-switch" title="自定义顾问人格" @click="personaEditorOpen = !personaEditorOpen"><UserRoundPen :size="16" /></button>
      <button class="icon-button dock-switch" :title="side === 'right' ? '移到左侧' : '移到右侧'" @click="switchSide">
        <PanelLeftClose v-if="side === 'right'" :size="16" />
        <PanelRightClose v-else :size="16" />
      </button>
      <button class="icon-button" title="收起顾问" @click="close"><X :size="17" /></button>
    </template>

    <form v-if="personaEditorOpen" class="advisor-persona-editor" @submit.prevent="saveCustomPersona">
      <header><div><strong>自定义顾问人格</strong><small>只改变语言与关注重点，不改变只读权限。</small></div><button type="button" class="icon-button" @click="personaEditorOpen = false"><X :size="15" /></button></header>
      <input v-model.trim="customPersona.name" required maxlength="40" placeholder="人格名称" />
      <input v-model.trim="customPersona.tagline" maxlength="120" placeholder="一句话说明它最关注什么" />
      <textarea v-model.trim="customPersona.prompt" required minlength="80" maxlength="5000" rows="6" placeholder="描述回答节奏、判断重点、反对方式、追问倾向和不应使用的套话。"></textarea>
      <button class="primary-button">保存并使用</button>
      <section class="advisor-notification-settings">
        <strong>主动提醒</strong>
        <select v-model="inboxSettings.mode"><option value="off">全部关闭</option><option value="blocking">只提醒阻塞</option><option value="standard">标准</option><option value="active">积极</option></select>
        <label>免打扰开始<input v-model="inboxSettings.quiet_start" type="time" /></label>
        <label>免打扰结束<input v-model="inboxSettings.quiet_end" type="time" /></label>
        <button type="button" class="secondary-button" @click="saveInboxSettings">保存提醒偏好</button>
      </section>
    </form>

    <AdvisorMessageThread
      ref="thread"
      :messages="conversation.messages.value"
      :inbox="inbox"
      :loading-session="conversation.loadingSession.value"
      :action-busy="actionBusy"
      @starter="submitQuestion('请结合当前进度，告诉我现在最值得决定的创作问题。')"
      @notice="markNotice"
      @action="runAction"
    />

    <form class="advisor-composer" @submit.prevent="submitQuestion()">
      <textarea
        v-model="question"
        rows="2"
        placeholder="说说你的想法，或问一个关于作品的问题……"
        :disabled="conversation.thinking.value || conversation.loadingSession.value"
        @keydown="keydown"
      ></textarea>
      <button v-if="conversation.thinking.value" type="button" title="停止回答" @click="conversation.stop"><Pause :size="17" /></button>
      <button v-else type="submit" :disabled="!question.trim()" title="发送"><ArrowUp :size="18" /></button>
      <small>Enter 发送 · Shift + Enter 换行</small>
    </form>
  </AdvisorFloatingShell>
</template>
