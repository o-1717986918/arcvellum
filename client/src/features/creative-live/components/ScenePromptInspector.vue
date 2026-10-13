<script setup lang="ts">
import { ref, watch } from "vue";
import { creativeLiveClient } from "../services/creativeLiveClient";
import type { ScenePromptInspection } from "../scenePromptTypes";
const props = defineProps<{ projectRoot: string; transactionId: string; refreshKey?: number }>();
const inspection = ref<ScenePromptInspection | null>(null), error = ref(""), busy = ref(false);
let generation = 0;
async function load() {
  const token = ++generation;
  if (!props.projectRoot || !props.transactionId) { inspection.value = null; return; }
  busy.value = true; error.value = "";
  try { const result = await creativeLiveClient.prompts(props.projectRoot, props.transactionId); if (token === generation) inspection.value = result; }
  catch (cause) { if (token === generation) { inspection.value = null; error.value = String(cause); } }
  finally { if (token === generation) busy.value = false; }
}
watch(() => [props.projectRoot, props.transactionId, props.refreshKey], () => { void load(); }, { immediate: true });
function inputParts(input: { prompt: string; system_prompt: string }) {
  try { const value = JSON.parse(input.prompt); if (value.system_prompt && value.prompt) return { system: value.system_prompt, task: value.prompt }; } catch { /* Plain creative inputs remain plain. */ }
  return { system: input.system_prompt, task: input.prompt };
}
</script>
<template>
  <section class="scene-prompt-inspector" aria-label="实际交易提示词与文风">
    <header><h3>实际加载 · {{ transactionId }}</h3><button :disabled="busy" @click="load">刷新加载记录</button></header>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="inspection">
      <p>{{ inspection.prompt_assembly?.response_mode === 'natural-v1' ? 'v2 自然创作' : '原交易链路' }} · 计量 {{ inspection.style_bundle?.measurement.enabled ? inspection.style_bundle.measurement.usage : '查看原快照' }} · 去 AI 味 {{ inspection.tone_mount?.enabled ? '已挂载' : '未挂载' }}</p>
      <details v-if="inspection.style_bundle" open><summary>冻结文风 · {{ inspection.style_bundle.selection.preset_id }} · 预设版本 {{ inspection.style_bundle.preset_revision }}</summary><p>{{ inspection.style_bundle.selection.reason }}</p><pre>{{ inspection.style_bundle.style.assembled.content }}</pre><small>{{ inspection.style_bundle.digest }}</small></details>
      <details v-if="inspection.creator_briefing"><summary>主创人格与必达信息</summary><pre>{{ JSON.stringify(inspection.creator_briefing, null, 2) }}</pre></details>
      <p v-if="!inspection.submitted_inputs.length">此历史交易未保存逐次发起输入；上方提供其冻结快照。</p>
      <details v-for="(input, index) in inspection.submitted_inputs" :key="input.digest"><summary>调用 {{ index + 1 }} · {{ input.role }} · {{ input.stage }}</summary><h4>系统提示词</h4><pre>{{ inputParts(input).system }}</pre><h4>当轮任务</h4><pre>{{ inputParts(input).task }}</pre><details v-if="input.history.length"><summary>独立上下文</summary><pre>{{ JSON.stringify(input.history, null, 2) }}</pre></details></details>
      <details v-if="inspection.prompt_assembly"><summary>提示词版本与来源</summary><pre>{{ JSON.stringify(inspection.prompt_assembly, null, 2) }}</pre></details>
      <details v-for="report in inspection.edits" :key="report.input_digest"><summary>原稿／编辑稿 · {{ report.phase }} · {{ report.accepted.length }} 处修改</summary><p>{{ report.summary }}</p><div class="scene-prose-comparison"><div><h4>原稿</h4><pre>{{ report.original }}</pre></div><div><h4>编辑稿</h4><pre>{{ report.cleaned }}</pre></div></div><details><summary>逐处差异与理由</summary><pre>{{ JSON.stringify(report.accepted, null, 2) }}</pre></details></details>
      <details v-for="report in inspection.measurements" :key="report.text_sha256"><summary>真实计量 · {{ report.stages?.join(" / ") || "主创稿件" }} · {{ report.text_sha256.slice(0, 12) }} · {{ report.error ? '测量失败' : '已测量' }}</summary><div class="scene-metric-table" v-if="report.result?.targets?.length"><table><thead><tr><th>指标</th><th>目标区间</th><th>实际分布</th><th>区间距离</th></tr></thead><tbody><tr v-for="target in report.result.targets" :key="target.id"><td>{{ target.label }}</td><td>{{ target.min }}–{{ target.max }} {{ target.unit }}</td><td>{{ target.observed ?? '缺测' }}</td><td>{{ target.distance ?? '缺测' }}</td></tr></tbody></table></div><details><summary>原始统计与样本诊断</summary><pre>{{ JSON.stringify(report, null, 2) }}</pre></details></details>
    </template>
  </section>
</template>
<style scoped>
.scene-prompt-inspector { margin: 1rem; padding: 1rem; border: 1px solid var(--border, #ccc); border-radius: 8px; min-width: 0; }
.scene-prompt-inspector header { display: flex; gap: 1rem; flex-wrap: wrap; } .scene-prompt-inspector h3, .scene-prompt-inspector small { overflow-wrap: anywhere; }
.scene-prompt-inspector details { margin: .75rem 0; } .scene-prompt-inspector pre { white-space: pre-wrap; overflow-wrap: anywhere; overflow: auto; max-height: 32rem; }
.scene-metric-table { overflow-x: auto; } .scene-metric-table th, .scene-metric-table td { padding: .5rem; text-align: left; }
.scene-prose-comparison { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 1rem; } @media(max-width: 650px) { .scene-prose-comparison { grid-template-columns: minmax(0, 1fr); } }
</style>
