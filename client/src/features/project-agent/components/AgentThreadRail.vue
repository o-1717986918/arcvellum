<script setup lang="ts">
import { computed, ref } from "vue";
import {
  Archive,
  BookOpenText,
  Boxes,
  CircleHelp,
  FileCheck2,
  Info,
  MessageSquarePlus,
  Palette,
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
}>();
const query = ref("");
const filteredSessions = computed(() => {
  const value = query.value.trim().toLowerCase();
  return value ? props.sessions.filter((item) =>
    item.title.toLowerCase().includes(value) || (props.projectLabels?.[item.project_root] || "").toLowerCase().includes(value),
  ) : props.sessions;
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
    <button class="pa-new-thread" data-tour-id="navigation" :disabled="disabled" @click="emit('create')"><MessageSquarePlus :size="16" />新对话</button>
    <label class="pa-thread-search"><Search :size="14" /><input v-model="query" placeholder="搜索会话" /></label>

    <div class="pa-thread-section-label">最近对话</div>
    <div class="pa-thread-list">
      <button v-for="item in filteredSessions" :key="item.session_id" :class="{ active: item.session_id === activeSessionId }" :disabled="disabled" @click="emit('select', item.session_id)">
        <span class="pa-thread-dot"></span><span><strong>{{ item.title }}</strong><small>{{ projectLabels?.[item.project_root] || '作品库会话' }} · {{ relativeDate(item.updated_at) }}</small></span>
      </button>
      <p v-if="!filteredSessions.length" class="pa-thread-empty">还没有项目对话。</p>
    </div>

    <div class="pa-workspace-links">
      <span>查看作品</span>
      <button :disabled="!hasProject" :class="{ active: activeWorkspace === 'reader' }" @click="emit('workspace', 'reader')"><BookOpenText :size="14" />正文长卷</button>
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

    <div class="pa-project-chip" data-tour-id="project">
      <span>{{ hasProject ? projectTitle.slice(0, 1) : '＋' }}</span><div><strong>{{ hasProject ? projectTitle : '作品库总控' }}</strong><small>{{ hasProject ? (projectProgress == null ? '正在读取进度' : `全书 ${Math.round(projectProgress)}%`) : '可以让 Agent 建立作品' }}</small></div>
    </div>
  </aside>
</template>
