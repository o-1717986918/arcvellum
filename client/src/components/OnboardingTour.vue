<script setup lang="ts">
import { computed } from "vue";
import GuidedTour from "@/onboarding/components/GuidedTour.vue";
import type { GuidedTourStep } from "@/onboarding/types";

const props = defineProps<{ active: boolean; hasProject: boolean }>();
const emit = defineEmits<{ complete: []; dismiss: [] }>();

const steps = computed<GuidedTourStep[]>(() => [
  {
    targetId: "project",
    eyebrow: "第一步",
    title: props.hasProject ? "当前作品在这里" : "先从作品库开始",
    body: props.hasProject ? "正文、人物、世界和创作进度都归属于当前作品。点开作品库可以建立或切换项目。" : "打开左栏的作品库，建立新作品或选择已经存在的项目。",
  },
  ...(props.hasProject ? [{
    targetId: "orrery",
    eyebrow: "另一种视角",
    title: "进入叙事星仪",
    body: "星仪与 Agent 桌面读取同一部作品，用空间关系观察章节、人物与推进状态。",
  }] : []),
  {
    targetId: "navigation",
    eyebrow: "双主界面",
    title: "Agent 与星仪随时切换",
    body: "日常创作留在 Agent；需要观察全书结构时进入星仪。两边共享当前作品和运行状态。",
  },
  {
    targetId: "advisor",
    eyebrow: "自然语言控制台",
    title: "直接告诉 Agent 你要什么",
    body: "它可以查阅作品、记录方向、处理项目决定并继续创作。已开放动作无需逐项审批，正式变化仍由文学内核检查。",
  },
  {
    targetId: "help",
    eyebrow: "应用工作区",
    title: "设置和说明也留在桌面里",
    body: "作品库、模型设置、使用帮助、应用详情与协议都在左栏打开，不会把你带回旧页面。",
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
