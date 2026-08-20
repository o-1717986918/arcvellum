<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { Bell, BookOpenCheck, ChevronDown, CircleDotDashed, Sparkles } from "lucide-vue-next";
import SafeMarkdown from "@/components/SafeMarkdown.vue";
import type { AdvisorAction, AdvisorMessage } from "@/types/api";

const props = defineProps<{
  messages: AdvisorMessage[];
  inbox: Record<string, unknown>[];
  loadingSession: boolean;
  actionBusy: string;
}>();
const emit = defineEmits<{
  action: [action: AdvisorAction];
  notice: [item: Record<string, unknown>, run: boolean];
  starter: [];
}>();
const thread = ref<HTMLElement | null>(null);
const unreadItems = computed(() => props.inbox.filter((item) => Boolean(item.unread)));

async function scrollToEnd(): Promise<void> {
  await nextTick();
  if (thread.value) thread.value.scrollTop = thread.value.scrollHeight;
}

defineExpose({ scrollToEnd });
</script>

<template>
  <div ref="thread" class="advisor-thread">
    <section v-if="unreadItems.length" class="advisor-inbox">
      <header><span><Bell :size="14" />顾问主动提醒</span><strong>{{ unreadItems.length }}</strong></header>
      <article v-for="item in unreadItems.slice(0, 3)" :key="String(item.item_id)" :data-severity="item.severity">
        <div><strong>{{ item.title }}</strong><p>{{ item.message }}</p></div>
        <div>
          <button v-if="item.action" type="button" @click="emit('notice', item, true)">{{ (item.action as Record<string, unknown>).label || '查看' }}</button>
          <button type="button" @click="emit('notice', item, false)">知道了</button>
        </div>
      </article>
    </section>
    <section v-if="!messages.length && !loadingSession" class="advisor-welcome">
      <span class="welcome-symbol"><BookOpenCheck :size="25" /></span>
      <h2>我们聊聊这部作品</h2>
      <p>你可以讨论作品，也可以直接说“继续创作”“暂停”“把这条要求记下来”或“打开正文”。顾问会把明确意图变成可确认的安全操作。</p>
      <button type="button" @click="emit('starter')">从当前进度聊起</button>
    </section>

    <div v-if="loadingSession" class="advisor-loading"><CircleDotDashed :size="18" />正在熟悉作品……</div>

    <template v-for="(message, index) in messages" :key="message.sequence || index">
      <article v-if="message.role === 'user'" class="advisor-bubble user">{{ message.payload.question }}</article>
      <article v-else class="advisor-answer">
        <div class="advisor-avatar small"><Sparkles :size="14" /></div>
        <div class="advisor-answer-body">
          <SafeMarkdown
            v-if="message.payload.message || message.payload.answer"
            class="advisor-markdown"
            variant="chat"
            :source="message.payload.message || message.payload.answer"
          />
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
              type="button"
              :disabled="Boolean(actionBusy)"
              @click="emit('action', action)"
            >
              {{ actionBusy === action.label ? "正在处理……" : action.label }}
            </button>
          </div>
        </div>
      </article>
    </template>
  </div>
</template>
