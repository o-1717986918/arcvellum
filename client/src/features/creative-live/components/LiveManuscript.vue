<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { BookOpenText, FileClock, PauseCircle, PlayCircle, Radio, Sparkles } from "lucide-vue-next";
import SafeMarkdown from "@/components/SafeMarkdown.vue";
import type { CreativeArtifact } from "../types";
import { artifactKindLabel, artifactStatusLabel, artifactTitle } from "../artifactPresentation";

const props = defineProps<{ artifact?: CreativeArtifact | null }>();
const title = computed(() => artifactTitle(props.artifact));
const isFormal = computed(() => props.artifact?.identity === "promoted");
const renderedContent = ref("");
const scroll = ref<HTMLElement | null>(null);
const following = ref(true);
const animateChanges = ref(true);
let renderTimer = 0;
const displayContent = computed(() => {
  const content = renderedContent.value;
  if (content.length <= 160_000) return content;
  return `> 为保持实时阅读流畅，正在展示候选稿最近部分。完整正文会在写入后保留。\n\n${content.slice(-160_000)}`;
});

watch(() => props.artifact?.content || "", (content) => {
  window.clearTimeout(renderTimer);
  renderTimer = window.setTimeout(async () => {
    renderedContent.value = content;
    await nextTick();
    if (following.value && scroll.value) scroll.value.scrollTop = scroll.value.scrollHeight;
  }, content.length > 30_000 ? 450 : 90);
}, { immediate: true });

onBeforeUnmount(() => window.clearTimeout(renderTimer));

function trackScroll(): void {
  const element = scroll.value;
  if (element) following.value = element.scrollHeight - element.scrollTop - element.clientHeight < 100;
}

function resumeFollowing(): void {
  following.value = true;
  if (scroll.value) scroll.value.scrollTop = scroll.value.scrollHeight;
}
</script>

<template>
  <section class="live-manuscript" :class="{ 'motion-paused': !animateChanges }" :data-identity="artifact?.identity || 'waiting'">
    <header>
      <div>
        <span class="creative-live-kicker"><Radio v-if="artifact?.identity === 'streaming_preview'" :size="12" />{{ artifactKindLabel(artifact) }} · {{ artifactStatusLabel(artifact) }}</span>
        <h2>{{ title }}</h2>
        <p v-if="artifact">{{ isFormal ? '已进入正式项目' : '创作工作区' }} · {{ Number(artifact.characters || artifact.content.length).toLocaleString('zh-CN') }} 字符</p>
      </div>
      <div class="live-manuscript-controls">
        <button v-if="!following" title="回到新增内容" @click="resumeFollowing"><PlayCircle :size="13" />跟随</button>
        <button :title="animateChanges ? '暂停新增文字动效' : '恢复新增文字动效'" @click="animateChanges = !animateChanges"><PauseCircle v-if="animateChanges" :size="13" /><Sparkles v-else :size="13" /></button>
        <span class="manuscript-live-badge" :class="{ active: artifact?.identity === 'streaming_preview' }">{{ artifact?.identity === 'streaming_preview' ? 'LIVE' : isFormal ? 'FORMAL' : 'CANDIDATE' }}</span>
      </div>
    </header>
    <div v-if="artifact?.content" ref="scroll" class="live-manuscript-scroll" @scroll.passive="trackScroll">
      <SafeMarkdown :source="displayContent" variant="document" />
      <i v-if="artifact.identity === 'streaming_preview'" class="writing-caret" aria-label="仍在生成"></i>
    </div>
    <div v-else class="creative-live-empty manuscript-empty">
      <BookOpenText :size="28" />
      <strong>这里会出现正在形成的作品</strong>
      <p>人物、世界观、情节规划、审查意见和正文都会以可读形式呈现。正式正文仍需通过审查与晋升。</p>
      <span><FileClock :size="13" />当前仍在等待可展示的产物</span>
    </div>
  </section>
</template>
