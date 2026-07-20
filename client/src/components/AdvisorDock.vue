<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowUp,
  Bell,
  BookOpenCheck,
  ChevronDown,
  CircleDotDashed,
  MessageCircleMore,
  Minimize2,
  PanelLeftClose,
  PanelRightClose,
  Pause,
  ShieldCheck,
  Sparkles,
  UserRoundPen,
  X,
} from "lucide-vue-next";
import { api, connectEventStream, query, streamApi, type EventStreamConnection } from "@/services/api";
import { friendlyError, useAppStore } from "@/stores/app";
import type { AdvisorAction, AdvisorAnswer, AdvisorMessage, AdvisorSession } from "@/types/api";

const store = useAppStore();
const route = useRoute();
const router = useRouter();
const open = ref(false);
const loadingSession = ref(false);
const thinking = ref(false);
const question = ref("");
const session = ref<AdvisorSession | null>(null);
const transientMessages = ref<AdvisorMessage[]>([]);
const thread = ref<HTMLElement | null>(null);
const actionBusy = ref("");
const personas = ref<Record<string, unknown>[]>([]);
const selectedPersona = ref("chief-editor");
const personaEditorOpen = ref(false);
const customPersona = ref({ name: "", tagline: "", prompt: "" });
const inbox = ref<Record<string, unknown>[]>([]);
const unreadCount = ref(0);
const inboxSettings = ref({ mode: "standard", quiet_start: "22:30", quiet_end: "08:00" });
const dockSide = ref<"left" | "right">((localStorage.getItem("arcvellum.advisorSide") as "left" | "right") || "right");
let requestController: AbortController | null = null;
let inboxStream: EventStreamConnection | null = null;

const messages = computed(() => transientMessages.value.length ? transientMessages.value : session.value?.messages || []);
const projectTitle = computed(() => store.currentProject?.title || "当前作品");
const inboxUnreadCount = computed(() => inbox.value.filter((item) => Boolean(item.unread)).length);

watch(
  () => store.currentProjectPath,
  () => {
    session.value = null;
    transientMessages.value = [];
    inboxStream?.close();
    inboxStream = null;
    inbox.value = [];
    unreadCount.value = 0;
    if (store.currentProjectPath) void loadAdvisorSurface();
    if (open.value && store.currentProjectPath) void ensureSession();
  },
);

onMounted(() => {
  window.addEventListener("keydown", globalKeydown);
  if (store.currentProjectPath) void loadAdvisorSurface();
});
onBeforeUnmount(() => {
  window.removeEventListener("keydown", globalKeydown);
  requestController?.abort();
  inboxStream?.close();
});

async function toggle(): Promise<void> {
  open.value = !open.value;
  if (open.value && store.currentProjectPath) await ensureSession();
}

async function loadAdvisorSurface(): Promise<void> {
  if (!store.currentProjectPath) return;
  const [catalog, notices] = await Promise.all([
    api<{ selected_persona: string; items: Record<string, unknown>[] }>(
      `/advisor/personas?${query({ project_root: store.currentProjectPath })}`,
    ),
    api<{ items: Record<string, unknown>[]; unread_count: number; notification_count?: number; settings?: { mode: string; quiet_start: string; quiet_end: string } }>(
      `/advisor/inbox?${query({ project_root: store.currentProjectPath })}`,
    ),
  ]).catch(() => [
    { selected_persona: "chief-editor", items: [] as Record<string, unknown>[] },
    { items: [] as Record<string, unknown>[], unread_count: 0, notification_count: 0, settings: undefined },
  ]);
  personas.value = [...(catalog.items || [])];
  selectedPersona.value = catalog.selected_persona || "chief-editor";
  inbox.value = [...(notices.items || [])];
  unreadCount.value = notices.notification_count ?? notices.unread_count ?? 0;
  if (notices.settings) inboxSettings.value = notices.settings;
  inboxStream?.close();
  inboxStream = connectEventStream(
    `/advisor/inbox/stream?${query({ project_root: store.currentProjectPath, interval_seconds: 8 })}`,
    (event, data) => {
      if (event !== "advisor.inbox") return;
      inbox.value = (data.items || []) as Record<string, unknown>[];
      unreadCount.value = Number(data.notification_count ?? data.unread_count ?? 0);
    },
  );
}

