<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { ArrowDown, ArrowUpRight, BookOpenText, Check, CircleDashed, Copy, PencilLine, Radio, Search, Waypoints } from "lucide-vue-next";
import StudioGlyph from "@/components/StudioGlyph.vue";
import SafeMarkdown from "@/components/SafeMarkdown.vue";
import AgentActionGroup from "@/features/project-agent/components/AgentActionGroup.vue";
import type { ProjectAgentMessage, ProjectAgentTurnActivity } from "@/features/project-agent/types";

const props = defineProps<{
  messages: ProjectAgentMessage[];
  activity: ProjectAgentTurnActivity | null;
  loading: boolean;
  omittedCount: number;
  hasSession?: boolean;
  sessionId?: string;
  creativeStatus?: string;
  creativeTask?: string;
  creativePhase?: "active" | "waiting" | "attention" | null;
}>();
const emit = defineEmits<{ starter: [message: string]; newConversation: []; openLive: []; earlier: []; edit: [message: string]; recover: [] }>();
const scroller = ref<HTMLElement | null>(null);
const following = ref(true);
const unread = ref(false);
const copied = ref(-1);
const copyNotice = ref("");
let previousHeight = 0;

function trackScroll(): void {
  const el = scroller.value;
  if (!el) return;
  following.value = el.scrollHeight - el.scrollTop - el.clientHeight < 90;
  if (following.value) unread.value = false;
}

function jumpToLatest(): void {
  following.value = true;
  unread.value = false;
  scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: "instant" });
}

function earlier(): void {
  previousHeight = scroller.value?.scrollHeight || 0;
  emit("earlier");
}

async function copyMessage(message: ProjectAgentMessage, index: number): Promise<void> {
  try {
    await navigator.clipboard.writeText(messageText(message));
    copied.value = index;
    copyNotice.value = "已复制消息";
  } catch { copyNotice.value = "复制没有完成，可以选择文字后复制。"; }
}
const activityMessageIndex = computed(() => {
  const activity = props.activity;
  if (!activity) return -1;
  const matched = props.messages.findLastIndex((message) => message.role === "assistant" && (
    (activity.turnId && message.payload.turn_id === activity.turnId)
    || (activity.jobId && message.payload.job_id === activity.jobId)
  ));
  if (matched >= 0) return matched;
  const lastAssistant = props.messages.findLastIndex((message) => message.role === "assistant");
  const lastUser = props.messages.findLastIndex((message) => message.role === "user");
  const message = props.messages[lastAssistant];
  return lastAssistant > lastUser && message && !message.payload.turn_id && !message.payload.job_id
    ? lastAssistant : -1;
});

watch(() => props.sessionId, async () => {
  following.value = true;
  unread.value = false;
  copied.value = -1;
  await nextTick();
  jumpToLatest();
});

watch(
  () => [props.messages.length, props.messages.at(-1)?.payload.text, props.activity?.tools.length],
  async () => {
    await nextTick();
    if (previousHeight && scroller.value) {
      scroller.value.scrollTop += scroller.value.scrollHeight - previousHeight;
      previousHeight = 0;
    } else if (following.value) jumpToLatest();
    else unread.value = true;
  },
);

function messageText(message: ProjectAgentMessage): string {
  return String(message.payload.text || "");
}
</script>

