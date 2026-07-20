<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ChevronLeft, ChevronRight, Maximize2, Minimize2 } from "lucide-vue-next";
import { displayValue } from "@/services/presentation";

const props = defineProps<{ items: Record<string, unknown>[]; compact?: boolean }>();
const index = ref(0);
const expanded = ref(false);
const current = computed(() => props.items[index.value] || null);

watch(
  () => props.items.length,
  () => {
    if (index.value >= props.items.length) index.value = 0;
  },
);
</script>

<template>
  <section class="manuscript-reader" :class="{ expanded, compact }">
    <header>
      <div>
        <span class="eyebrow">正式正文</span>
        <h2>{{ current?.title || "尚未形成正式正文" }}</h2>
        <p v-if="current">{{ current.subtitle || current.status }} · {{ displayValue(current.badges) }}</p>
      </div>
      <div class="reader-actions" v-if="current">
        <button class="icon-button" title="上一节" :disabled="index === 0" @click="index--"><ChevronLeft :size="18" /></button>
        <span>{{ index + 1 }} / {{ items.length }}</span>
        <button class="icon-button" title="下一节" :disabled="index >= items.length - 1" @click="index++"><ChevronRight :size="18" /></button>
        <button class="icon-button" :title="expanded ? '收回阅读器' : '展开阅读器'" @click="expanded = !expanded">
          <Minimize2 v-if="expanded" :size="18" /><Maximize2 v-else :size="18" />
        </button>
      </div>
    </header>
    <div class="reader-scroll" tabindex="0">
      <article v-if="current">
        <p v-for="(paragraph, paragraphIndex) in String(current.body || current.excerpt || '').split(/\n{2,}/)" :key="paragraphIndex">
          {{ paragraph.replace(/^#+\s*/, "") }}
        </p>
      </article>
      <div v-else class="empty-manuscript">
        <span>稿</span>
        <strong>正文会在通过审查后出现在这里</strong>
        <p>候选稿、流程记录和设定更新不会混入阅读区域。</p>
      </div>
    </div>
  </section>
</template>
