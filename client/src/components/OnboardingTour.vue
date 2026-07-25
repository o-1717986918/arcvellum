<script setup lang="ts">
import { computed } from "vue";
import GuidedTour from "@/features/onboarding/components/GuidedTour.vue";
import type { GuidedTourStep } from "@/features/onboarding/types";

const props = defineProps<{ active: boolean; hasProject: boolean }>();
const emit = defineEmits<{ complete: []; dismiss: [] }>();

const steps = computed<GuidedTourStep[]>(() => [
  {
    targetId: "project",
    eyebrow: "第一步",
    title: props.hasProject ? "作品已经就位" : "先建立或选择一部作品",
    body: props.hasProject ? "所有正文、人物、世界观和创作进度都归属于当前作品。这里可以随时切换。" : "ArcVellum 会为每部作品保存独立的正文、人物、世界观和创作进度。",
  },
  ...(props.hasProject ? [{
    targetId: "orrery",
    eyebrow: "沉浸工作台",
    title: "从这里进入叙事星仪",
    body: "这是 ArcVellum 的核心视图。星图展示真实的场景、人物与推进状态，仪表盘可打开全部项目功能。",
  }] : []),
  {
    targetId: "navigation",
    eyebrow: "作品工作区",
    title: "需要精细操作时，使用项目导航",
    body: "阅读、作品档案、创作规则和交付都在这里。页面展示经过包装，不需要直接处理项目文件。",
  },
  {
    targetId: "advisor",
    eyebrow: "自然语言控制台",
    title: "随时和创作顾问谈一谈",
    body: "你可以讨论人物与结构，也可以让顾问准备任务、记录方向或控制连续创作。正式写回仍由门禁保护。",
  },
  {
    targetId: "help",
    eyebrow: "随时回来",
    title: "忘了操作，不必硬记",
    body: "使用帮助会根据当前状态解释下一步，也可以从那里重新打开这份引导。",
  },
]);
</script>

<template>
  <GuidedTour
    :active="active"
    :steps="steps"
    complete-label="开始创作"
    @complete="emit('complete')"
    @dismiss="emit('dismiss')"
  />
</template>
