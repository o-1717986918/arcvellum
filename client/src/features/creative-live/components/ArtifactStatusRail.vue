<script setup lang="ts">
import { computed } from "vue";
import { Check, CircleDot, FilePenLine, ShieldCheck, Sparkles } from "lucide-vue-next";
import type { ArtifactIdentity } from "../types";

const props = defineProps<{ identity?: ArtifactIdentity; characters?: number }>();

const stages: Array<{ id: ArtifactIdentity; label: string }> = [
  { id: "streaming_preview", label: "正在形成" },
  { id: "candidate_written", label: "候选已写入" },
  { id: "deterministic_preflight_passed", label: "机器检查通过" },
  { id: "semantic_review_passed", label: "审读通过" },
  { id: "promoted", label: "已晋升正文" },
];
const activeIndex = computed(() => Math.max(0, stages.findIndex((item) => item.id === props.identity)));
</script>

<template>
  <section class="creative-identity-rail" :data-identity="identity || 'waiting'">
    <header><span>稿件身份</span><strong>{{ Number(characters || 0).toLocaleString('zh-CN') }} 字符</strong></header>
    <ol>
      <li v-for="(stage, index) in stages" :key="stage.id" :class="{ complete: index < activeIndex, active: index === activeIndex }">
        <span class="identity-mark"><Check v-if="index < activeIndex" :size="11" /><CircleDot v-else-if="index === activeIndex" :size="12" /><i v-else></i></span>
        <span>{{ stage.label }}</span>
      </li>
    </ol>
    <p v-if="identity === 'validation_failed' || identity === 'rejected'" class="identity-warning"><ShieldCheck :size="13" />本轮候选未通过，正式正文未受影响。</p>
    <p v-else-if="identity === 'revision_streaming' || identity === 'revision_written'"><FilePenLine :size="13" />当前内容属于修订链。</p>
    <p v-else><Sparkles :size="13" />只有完成晋升的稿件才进入阅读长卷。</p>
  </section>
</template>

