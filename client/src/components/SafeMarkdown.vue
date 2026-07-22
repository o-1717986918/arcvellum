<script setup lang="ts">
import { computed } from "vue";
import { renderSafeMarkdown } from "@/services/markdown";

const props = defineProps<{
  source?: unknown;
  variant?: "compact" | "evidence" | "chat" | "document";
}>();

const html = computed(() => renderSafeMarkdown(props.source ?? ""));
</script>

<template>
  <div class="safe-markdown" :class="`safe-markdown-${variant || 'compact'}`" v-html="html"></div>
</template>
