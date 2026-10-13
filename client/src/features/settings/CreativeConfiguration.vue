<script setup lang="ts">
import { ref, watch } from "vue";
import type { CreatorPersonaState } from "@/features/creative-live/types";
import { creativeLiveClient } from "@/features/creative-live/services/creativeLiveClient";
const props = defineProps<{ projectRoot: string }>();
const revision = ref(0), v2 = ref(false), tone = ref(false), message = ref(""), busy = ref(false);
const persona = ref<CreatorPersonaState | null>(null), personaText = ref(""), reason = ref(""), personaMessage = ref("");
let generation = 0;
watch(() => props.projectRoot, async root => {
  const token = ++generation;
  v2.value = false; tone.value = false; revision.value = 0;
  persona.value = null; personaText.value = ""; reason.value = ""; personaMessage.value = "";
  if (!root) return;
  try { const [data, loadedPersona] = await Promise.all([creativeLiveClient.configuration(root), creativeLiveClient.persona(root)]); if (token !== generation) return;
    revision.value = data.revision; v2.value = data.effective.scene_creator_v2 === true; tone.value = data.effective.less_ai_tone_experiment === true;
    persona.value = loadedPersona; personaText.value = (loadedPersona.active || loadedPersona.last_generated)?.text || "";
    message.value = data.revision ? "作品配置版本 " + data.revision : "当前继承全局设置；保存后使用这里的作品开关。";
  } catch (cause) { if (token === generation) message.value = String(cause); }
}, { immediate: true });
async function save() {
  busy.value = true;
  try { const data = await creativeLiveClient.saveConfiguration(props.projectRoot, revision.value,
    { scene_creator_v2: v2.value, less_ai_tone_experiment: tone.value }); revision.value = data.revision; message.value = "已保存作品配置，后续新交易生效；版本 " + data.revision; }
  catch (cause) { message.value = String(cause); }
  finally { busy.value = false; }
}
async function savePersona() {
  const root = props.projectRoot, token = generation;
  busy.value = true;
  try { const data = await creativeLiveClient.savePersona(root, persona.value?.active_version || 0, personaText.value, reason.value);
    if (token === generation) { persona.value = data; personaMessage.value = "人格与作者方向已保存，新版本 " + data.active_version + " 用于后续新交易。"; } }
  catch (cause) { if (token === generation) personaMessage.value = String(cause); }
  finally { busy.value = false; }
}
</script>
<template><section class="creative-config" aria-label="作品创作链设置"><h3>作品创作链</h3><label><input v-model="v2" type="checkbox" />v2 主创与自然交付</label><label><input v-model="tone" type="checkbox" />实验：去 AI 味编辑</label><button :disabled="busy || !projectRoot" @click="save">保存作品开关</button><p role="status">{{ message }}</p><p>新交易冻结人格、文风与开关；实际状态在创作过程的加载记录中查看。</p><details><summary>主创人格 · {{ persona?.status === 'ready' ? '就绪' : persona?.status === 'needs-repair' ? '待修订' : '待初始化' }} · 版本 {{ persona?.active_version || 0 }}</summary><p v-if="persona?.literary_review?.decision === 'revise'">{{ persona.literary_review.reason }}</p><label>人格正文<textarea v-model="personaText" rows="12" maxlength="4000" /></label><label>修改理由<input v-model="reason" maxlength="1000" /></label><p>保存这份人格会记录为你的作者方向，既有交易保留原人格快照。</p><button :disabled="busy || personaText.trim().length < 20 || reason.trim().length < 6" @click="savePersona">保存人格与作者方向</button><p role="status">{{ personaMessage }}</p><details v-if="persona?.history.length"><summary>历史版本与来源</summary><details v-for="version in persona.history" :key="version.version"><summary>版本 {{ version.version }} · {{ version.reason }}</summary><small>{{ version.source_digest }}</small><pre>{{ version.text }}</pre></details></details></details></section></template>
<style scoped>.creative-config { padding: 1rem; border: 1px solid var(--border, #ccc); border-radius: 8px; margin: 1rem 0; } label { display: block; margin: .5rem 0; } textarea, input:not([type=checkbox]) { width: 100%; max-width: 100%; box-sizing: border-box; } small { display: block; overflow-wrap: anywhere; } pre { white-space: pre-wrap; overflow-wrap: anywhere; }</style>
