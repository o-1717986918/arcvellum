<script setup lang="ts">
import { nextTick, ref } from "vue";
import { ArrowUp, Paperclip } from "lucide-vue-next";

defineProps<{ disabled?: boolean }>();
const emit = defineEmits<{ send: [message: string] }>();
const value = ref("");
const input = ref<HTMLTextAreaElement | null>(null);

function submit(): void {
  const message = value.value.trim();
  if (!message) return;
  emit("send", message);
  value.value = "";
  void nextTick(() => input.value?.focus());
}

function keydown(event: KeyboardEvent): void {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}
</script>

<template>
  <footer class="pa-composer-shell">
    <form class="pa-composer" @submit.prevent="submit">
      <textarea ref="input" v-model="value" rows="2" :disabled="disabled" placeholder="告诉 ArcVellum 你想了解什么，或描述接下来的创作方向……" @keydown="keydown"></textarea>
      <div class="pa-composer-foot">
        <button type="button" class="pa-icon-button" disabled title="资料附件将在后续版本开放"><Paperclip :size="16" /></button>
        <span>可查阅作品，也可按你的明确指令推进</span>
        <button type="submit" class="pa-send" :disabled="disabled || !value.trim()" title="发送"><ArrowUp :size="17" /></button>
      </div>
    </form>
    <small>Enter 发送 · Shift + Enter 换行</small>
  </footer>
</template>
