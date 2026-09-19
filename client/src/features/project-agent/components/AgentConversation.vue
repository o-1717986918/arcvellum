<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import { ArrowUpRight, Bot, BookOpenText, CircleDashed, Radio, Search, Waypoints } from "lucide-vue-next";
import SafeMarkdown from "@/components/SafeMarkdown.vue";
import AgentActionGroup from "@/features/project-agent/components/AgentActionGroup.vue";
import type { ProjectAgentMessage, ProjectAgentTurnActivity } from "@/features/project-agent/types";

const props = defineProps<{
  messages: ProjectAgentMessage[];
  activity: ProjectAgentTurnActivity | null;
  loading: boolean;
  omittedCount: number;
  hasSession?: boolean;
  creativeStatus?: string;
  creativeTask?: string;
  creativePhase?: "active" | "waiting" | "attention" | null;
}>();
const emit = defineEmits<{ starter: [message: string]; newConversation: []; openLive: [] }>();
const scroller = ref<HTMLElement | null>(null);

watch(
  () => [props.messages.length, props.messages.at(-1)?.payload.text, props.activity?.tools.length],
  async () => {
    await nextTick();
    scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: "smooth" });
  },
);

function messageText(message: ProjectAgentMessage): string {
  return String(message.payload.text || "");
}
</script>

<template>
  <div ref="scroller" class="pa-conversation">
    <div class="pa-conversation-inner">
      <div class="pa-manuscript-spine" aria-hidden="true"></div>
      <p v-if="omittedCount" class="pa-history-note">较早的 {{ omittedCount }} 条消息已收起，完整记录仍保存在当前会话中。</p>
      <section v-if="!messages.length && !loading" class="pa-welcome">
        <span class="pa-welcome-mark"><Bot :size="24" /></span>
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
        </article>
        <article v-else-if="message.role === 'assistant'" class="pa-turn pa-turn-agent">
          <header><span class="pa-mini-mark"><BookOpenText :size="13" /></span><strong>ArcVellum</strong><time v-if="message.at">{{ new Date(message.at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}</time></header>
          <SafeMarkdown v-if="messageText(message)" :source="messageText(message)" variant="chat" />
          <div v-else class="pa-thinking"><i></i><i></i><i></i><span>正在阅读作品并形成回答</span></div>
        </article>
      </template>

      <button v-if="hasSession && creativePhase" class="pa-creative-live-card" :class="creativePhase" @click="emit('openLive')">
        <span class="pa-live-indicator"><Radio :size="17" /></span>
        <span><small>{{ creativePhase === 'active' ? '创作正在进行' : creativePhase === 'waiting' ? '创作等待继续' : '创作需要处理' }}</small><strong>{{ creativeStatus || creativeTask || '查看作品创作状态' }}</strong><em>{{ creativePhase === 'active' ? (creativeTask || '查看创作中的正文、审查与修订') : '打开创作现场，查看原因和继续方式' }}</em></span>
        <ArrowUpRight :size="16" />
      </button>

      <AgentActionGroup v-if="activity" :activity="activity" />
    </div>
  </div>
</template>
