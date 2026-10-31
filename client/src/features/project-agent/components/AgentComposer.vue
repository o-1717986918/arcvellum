<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { ArrowUp, Check, Paperclip, Square } from "lucide-vue-next";

const props = defineProps<{ disabled?: boolean; busy?: boolean; sessionId?: string }>();
const emit = defineEmits<{ send: [message: string, accepted: () => void]; stop: [] }>();
const value = ref("");
const input = ref<HTMLTextAreaElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const saved = ref(false);
const notice = ref("");
const composing = ref(false);
const storageKey = computed(() => props.sessionId ? `arcvellum.draft.${props.sessionId}` : "");

watch(storageKey, (key) => {
  try { value.value = key ? localStorage.getItem(key) || "" : ""; }
  catch { value.value = ""; }
  notice.value = "";
}, { immediate: true, flush: "sync" });
watch(value, (text) => {
  saved.value = false;
  if (storageKey.value) {
    try {
      if (text) localStorage.setItem(storageKey.value, text);
      else localStorage.removeItem(storageKey.value);
      saved.value = Boolean(text);
    } catch { notice.value = "草稿暂未存入本机，请保持此窗口打开。"; }
  }
  void nextTick(resize);
}, { flush: "sync", immediate: true });

function resize(): void {
  if (!input.value) return;
  input.value.style.height = "auto";
  input.value.style.height = `${Math.min(220, Math.max(56, input.value.scrollHeight))}px`;
}

function submit(): void {
  const message = value.value.trim();
  if (!message || props.disabled || props.busy || composing.value) return;
  const original = value.value;
  const session = props.sessionId;
  emit("send", message, () => {
    // Only the durable turn acknowledgement consumes this exact draft.
    if (props.sessionId === session && value.value === original) value.value = "";
  });
  void nextTick(() => input.value?.focus());
}

function keydown(event: KeyboardEvent): void {
  if (event.isComposing || event.keyCode === 229 || composing.value) return;
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}

function edit(message: string): void {
  value.value = value.value ? `${value.value}\n\n${message}` : message;
  void nextTick(() => input.value?.focus());
}

async function insertText(event: Event): Promise<void> {
  const field = event.target as HTMLInputElement;
  const file = field.files?.[0];
  if (!file) return;
  try {
    edit(`【资料：${file.name}】\n${await file.text()}`);
    notice.value = `已插入 ${file.name}，发送前可编辑。`;
  } catch { notice.value = "没有读到这份文本，请重新选择。"; }
  field.value = "";
}
defineExpose({ edit, focus: () => input.value?.focus() });
</script>

<template>
  <footer class="pa-composer-shell">
    <form class="pa-composer" @submit.prevent="submit">
      <textarea ref="input" v-model="value" rows="2" aria-label="给 ArcVellum 的消息" :disabled="disabled"
        :placeholder="busy ? '回答正在进行，可以先写下一个想法…' : '写下你的想法，让作品继续。'"
        @keydown="keydown" @compositionstart="composing = true" @compositionend="composing = false"></textarea>
      <div class="pa-composer-foot">
        <input ref="fileInput" class="pa-file-input" type="file" accept=".txt,.md,.markdown,text/plain,text/markdown" tabindex="-1" @change="insertText" />
        <button type="button" class="pa-icon-button" :disabled="disabled" title="插入文本资料（TXT、MD）" @click="fileInput?.click()"><Paperclip :size="16" /></button>
        <span class="pa-draft-status" role="status"><Check v-if="saved" :size="12" />{{ saved ? '草稿已保存于本机' : '想法 · 资料 · 创作方向' }}</span>
        <button v-if="busy" type="button" class="pa-send pa-stop" title="停止当前回答" @click="emit('stop')"><Square :size="15" /></button>
        <button v-else type="submit" class="pa-send" :disabled="disabled || !value.trim()" title="发送"><ArrowUp :size="17" /></button>
      </div>
    </form>
    <small v-if="notice" role="status">{{ notice }}</small>
    <small v-else>Enter 发送 · Shift + Enter 换行</small>
  </footer>
</template>
