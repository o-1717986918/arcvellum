<script setup lang="ts">
import { ref } from "vue";
import { ArrowLeft, Maximize2, Minimize2, RefreshCw } from "lucide-vue-next";
import type { ProjectAgentWorkspaceDescriptor, ProjectAgentWorkspaceId } from "@/features/project-agent/workspaces";

defineProps<{
  workspace: ProjectAgentWorkspaceDescriptor;
  fullscreen: boolean;
}>();
const emit = defineEmits<{ close: []; fullscreen: []; navigate: [workspace: ProjectAgentWorkspaceId] }>();
const revision = ref(0);
</script>

<template>
  <section class="pa-subworkspace" :data-workspace="workspace.id" :aria-label="workspace.title">
    <header class="pa-subworkspace-head">
      <button class="pa-subworkspace-back" type="button" @click="emit('close')"><ArrowLeft :size="16" />返回对话</button>
      <div>
        <span>{{ workspace.scope === "application" ? "应用工作区" : "作品工作区" }}</span>
        <strong>{{ workspace.title }}</strong>
        <small>{{ workspace.description }}</small>
      </div>
      <div class="pa-subworkspace-actions">
        <button class="pa-icon-button" type="button" title="重新读取当前工作区" @click="revision += 1"><RefreshCw :size="16" /></button>
        <button class="pa-icon-button" type="button" :title="fullscreen ? '退出全屏' : '全屏查看'" @click="emit('fullscreen')">
          <Minimize2 v-if="fullscreen" :size="16" />
          <Maximize2 v-else :size="16" />
        </button>
      </div>
    </header>
    <div class="pa-subworkspace-scroll">
      <Suspense>
        <KeepAlive :max="9">
          <component
            :is="workspace.component"
            :key="`${workspace.id}:${revision}`"
            v-bind="workspace.id === 'details' ? { embedded: true } : {}"
            @navigate="emit('navigate', $event)"
          />
        </KeepAlive>
        <template #fallback>
          <div class="pa-subworkspace-state"><i></i><strong>正在打开{{ workspace.title }}</strong><span>当前内容会继续留在 Agent 桌面中。</span></div>
        </template>
      </Suspense>
    </div>
  </section>
</template>
