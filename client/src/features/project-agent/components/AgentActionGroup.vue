<script setup lang="ts">
import { computed, ref } from "vue";
import { Check, ChevronDown, CircleAlert, CircleDashed, LoaderCircle } from "lucide-vue-next";
import SafeMarkdown from "@/components/SafeMarkdown.vue";
import type { ProjectAgentTurnActivity } from "@/features/project-agent/types";

const props = defineProps<{ activity: ProjectAgentTurnActivity }>();
const open = ref(true);
const elapsed = computed(() => Math.max(0, Math.round((Date.now() - props.activity.startedAt) / 1000)));
</script>

<template>
  <section class="pa-action-group" :data-state="activity.status">
    <button class="pa-action-head" type="button" :aria-expanded="open" @click="open = !open">
      <LoaderCircle v-if="activity.status === 'running' || activity.status === 'queued'" class="pa-spin" :size="15" />
      <CircleAlert v-else-if="activity.status === 'failed'" :size="15" />
      <Check v-else :size="15" />
      <span><strong>{{ activity.statusLabel }}</strong><small>{{ activity.tools.length }} 项资料活动 · {{ elapsed }} 秒</small></span>
      <ChevronDown :size="15" :class="{ rotated: open }" />
    </button>
    <div v-if="open" class="pa-action-body">
      <div v-for="tool in activity.tools" :key="tool.key" class="pa-tool-row">
        <LoaderCircle v-if="tool.status === 'running'" class="pa-spin" :size="13" />
        <CircleAlert v-else-if="tool.status === 'failed'" :size="13" />
        <Check v-else :size="13" />
        <span><strong>{{ tool.label }}</strong><small>{{ tool.name }}</small></span>
      </div>
      <div v-if="!activity.tools.length" class="pa-tool-row pa-tool-waiting">
        <CircleDashed :size="13" /><span><strong>理解你的问题</strong><small>需要项目事实时会自动查阅</small></span>
      </div>
      <details v-if="activity.reasoning" class="pa-reasoning">
        <summary>查看推理过程</summary>
        <SafeMarkdown :source="activity.reasoning" variant="compact" />
      </details>
      <p v-if="activity.inputTokens || activity.outputTokens" class="pa-usage">
        本轮上下文 {{ activity.inputTokens.toLocaleString('zh-CN') }} · 回答 {{ activity.outputTokens.toLocaleString('zh-CN') }} tokens
      </p>
    </div>
  </section>
</template>
