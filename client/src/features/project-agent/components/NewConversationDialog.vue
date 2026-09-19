<script setup lang="ts">
import { BookOpenText, FolderPlus, X } from "lucide-vue-next";
import type { ProjectSummary } from "@/types/api";

defineProps<{ projects: ProjectSummary[]; busy?: boolean }>();
const emit = defineEmits<{
  choose: [project: ProjectSummary];
  createProject: [];
  close: [];
}>();
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
          <BookOpenText :size="18" /><span><strong>{{ project.title }}</strong><small>{{ project.premise || (project.read_only ? '只读演示作品' : '继续这部作品') }}</small></span>
        </button>
        <p v-if="!projects.length">还没有作品。先建立一部作品，就可以开始专属对话。</p>
      </div>
      <footer><button class="pa-dialog-create" @click="emit('createProject')"><FolderPlus :size="16" />建立或导入作品</button></footer>
    </section>
  </div>
</template>
