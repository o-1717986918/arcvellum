<script setup lang="ts">
import { onMounted, ref } from "vue";
import { WandSparkles } from "lucide-vue-next";
import { settingsClient, type ToneExperimentPreferences } from "./services/settingsClient";

const preferences = ref<ToneExperimentPreferences | null>(null);
const enabled = ref(false);
const busy = ref(false);
const feedback = ref("");

onMounted(async () => {
  try {
    const response = await settingsClient.toneExperimentPreferences();
    preferences.value = response.preferences;
    enabled.value = response.preferences.enabled;
  } catch (cause) { feedback.value = cause instanceof Error ? cause.message : "实验设置加载失败。"; }
});

async function save(): Promise<void> {
  busy.value = true;
  try {
    const response = await settingsClient.saveToneExperimentPreferences(enabled.value);
    preferences.value = response.preferences;
    enabled.value = response.preferences.enabled;
    feedback.value = "已保存，新场景开始时生效。";
  } catch (cause) {
    enabled.value = preferences.value?.enabled ?? false;
    feedback.value = cause instanceof Error ? cause.message : "保存失败，已恢复原设置。";
  } finally { busy.value = false; }
}
</script>

<template>
  <section class="settings-section tone-experiment">
    <header><span class="section-icon iris"><WandSparkles :size="18" /></span><div><h2>自动去 AI 味 · 实验</h2><p>主创在成稿与返修后回看表达，依据十一项规则提出局部修改，再进入审读。</p></div></header>
    <label class="tone-switch">
      <span><strong>自动挂载编辑规则</strong><small>每场保留原稿、改稿与修改理由。开关在新场景开始时生效。</small></span>
      <select v-model="enabled" aria-label="自动去 AI 味实验" :disabled="!preferences || busy" @change="save"><option :value="true">开启</option><option :value="false">关闭</option></select>
    </label>
    <p v-if="feedback" class="inline-feedback" role="status">{{ feedback }}</p>
    <p class="tone-source">规则来源：<a href="https://github.com/larashero3-dotcom/lieflat-less-ai-tone" target="_blank" rel="noreferrer">lieflat-less-ai-tone</a> · 正向文学编辑适配版。文风取自作品当前挂载。</p>
    <details v-if="preferences"><summary>规则版本与改稿记录</summary><p>源版本 {{ preferences.source_commit }}</p><p>可在“提示词”工作台搜索 {{ preferences.prompt_layer_id }}，查看或修改模板。</p><p>记录目录：{{ preferences.audit_directory }} / 场景交易 / less-ai-tone</p></details>
  </section>
</template>

<style scoped>
.tone-switch { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.tone-switch span { display: grid; gap: 6px; }
.tone-switch small, .tone-source, details { color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.tone-switch select { min-width: 100px; }
.tone-source { margin-top: 18px; }
.tone-experiment p { overflow-wrap: anywhere; }
details { margin-top: 12px; }
summary { cursor: pointer; }
@media (max-width: 600px) { .tone-switch { align-items: stretch; flex-direction: column; } }
</style>
