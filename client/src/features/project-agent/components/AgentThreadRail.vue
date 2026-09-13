<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import {
  Archive,
  BookOpenText,
  Bot,
  Boxes,
  FileCheck2,
  MessageSquarePlus,
  Orbit,
  Palette,
  Radio,
  Search,
} from "lucide-vue-next";
import type { ProjectAgentSessionSummary } from "@/features/project-agent/types";

const props = defineProps<{
  sessions: ProjectAgentSessionSummary[];
  activeSessionId?: string;
  projectTitle: string;
  projectProgress?: number | null;
  disabled?: boolean;
}>();
const emit = defineEmits<{ create: []; select: [sessionId: string] }>();
const query = ref("");
const filteredSessions = computed(() => {
  const value = query.value.trim().toLowerCase();
  return value ? props.sessions.filter((item) => item.title.toLowerCase().includes(value)) : props.sessions;
});

function relativeDate(value: string): string {
  const time = new Date(value).getTime();
  if (!Number.isFinite(time)) return "";
  const days = Math.floor((Date.now() - time) / 86_400_000);
  if (days <= 0) return "今天";
  if (days === 1) return "昨天";
  return `${days} 天前`;
}
</script>

<template>
  <aside class="pa-thread-rail">
    <div class="pa-brand"><span class="pa-brand-mark"><i></i><i></i></span><div><strong>ArcVellum</strong><small>文学项目 Agent</small></div></div>
    <div class="pa-mode-switch" aria-label="主工作模式">
      <RouterLink to="/agent" class="active"><Bot :size="15" />Agent</RouterLink>
      <RouterLink to="/overview"><Orbit :size="15" />星仪</RouterLink>
    </div>
    <button class="pa-new-thread" :disabled="disabled" @click="emit('create')"><MessageSquarePlus :size="16" />新对话</button>
    <label class="pa-thread-search"><Search :size="14" /><input v-model="query" placeholder="搜索会话" /></label>

    <div class="pa-thread-section-label">最近对话</div>
    <div class="pa-thread-list">
      <button v-for="item in filteredSessions" :key="item.session_id" :class="{ active: item.session_id === activeSessionId }" :disabled="disabled" @click="emit('select', item.session_id)">
        <span class="pa-thread-dot"></span><span><strong>{{ item.title }}</strong><small>{{ relativeDate(item.updated_at) }}</small></span>
      </button>
      <p v-if="!filteredSessions.length" class="pa-thread-empty">还没有项目对话。</p>
    </div>

    <div class="pa-workspace-links">
      <span>查看作品</span>
      <RouterLink to="/reader"><BookOpenText :size="14" />正文长卷</RouterLink>
      <RouterLink to="/observatory"><Radio :size="14" />创作现场</RouterLink>
      <RouterLink to="/archive"><Archive :size="14" />作品档案</RouterLink>
      <RouterLink to="/style"><Palette :size="14" />文风成果</RouterLink>
      <RouterLink to="/quality"><Boxes :size="14" />质量与规则</RouterLink>
      <RouterLink to="/delivery"><FileCheck2 :size="14" />交付状态</RouterLink>
    </div>

    <div class="pa-project-chip">
      <span>{{ projectTitle.slice(0, 1) }}</span><div><strong>{{ projectTitle }}</strong><small>{{ projectProgress == null ? '正在读取进度' : `全书 ${Math.round(projectProgress)}%` }}</small></div>
    </div>
  </aside>
</template>
