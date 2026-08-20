<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ArrowLeft, ArrowRight, Check, Compass, X } from "lucide-vue-next";
import type { GuidedTourStep } from "../types";

const props = withDefaults(defineProps<{
  active: boolean;
  steps: GuidedTourStep[];
  completeLabel?: string;
}>(), {
  completeLabel: "完成引导",
});
const emit = defineEmits<{ complete: []; dismiss: [] }>();

const index = ref(0);
const targetStyle = ref<Record<string, string>>({ opacity: "0" });
const cardStyle = ref<Record<string, string>>({
  left: "50%",
  top: "50%",
  transform: "translate(-50%,-50%)",
});
let observer: MutationObserver | null = null;

const step = computed(() => props.steps[Math.min(index.value, props.steps.length - 1)]);
const last = computed(() => index.value >= props.steps.length - 1);

function updatePosition(): void {
  if (!props.active || !step.value) return;
  const element = document.querySelector<HTMLElement>(
    `[data-tour-id="${step.value.targetId}"]`,
  );
  if (!element) {
    targetStyle.value = { opacity: "0" };
    cardStyle.value = {
      left: "50%",
      top: "50%",
      transform: "translate(-50%,-50%)",
    };
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
  cardStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
    width: `${cardWidth}px`,
    transform: "none",
  };
}

async function move(delta: number): Promise<void> {
  index.value = Math.min(Math.max(0, index.value + delta), props.steps.length - 1);
  await nextTick();
  updatePosition();
}

watch([() => props.active, () => props.steps, index], async ([active]) => {
  if (!active || !props.steps.length) return;
  index.value = Math.min(index.value, props.steps.length - 1);
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
    <div
      v-if="active && step"
      class="onboarding-tour"
      role="dialog"
      aria-modal="true"
      :aria-label="step.title"
    >
      <div class="onboarding-shield"></div>
      <div class="onboarding-highlight" :style="targetStyle"></div>
      <section class="onboarding-card" :style="cardStyle">
        <header>
          <span><Compass :size="14" />{{ step.eyebrow }}</span>
          <button title="暂时跳过" @click="emit('dismiss')"><X :size="16" /></button>
        </header>
        <h2>{{ step.title }}</h2>
        <p>{{ step.body }}</p>
        <footer>
          <span>{{ index + 1 }} / {{ steps.length }}</span>
          <div>
            <button v-if="index" class="tour-back" @click="move(-1)">
              <ArrowLeft :size="15" />上一步
            </button>
            <button v-if="!last" class="tour-next" @click="move(1)">
              下一步<ArrowRight :size="15" />
            </button>
            <button v-else class="tour-next" @click="emit('complete')">
              {{ completeLabel }}<Check :size="15" />
            </button>
          </div>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
