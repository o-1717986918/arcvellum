<script setup lang="ts">
import { RouterLink } from "vue-router";
import { Activity, ArrowUpRight, BookOpenText, CircleCheck, CircleDashed, Gauge, Radio } from "lucide-vue-next";

defineProps<{
  title: string;
  premise: string;
  progress: number | null;
  formalChars: number;
  targetChars: number;
  currentTask: string;
  currentStage: string;
  agentStatus: string;
  readerUnits: number;
  nextAction: string;
}>();
</script>

<template>
  <aside class="pa-inspector">
    <section class="pa-inspect-focus">
      <header><span>当前作品</span><RouterLink to="/details" title="打开作品详情"><ArrowUpRight :size="14" /></RouterLink></header>
      <h2>{{ title }}</h2>
      <p>{{ premise || '作品方向会随着创作逐步变得清晰。' }}</p>
      <div class="pa-progress"><i :style="{ width: `${Math.max(0, Math.min(100, progress || 0))}%` }"></i></div>
      <div class="pa-progress-meta"><span>{{ progress == null ? '等待校准' : `${Math.round(progress)}%` }}</span><span>{{ formalChars.toLocaleString('zh-CN') }} / {{ targetChars.toLocaleString('zh-CN') }} 字</span></div>
    </section>

    <section>
      <header><span>创作现场</span><RouterLink to="/observatory">打开</RouterLink></header>
      <div class="pa-context-row"><Radio :size="15" /><span><strong>{{ agentStatus }}</strong><small>{{ currentStage || '等待下一项创作活动' }}</small></span></div>
      <div class="pa-context-row"><Activity :size="15" /><span><strong>{{ currentTask || '当前没有运行中的任务' }}</strong><small>创作任务的变化会持续更新在这里</small></span></div>
    </section>

    <section>
      <header><span>下一步</span><RouterLink to="/overview">在星仪中查看</RouterLink></header>
      <div class="pa-next-action"><CircleDashed :size="15" /><p>{{ nextAction || '等待作品状态形成下一项建议。' }}</p></div>
    </section>

    <section>
      <header><span>已完成正文</span><RouterLink to="/reader">阅读</RouterLink></header>
      <div class="pa-context-row"><BookOpenText :size="15" /><span><strong>{{ readerUnits }} 个正式单元</strong><small>新晋升正文会自动进入长卷</small></span></div>
      <div class="pa-context-row"><CircleCheck :size="15" /><span><strong>依据作品回答</strong><small>只查阅和问题有关的正文与资料</small></span></div>
    </section>

    <section class="pa-inspector-note">
      <Gauge :size="15" /><p>当前对话可以了解作品，暂时不会直接改动正文、设定或创作进度。</p>
    </section>
  </aside>
</template>
