<script setup lang="ts">
import { computed } from "vue";
import { BookOpenText, FolderPlus, X } from "lucide-vue-next";
import type { ProjectSummary } from "@/types/api";

const props = defineProps<{ projects: ProjectSummary[]; busy?: boolean }>();
const emit = defineEmits<{
  choose: [project: ProjectSummary];
  createProject: [];
  close: [];
}>();

const duplicateTitles = computed(() => {
  const counts = new Map<string, number>();
  for (const project of props.projects) counts.set(project.title, (counts.get(project.title) || 0) + 1);
  return new Set([...counts].filter(([, count]) => count > 1).map(([title]) => title));
});

function projectMeta(project: ProjectSummary): string {
  const kind = project.genre || project.work_type || "文学作品";
  const length = project.target_length ? `目标 ${project.target_length.toLocaleString("zh-CN")} 字` : "未设字数目标";
  const status = project.read_only ? "只读" : project.status || "可继续创作";
  if (!duplicateTitles.value.has(project.title)) return `${kind} · ${length} · ${status}`;
  const folder = project.path.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || "未命名目录";
  return `${kind} · ${length} · ${status} · ${folder}`;
}
</script>

<template>
  <div class="pa-dialog-backdrop" @click.self="emit('close')">
    <section class="pa-new-conversation-dialog" role="dialog" aria-modal="true" aria-labelledby="new-conversation-title">
      <header>
        <div><span>新对话</span><h2 id="new-conversation-title">这次想写哪部作品？</h2><p>对话会归属于你选择的作品。之后从会话里进入它的星仪、正文和档案。</p></div>
        <button class="pa-icon-button" title="关闭" @click="emit('close')"><X :size="18" /></button>
      </header>
      <div class="pa-dialog-projects">
        <button v-for="project in projects" :key="project.path" :disabled="busy" @click="emit('choose', project)">
          <BookOpenText :size="18" /><span><strong>{{ project.title }}</strong><small>{{ project.premise || (project.read_only ? '只读演示作品' : '继续这部作品') }}</small><small class="pa-dialog-project-meta">{{ projectMeta(project) }}</small></span>
        </button>
        <p v-if="!projects.length">还没有作品。先建立一部作品，就可以开始专属对话。</p>
      </div>
      <footer><button class="pa-dialog-create" @click="emit('createProject')"><FolderPlus :size="16" />建立或导入作品</button></footer>
    </section>
  </div>
</template>