async function choosePersona(): Promise<void> {
  if (!store.currentProjectPath) return;
  const result = await api<{ selected_persona: string; items: Record<string, unknown>[] }>("/advisor/personas/selection", {
    method: "PUT",
    body: JSON.stringify({ project_root: store.currentProjectPath, persona_id: selectedPersona.value }),
  });
  personas.value = result.items || personas.value;
  store.notice = `顾问已切换为${String(personas.value.find((item) => item.persona_id === selectedPersona.value)?.name || "新人格")}。`;
}

async function saveCustomPersona(): Promise<void> {
  const result = await api<{ persona: Record<string, unknown> }>("/advisor/personas/custom", {
    method: "PUT",
    body: JSON.stringify(customPersona.value),
  });
  await loadAdvisorSurface();
  selectedPersona.value = String(result.persona.persona_id || "chief-editor");
  await choosePersona();
  personaEditorOpen.value = false;
}

async function saveInboxSettings(): Promise<void> {
  if (!store.currentProjectPath) return;
  const result = await api<{ settings: { mode: string; quiet_start: string; quiet_end: string } }>("/advisor/inbox/settings", {
    method: "PUT",
    body: JSON.stringify({ project_root: store.currentProjectPath, ...inboxSettings.value }),
  });
  inboxSettings.value = result.settings;
  store.notice = "顾问主动提醒偏好已保存。";
}

async function markNotice(item: Record<string, unknown>, run = false): Promise<void> {
  if (item.unread) {
    await api(`/advisor/inbox/${encodeURIComponent(String(item.item_id))}`, {
      method: "PATCH",
      body: JSON.stringify({ read: true }),
    });
    item.unread = false;
    unreadCount.value = Math.max(0, unreadCount.value - 1);
  }
  if (run && item.action && typeof item.action === "object") await runAction(item.action as AdvisorAction);
}

async function ensureSession(): Promise<void> {
  if (session.value || loadingSession.value || !store.currentProjectPath) return;
  loadingSession.value = true;
  try {
    const list = await api<{ items: Array<Pick<AdvisorSession, "session_id">> }>(
      `/advisor/sessions?${query({ project_root: store.currentProjectPath })}`,
    );
    if (list.items?.[0]?.session_id) {
      session.value = await api<AdvisorSession>(`/advisor/sessions/${encodeURIComponent(list.items[0].session_id)}`);
    } else {
      session.value = await api<AdvisorSession>("/advisor/sessions", {
        method: "POST",
        body: JSON.stringify({ project_root: store.currentProjectPath, title: `${projectTitle.value}创作对话` }),
      });
    }
    await scrollToEnd();
  } catch (cause) {
    store.error = friendlyError(cause, "暂时无法建立顾问对话。");
  } finally {
    loadingSession.value = false;
  }
}

async function ask(): Promise<void> {
  const value = question.value.trim();
  if (!value || thinking.value || !store.currentProjectPath) return;
  await ensureSession();
  if (!session.value) return;
  question.value = "";
  thinking.value = true;
  const optimistic: AdvisorMessage[] = [
    ...(session.value.messages || []),
    { role: "user", payload: { question: value } },
    { role: "advisor", payload: { message: "", evidence: [], uncertainties: [], suggested_actions: [] } },
  ];
  transientMessages.value = optimistic;
  await scrollToEnd();
  try {
    requestController = new AbortController();
    await streamApi(
      `/advisor/sessions/${encodeURIComponent(session.value.session_id)}/ask/stream`,
      {
        method: "POST",
        signal: requestController.signal,
        body: JSON.stringify({
          question: value,
          timeout: 240,
          context: { view: String(route.name || "overview"), user_intent: "free_conversation" },
        }),
      },
      (event, data) => {
        const current = transientMessages.value.at(-1);
        if (!current || current.role !== "advisor") return;
        if (event === "advisor.delta") current.payload.message = String(current.payload.message || "") + String(data.text || "");
        if (event === "advisor.result") {
          const answer = (data.answer || {}) as AdvisorAnswer;
          current.payload = answer;
        }
        if (event === "advisor.error") throw new Error(String(data.message || "顾问暂时没有完成回答。"));
        void scrollToEnd();
      },
    );
    session.value = await api<AdvisorSession>(`/advisor/sessions/${encodeURIComponent(session.value.session_id)}`);
    transientMessages.value = [];
  } catch (cause) {
    const current = transientMessages.value.at(-1);
    if (current && !(cause instanceof DOMException && cause.name === "AbortError")) {
      current.payload.message = friendlyError(cause, "顾问暂时没有完成回答，请重试。");
    }
  } finally {
    requestController = null;
    thinking.value = false;
    await scrollToEnd();
  }
}

