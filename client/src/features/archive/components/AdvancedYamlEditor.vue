<script setup lang="ts">
import { ShieldAlert } from "lucide-vue-next";

defineProps<{ modelValue: string; documentFormat?: string }>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();
</script>

<template>
  <label class="archive-source-editor">
    <span>
      <ShieldAlert :size="12" />
      专家模式 · {{ documentFormat === "json" ? "JSON" : "YAML" }} 结构、稳定身份和引用仍会接受确定性检查
    </span>
    <textarea
      spellcheck="false"
      :value="modelValue"
      @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    ></textarea>
  </label>
</template>