<template>
  <div class="pa-conversation-frame">
  <div ref="scroller" class="pa-conversation" aria-label="作品对话" @scroll.passive="trackScroll">
    <div class="pa-conversation-inner">
      <div class="pa-manuscript-spine" aria-hidden="true"></div>
      <button v-if="omittedCount" class="pa-history-note pa-history-more" @click="earlier">查看较早的对话 · 还有 {{ omittedCount }} 条</button>
      <section v-if="!messages.length && !loading" class="pa-welcome">
        <div class="pa-welcome-signature"><StudioGlyph class="pa-welcome-mark" /><span>ArcVellum <i>与你一起，让作品向前。</i></span></div>
        <h1>{{ hasSession ? '从这部作品继续。' : '选择一部作品，开始交谈。' }}</h1>
        <p>{{ hasSession ? '我可以查阅正文与资料，也能接下长期创作目标，在你离开当前对话后持续推进。' : '每段对话属于一部作品。你可以选择已有作品，也可以先建立一部新作品。' }}</p>
        <button v-if="!hasSession" class="pa-welcome-create" @click="emit('newConversation')">选择作品并新建对话 <ArrowUpRight :size="16" /></button>
        <div v-else class="pa-starters">
          <button @click="emit('starter', '结合当前作品状态，告诉我现在最值得关注的创作问题。')"><Waypoints :size="16" /><span><strong>现在最值得关注什么？</strong><small>从进度和作品结构中判断</small></span></button>
          <button @click="emit('starter', '把当前作品设为长期目标，持续创作、审查并推进，直到满足正式交付条件。')"><CircleDashed :size="16" /><span><strong>持续完成到交付</strong><small>启动可恢复的长期目标</small></span></button>
          <button @click="emit('starter', '请在现有正文和项目资料中查找最重要的未解决问题。')"><Search :size="16" /><span><strong>作品还留下哪些问题？</strong><small>检索正文和项目档案</small></span></button>
        </div>
      </section>

      <div v-if="loading" class="pa-loading"><CircleDashed :size="17" />正在打开作品对话……</div>

      <template v-for="(message, index) in messages" :key="message.sequence || `${message.role}-${index}`">
        <article v-if="message.role === 'user'" class="pa-turn pa-turn-user">
          <header><strong>你</strong><time v-if="message.at">{{ new Date(message.at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}</time></header>
          <p>{{ messageText(message) }}</p>
          <div class="pa-message-actions"><button title="重新编辑这条消息" @click="emit('edit', messageText(message))"><PencilLine :size="13" />重新编辑</button></div>
        </article>
        <article v-else-if="message.role === 'assistant'" class="pa-turn pa-turn-agent">
          <header><span class="pa-mini-mark"><BookOpenText :size="13" /></span><strong>ArcVellum</strong><time v-if="message.at">{{ new Date(message.at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}</time></header>
          <AgentActionGroup v-if="activity && activityMessageIndex === index" :key="activity.jobId || activity.turnId || 'pending'" :activity="activity" />
          <SafeMarkdown v-if="messageText(message)" :source="messageText(message)" variant="chat" />
          <div v-else-if="activity && ['queued', 'running'].includes(activity.status) && activityMessageIndex === index" class="pa-thinking"><i></i><i></i><i></i><span>正在阅读作品并形成回答</span></div>
          <p v-else class="pa-history-note">{{ activity?.status === 'cancelled' ? '这次回答已停止，可以继续编辑你的想法。' : '这条记录没有回答正文。' }}</p>
          <div v-if="messageText(message)" class="pa-message-actions"><button :title="copied === index ? '已复制' : '复制回答'" @click="copyMessage(message, index)"><Check v-if="copied === index" :size="13" /><Copy v-else :size="13" />{{ copied === index ? '已复制' : '复制' }}</button></div>
        </article>
      </template>

      <AgentActionGroup v-if="activity && activityMessageIndex < 0" :key="activity.jobId || activity.turnId || 'pending'" :activity="activity" />
      <div v-if="activity?.status === 'failed'" class="pa-recovery-note" role="status"><span>这次回答未完成。可以重新连接查看已保存的进展，或编辑上方消息。</span><button @click="emit('recover')">重新连接</button></div>

      <button v-if="hasSession && creativePhase" class="pa-creative-live-card" :class="creativePhase" @click="emit('openLive')">
        <span class="pa-live-indicator"><Radio :size="17" /></span>
        <span><small>{{ creativePhase === 'active' ? '创作正在进行' : creativePhase === 'waiting' ? '创作等待继续' : '创作需要处理' }}</small><strong>{{ creativeStatus || creativeTask || '查看作品创作状态' }}</strong><em>{{ creativePhase === 'active' ? (creativeTask || '查看创作中的正文、审查与修订') : '打开创作现场，查看原因和继续方式' }}</em></span>
        <ArrowUpRight :size="16" />
      </button>

    </div>
  </div>
    <button v-if="!following" class="pa-jump-latest" @click="jumpToLatest"><ArrowDown :size="14" />{{ unread ? '有新内容 · 回到最新' : '回到最新' }}</button>
    <span class="sr-only" role="status">{{ copyNotice }}</span>
  </div>
</template>
