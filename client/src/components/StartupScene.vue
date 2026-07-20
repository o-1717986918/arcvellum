<script setup lang="ts">
import { computed } from "vue";
import { AlertTriangle, Check, LoaderCircle, RefreshCw } from "lucide-vue-next";
import type { BootstrapSnapshot } from "@/types/api";

const props = defineProps<{ snapshot: BootstrapSnapshot | null; error: string }>();
defineEmits<{ continue: []; retry: [] }>();

const currentStep = computed(() =>
  props.snapshot?.steps.find((step) => ["loading", "waiting"].includes(step.status)) ||
  props.snapshot?.steps.find((step) => step.status === "blocked") ||
  props.snapshot?.steps.at(-1),
);
</script>

<template>
  <div class="startup-scene" :data-phase="snapshot?.phase || 'starting'">
    <div class="startup-paper" aria-hidden="true">
      <span class="paper-sheet paper-one"></span>
      <span class="paper-sheet paper-two"></span>
      <span class="paper-sheet paper-three"></span>
      <svg class="story-line" viewBox="0 0 720 420" role="presentation">
        <path d="M38 324 C158 310 144 212 266 214 S394 292 472 194 S570 88 686 110" />
        <path class="branch" d="M266 214 C338 166 385 130 444 88" />
        <circle cx="38" cy="324" r="7" />
        <circle cx="266" cy="214" r="7" />
        <circle cx="472" cy="194" r="7" />
        <circle cx="686" cy="110" r="7" />
      </svg>
    </div>

    <section class="startup-content" aria-live="polite">
      <div class="startup-brand"><span class="brand-glyph"></span><strong>ArcVellum</strong></div>
      <p class="startup-kicker">THE LIVING MANUSCRIPT</p>
      <h1>让一部长篇作品<br />从脉络中醒来。</h1>
      <p class="startup-status">
        {{ error || currentStep?.detail || "正在确认作品、任务与创作能力。" }}
      </p>

      <ol class="bootstrap-steps" v-if="snapshot">
        <li v-for="step in snapshot.steps" :key="step.id" :data-state="step.status">
          <span class="step-icon">
            <Check v-if="step.status === 'ready'" :size="13" />
            <LoaderCircle v-else-if="['loading', 'waiting'].includes(step.status)" :size="13" class="spin" />
            <AlertTriangle v-else-if="step.status === 'blocked'" :size="13" />
            <span v-else></span>
          </span>
          <span>{{ step.label }}</span>
        </li>
      </ol>

      <div class="startup-actions" v-if="error || snapshot?.phase === 'blocked'">
        <button class="primary-button" @click="$emit('retry')"><RefreshCw :size="16" />重试</button>
      </div>
      <div class="startup-actions" v-else-if="snapshot?.can_enter_workspace">
        <button class="primary-button" @click="$emit('continue')">进入创作台</button>
        <small v-if="snapshot.degraded">部分模型连接可稍后在设置中恢复</small>
      </div>
    </section>
  </div>
</template>
