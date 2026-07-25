<script setup lang="ts">
import { ref } from "vue";
import { Eye, PenLine } from "lucide-vue-next";
import SafeMarkdown from "@/components/SafeMarkdown.vue";

defineProps<{ modelValue: string }>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();
const mode = ref<"write" | "preview">("write");
</script>

<template>
  <div class="archive-markdown-editor">
    <nav aria-label="长文本编辑方式">
      <button :class="{ active: mode === 'write' }" @click="mode = 'write'">
        <PenLine :size="12" />撰写
      </button>
      <button :class="{ active: mode === 'preview' }" @click="mode = 'preview'">
        <Eye :size="12" />预览
      </button>
    </nav>
    <textarea
      v-if="mode === 'write'"
      :value="modelValue"
      rows="6"
      @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    ></textarea>
    <SafeMarkdown
      v-else
      class="archive-markdown-preview"
      :source="modelValue || '尚未填写内容。'"
      variant="document"
    />
  </div>
</template>