async function runAction(action: AdvisorAction): Promise<void> {
  if (!store.currentProjectPath || actionBusy.value) return;
  actionBusy.value = action.label;
  try {
    if (action.type === "open_view") {
      await router.push(`/${action.target || "overview"}`);
      open.value = false;
    } else if (action.type === "record_direction") {
      await api("/projects/directions", {
        method: "POST",
        body: JSON.stringify({ project_root: store.currentProjectPath, message: action.message || action.label }),
      });
      store.notice = "这条想法已经交给创作流程。";
    } else if (action.type === "prepare_next_task") {
      await api("/worker/prepare", {
        method: "POST",
        body: JSON.stringify({ project_root: store.currentProjectPath, route: "scene-development", runtime: "opencode" }),
      });
      store.notice = "下一项创作任务已经准备好。";
      await store.loadDashboard();
    } else if (action.type === "pause_autopilot") {
      const state = await api<{ run?: { run_id: string; status: string } }>(
        `/autopilot/status?${query({ project_root: store.currentProjectPath })}`,
      );
      if (state.run?.run_id && state.run.status === "running") {
        await api(`/autopilot/runs/${state.run.run_id}/pause`, {
          method: "POST",
          body: JSON.stringify({ reason: "advisor-user-request" }),
        });
        store.notice = "连续创作已经暂停。";
      }
    } else if (action.type === "request_revision") {
      await api("/projects/directions", {
        method: "POST",
        body: JSON.stringify({ project_root: store.currentProjectPath, message: `修订方向：${action.message || action.label}` }),
      });
      store.notice = "修订要求已经加入创作方向。";
    }
  } catch (cause) {
    store.error = friendlyError(cause, "这个动作暂时无法完成。");
  } finally {
    actionBusy.value = "";
  }
}

function stopAnswer(): void {
  requestController?.abort();
}

function switchSide(): void {
  dockSide.value = dockSide.value === "right" ? "left" : "right";
  localStorage.setItem("arcvellum.advisorSide", dockSide.value);
}

function globalKeydown(event: KeyboardEvent): void {
  if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "a") {
    event.preventDefault();
    void toggle();
  }
}

function keydown(event: KeyboardEvent): void {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void ask();
  }
}

async function scrollToEnd(): Promise<void> {
  await nextTick();
  if (thread.value) thread.value.scrollTop = thread.value.scrollHeight;
}
</script>

