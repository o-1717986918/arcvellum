<script setup lang="ts">
import { computed, ref } from "vue";
import StudioGlyph from "@/components/StudioGlyph.vue";
import {
  Archive,
  BookOpenText,
  Boxes,
  CircleHelp,
  FileCheck2,
  Info,
  MessageSquarePlus,
  MessageCircleMore,
  MessagesSquare,
  Palette,
  Radio,
  ScanSearch,
  Search,
  Settings2,
  Scale,
} from "lucide-vue-next";
import type { ProjectAgentSessionSummary } from "@/features/project-agent/types";
import type { ProjectAgentWorkspaceId } from "@/workspaces/projectAgentWorkspaceRegistry";

const props = defineProps<{
  sessions: ProjectAgentSessionSummary[];
  activeSessionId?: string;
  projectTitle: string;
  projectProgress?: number | null;
  projectLabels?: Record<string, string>;
  disabled?: boolean;
  hasProject?: boolean;
  activeWorkspace?: ProjectAgentWorkspaceId | null;
}>();
const emit = defineEmits<{
  create: [];
  select: [sessionId: string];
  workspace: [workspace: ProjectAgentWorkspaceId];
  command: [];
}>();
const query = ref("");
const showAllSessions = ref(false);
const defaultSessionLimit = 8;
const filteredSessions = computed(() => {
  const value = query.value.trim().toLowerCase();
  return value ? props.sessions.filter((item) =>
    item.title.toLowerCase().includes(value) || (props.projectLabels?.[item.project_root] || "").toLowerCase().includes(value),
  ) : props.sessions;
});
const visibleSessions = computed(() => {
  if (query.value.trim() || showAllSessions.value || filteredSessions.value.length <= defaultSessionLimit) {
    return filteredSessions.value;
  }
  const recent = filteredSessions.value.slice(0, defaultSessionLimit);
  const active = filteredSessions.value.find((item) => item.session_id === props.activeSessionId);
  return active && !recent.some((item) => item.session_id === active.session_id) ? [...recent, active] : recent;
});
const hiddenSessionCount = computed(() => filteredSessions.value.length - visibleSessions.value.length);

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
  <aside id="studio-navigation" class="pa-thread-rail" aria-label="工作室导航">
    <div class="pa-brand"><StudioGlyph class="pa-brand-glyph" /><div><strong>ArcVellum</strong><small>文学创作工作室</small></div></div>
    <button class="pa-new-thread" data-tour-id="navigation" :disabled="disabled" @click="emit('create')"><MessageSquarePlus :size="16" />新对话</button>
    <button class="pa-command-entry" @click="emit('command')"><Search :size="14" /><span>快速切换</span><kbd>⌘ / Ctrl K</kbd></button>
    <div class="pa-navigation-scroll">
    <label class="pa-thread-search"><Search :size="14" /><input v-model="query" aria-label="搜索会话" placeholder="搜索会话" /></label>

    <div class="pa-thread-section-label">最近对话</div>
    <div class="pa-thread-list">
      <button v-for="item in visibleSessions" :key="item.session_id" :class="{ active: item.session_id === activeSessionId }" :disabled="disabled" @click="emit('select', item.session_id)">
        <span class="pa-thread-dot"></span><span><strong>{{ item.title }}</strong><small>{{ projectLabels?.[item.project_root] || '作品库会话' }} · {{ relativeDate(item.updated_at) }}</small></span>
      </button>
      <p v-if="!filteredSessions.length" class="pa-thread-empty">{{ query ? '没有匹配的会话，试试作品名称。' : '还没有项目对话。' }}</p>
      <button v-if="hiddenSessionCount > 0" class="pa-thread-more" type="button" @click="showAllSessions = true">显示其余 {{ hiddenSessionCount }} 个对话</button>
      <button v-else-if="showAllSessions && !query.trim() && filteredSessions.length > defaultSessionLimit" class="pa-thread-more" type="button" @click="showAllSessions = false">收起历史对话</button>
    </div>

    <div class="pa-workspace-links">
      <span>阅读与创作</span>
      <button :disabled="!hasProject" :class="{ active: activeWorkspace === 'reader' }" @click="emit('workspace', 'reader')"><BookOpenText :size="14" />正文长卷</button>
      <button :disabled="!hasProject" :class="{ active: activeWorkspace === 'character-chat' }" @click="emit('workspace', 'character-chat')"><MessagesSquare :size="14" />与角色交谈</button>
      <button :disabled="!hasProject" :class="{ active: activeWorkspace === 'live' }" @click="emit('workspace', 'live')"><Radio :size="14" />创作现场</button>
      <button :disabled="!hasProject" :class="{ active: activeWorkspace === 'rehearsal' }" @click="emit('workspace', 'rehearsal')"><MessageCircleMore :size="14" />推演观察</button>
      <span class="pa-nav-subgroup">作品研究</span>
      <button :disabled="!hasProject" :class="{ active: activeWorkspace === 'archive' }" @click="emit('workspace', 'archive')"><Archive :size="14" />作品档案</button>
      <button :disabled="!hasProject" :class="{ active: activeWorkspace === 'style' }" @click="emit('workspace', 'style')"><Palette :size="14" /><span>文风成果<small class="pa-feature-note">开发中，不完善</small></span></button>
      <button :disabled="!hasProject" :class="{ active: activeWorkspace === 'quality' }" @click="emit('workspace', 'quality')"><Boxes :size="14" />质量与节奏</button>
      <button :disabled="!hasProject" :class="{ active: activeWorkspace === 'archaeology' }" @click="emit('workspace', 'archaeology')"><ScanSearch :size="14" /><span>作品考古<small class="pa-feature-note">开发中，不完善</small></span></button>
      <button :disabled="!hasProject" :class="{ active: activeWorkspace === 'delivery' }" @click="emit('workspace', 'delivery')"><FileCheck2 :size="14" />交付状态</button>
    </div>

    <div class="pa-workspace-links pa-application-links" data-tour-id="help">
      <span>应用</span>
      <button :class="{ active: activeWorkspace === 'settings' }" @click="emit('workspace', 'settings')"><Settings2 :size="14" />设置</button>
      <button :class="{ active: activeWorkspace === 'help' }" @click="emit('workspace', 'help')"><CircleHelp :size="14" />使用帮助</button>
      <button :class="{ active: activeWorkspace === 'details' }" @click="emit('workspace', 'details')"><Info :size="14" />作品与应用</button>
      <button :class="{ active: activeWorkspace === 'legal' }" @click="emit('workspace', 'legal')"><Scale :size="14" />协议与隐私</button>
    </div>

    </div>
    <button class="pa-project-chip" data-tour-id="project" title="打开作品库" @click="emit('workspace', 'projects')">
      <span>{{ hasProject ? projectTitle.slice(0, 1) : '＋' }}</span><div><strong>{{ hasProject ? projectTitle : '作品库' }}</strong><small>{{ hasProject ? (projectProgress == null ? '正在读取正文进度' : `正文 ${Math.round(projectProgress)}% · 切换作品`) : '建立或打开一部作品' }}</small></div>
    </button>
  </aside>
</template>
