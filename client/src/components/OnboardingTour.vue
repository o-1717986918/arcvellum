<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ArrowLeft, ArrowRight, Check, Compass, X } from "lucide-vue-next";

const props = defineProps<{ active: boolean; hasProject: boolean }>();
const emit = defineEmits<{ complete: []; dismiss: [] }>();

const index = ref(0);
const targetStyle = ref<Record<string, string>>({ opacity: "0" });
const cardStyle = ref<Record<string, string>>({ left: "50%", top: "50%", transform: "translate(-50%,-50%)" });
let observer: MutationObserver | null = null;

const steps = computed(() => [
  {
    target: "[data-tour='project']",
    eyebrow: "第一步",
    title: props.hasProject ? "作品已经就位" : "先建立或选择一部作品",
    body: props.hasProject ? "所有正文、人物、世界观和创作进度都归属于当前作品。这里可以随时切换。" : "ArcVellum 会为每部作品保存独立的正文、人物、世界观和创作进度。",
  },
  ...(props.hasProject ? [{
    target: "[data-tour='orrery']",
    eyebrow: "沉浸工作台",
    title: "从这里进入叙事星仪",
    body: "这是 ArcVellum 的核心视图。星图展示真实的场景、人物与推进状态，仪表盘可打开全部项目功能。",
  }] : []),
  {
    target: "[data-tour='navigation']",
    eyebrow: "作品工作区",
    title: "需要精细操作时，使用项目导航",
    body: "阅读、作品档案、创作规则和交付都在这里。页面展示经过包装，不需要直接处理项目文件。",
  },
  {
    target: "[data-tour='advisor']",
    eyebrow: "自然语言控制台",
    title: "随时和创作顾问谈一谈",
    body: "你可以讨论人物与结构，也可以让顾问准备任务、记录方向或控制连续创作。正式写回仍由门禁保护。",
  },
  {
    target: "[data-tour='help']",
    eyebrow: "随时回来",
    title: "忘了操作，不必硬记",
    body: "使用帮助会根据当前状态解释下一步，也可以从那里重新打开这份引导。",
  },
]);

const step = computed(() => steps.value[Math.min(index.value, steps.value.length - 1)]);
const last = computed(() => index.value >= steps.value.length - 1);

function updatePosition(): void {
  if (!props.active || !step.value) return;
  const element = document.querySelector<HTMLElement>(step.value.target);
  if (!element) {
    targetStyle.value = { opacity: "0" };
    cardStyle.value = { left: "50%", top: "50%", transform: "translate(-50%,-50%)" };
    return;
  }
  const rect = element.getBoundingClientRect();
  const padding = 7;
  targetStyle.value = {
    opacity: "1",
    left: `${Math.max(4, rect.left - padding)}px`,
    top: `${Math.max(4, rect.top - padding)}px`,
    width: `${Math.max(24, rect.width + padding * 2)}px`,
    height: `${Math.max(24, rect.height + padding * 2)}px`,
  };
  const cardWidth = Math.min(350, window.innerWidth - 28);
  const roomRight = window.innerWidth - rect.right;
  let left = roomRight > cardWidth + 34 ? rect.right + 20 : rect.left - cardWidth - 20;
  let top = Math.min(Math.max(16, rect.top), window.innerHeight - 270);
  if (window.innerWidth <= 620 || left < 14) {
    left = Math.min(Math.max(14, rect.left), window.innerWidth - cardWidth - 14);
    top = rect.bottom + 18;
    if (top + 250 > window.innerHeight) top = Math.max(14, rect.top - 258);
  }
  cardStyle.value = { left: `${left}px`, top: `${top}px`, width: `${cardWidth}px`, transform: "none" };
}

async function move(delta: number): Promise<void> {
  index.value = Math.min(Math.max(0, index.value + delta), steps.value.length - 1);
  await nextTick();
  updatePosition();
}

function finish(): void {
  emit("complete");
}

watch([() => props.active, () => props.hasProject, index], async ([active]) => {
  if (!active) return;
  index.value = Math.min(index.value, steps.value.length - 1);
  await nextTick();
  updatePosition();
});

onMounted(() => {
  window.addEventListener("resize", updatePosition);
  observer = new MutationObserver(updatePosition);
  observer.observe(document.body, { childList: true, subtree: true, attributes: true });
  updatePosition();
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", updatePosition);
  observer?.disconnect();
});
</script>

<template>
  <Teleport to="body">
    <div v-if="active" class="onboarding-tour" role="dialog" aria-modal="true" :aria-label="step.title">
      <div class="onboarding-shield"></div>
      <div class="onboarding-highlight" :style="targetStyle"></div>
      <section class="onboarding-card" :style="cardStyle">
        <header><span><Compass :size="14" />{{ step.eyebrow }}</span><button title="暂时跳过" @click="emit('dismiss')"><X :size="16" /></button></header>
        <h2>{{ step.title }}</h2>
        <p>{{ step.body }}</p>
        <footer>
          <span>{{ index + 1 }} / {{ steps.length }}</span>
          <div>
            <button v-if="index" class="tour-back" @click="move(-1)"><ArrowLeft :size="15" />上一步</button>
            <button v-if="!last" class="tour-next" @click="move(1)">下一步<ArrowRight :size="15" /></button>
            <button v-else class="tour-next" @click="finish">开始创作<Check :size="15" /></button>
          </div>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