<template>
  <button
    class="advisor-orb"
    :class="{ open }"
    :disabled="!store.hasProject"
    :title="store.hasProject ? '打开创作顾问' : '先选择一部作品'"
    @click="toggle"
  >
    <span class="advisor-orb-rings" aria-hidden="true"></span>
    <MessageCircleMore v-if="!open" :size="23" />
    <Minimize2 v-else :size="21" />
    <span>顾问</span>
    <i v-if="unreadCount" class="advisor-unread">{{ unreadCount > 9 ? '9+' : unreadCount }}</i>
  </button>

  <Transition name="advisor-panel">
    <aside v-if="open" class="advisor-dock" :class="dockSide" aria-label="ArcVellum 创作顾问">
      <header class="advisor-dock-header">
        <div class="advisor-avatar"><Sparkles :size="18" /></div>
        <div>
          <span>ArcVellum 创作顾问</span>
          <select v-model="selectedPersona" class="advisor-persona-select" title="选择顾问人格" @change="choosePersona">
            <option v-for="persona in personas" :key="String(persona.persona_id)" :value="persona.persona_id">{{ persona.name }}</option>
          </select>
        </div>
        <span class="advisor-readonly"><ShieldCheck :size="13" />只读</span>
        <button class="icon-button dock-switch" title="自定义顾问人格" @click="personaEditorOpen = !personaEditorOpen"><UserRoundPen :size="16" /></button>
        <button class="icon-button dock-switch" :title="dockSide === 'right' ? '移到左侧' : '移到右侧'" @click="switchSide">
          <PanelLeftClose v-if="dockSide === 'right'" :size="16" />
          <PanelRightClose v-else :size="16" />
        </button>
        <button class="icon-button" title="收起顾问" @click="open = false"><X :size="17" /></button>
      </header>

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

      <div ref="thread" class="advisor-thread">
        <section v-if="inbox.some((item) => item.unread)" class="advisor-inbox">
          <header><span><Bell :size="14" />顾问主动提醒</span><strong>{{ inboxUnreadCount }}</strong></header>
          <article v-for="item in inbox.filter((notice) => notice.unread).slice(0, 3)" :key="String(item.item_id)" :data-severity="item.severity">
            <div><strong>{{ item.title }}</strong><p>{{ item.message }}</p></div>
            <div><button v-if="item.action" @click="markNotice(item, true)">{{ (item.action as Record<string, unknown>).label || '查看' }}</button><button @click="markNotice(item)">知道了</button></div>
          </article>
        </section>
        <section v-if="!messages.length && !loadingSession" class="advisor-welcome">
          <span class="welcome-symbol"><BookOpenCheck :size="25" /></span>
          <h2>我们聊聊这部作品</h2>
          <p>你可以讨论人物动机、情节取舍、世界规则和下一步方向。顾问会看作品，但不会擅自改动它。</p>
          <button @click="question = '请结合当前进度，告诉我现在最值得决定的创作问题。'; ask()">从当前进度聊起</button>
        </section>

        <div v-if="loadingSession" class="advisor-loading"><CircleDotDashed :size="18" />正在熟悉作品……</div>

        <template v-for="(message, index) in messages" :key="message.sequence || index">
          <article v-if="message.role === 'user'" class="advisor-bubble user">
            {{ message.payload.question }}
          </article>
          <article v-else class="advisor-answer">
            <div class="advisor-avatar small"><Sparkles :size="14" /></div>
            <div class="advisor-answer-body">
              <p v-if="message.payload.message || message.payload.answer">{{ message.payload.message || message.payload.answer }}</p>
              <div v-else class="advisor-thinking"><i></i><i></i><i></i><span>正在阅读作品并思考</span></div>
              <details v-if="message.payload.evidence?.length || message.payload.uncertainties?.length" class="advisor-evidence">
                <summary><ChevronDown :size="14" />查看判断依据</summary>
                <div v-for="item in message.payload.evidence" :key="item.citation + item.statement">
                  <p>{{ item.statement }}</p><small>{{ item.citation }}</small>
                </div>
                <p v-for="item in message.payload.uncertainties" :key="item" class="uncertainty">尚待确认：{{ item }}</p>
              </details>
              <div v-if="message.payload.suggested_actions?.length" class="advisor-actions">
                <button
                  v-for="action in message.payload.suggested_actions"
                  :key="action.label"
                  :disabled="Boolean(actionBusy)"
                  @click="runAction(action)"
                >
                  {{ actionBusy === action.label ? "正在处理……" : action.label }}
                </button>
              </div>
            </div>
          </article>
        </template>
      </div>

      <form class="advisor-composer" @submit.prevent="ask">
        <textarea
          v-model="question"
          rows="2"
          placeholder="说说你的想法，或问一个关于作品的问题……"
          :disabled="thinking || loadingSession"
          @keydown="keydown"
        ></textarea>
        <button v-if="thinking" type="button" title="停止回答" @click="stopAnswer">
          <Pause :size="17" />
        </button>
        <button v-else type="submit" :disabled="!question.trim()" title="发送">
          <ArrowUp :size="18" />
        </button>
        <small>Enter 发送 · Shift + Enter 换行</small>
      </form>
    </aside>
  </Transition>
</template>
