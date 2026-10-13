<script setup lang="ts">
import { computed, ref, shallowRef, watch } from "vue";
import { creativeLiveClient } from "../services/creativeLiveClient";
import type { SceneMaterialInspection } from "../types";

const props = defineProps<{ projectRoot: string; transactionId: string; refreshKey?: number }>();
const inspection = shallowRef<SceneMaterialInspection | null>(null);
const loading = ref(false);
const error = ref("");
const kind = ref("");
const search = ref("");
let generation = 0;
const names: Record<string, string> = {
  actor: "角色扮演", environment: "环境创作", "character-description": "人物描写",
  "event-narration": "事件与世界叙述", "scene-description": "场面与群像",
};
const decisions: Record<string, string> = { use: "采用", adapt: "改写", discard: "舍下", defer: "待后续使用" };
const basis: Record<string, string> = { confirmed: "已确认资料", attributed: "人物转述", proposed: "创作提案" };
const intentLabels: Record<string, string> = { reader_experience: "阅读经验", reader_knows: "交给读者的信息", reader_misreads: "预期误读", withheld: "暂留信息" };
const transportModes: Record<string,string> = { local:'本地解析', reused:'本地复用', recovered:'保存结果恢复',
  model:'模型整理', repaired:'局部修复', failed:'整理待完成' };
const transportKinds: Record<string,string> = { creator:'主创交付', material:'取材回应', card:'角色卡',
  'style-choice':'文风选择', 'material-plan':'取材计划', tone:'编辑建议', review:'审读记录',
  'planning-future-outline':'未来纲要', 'planning-future-chapter':'章节规划' };
const filtered = computed(() => (inspection.value?.materials || []).filter((item) => {
  const haystack = [item.target, item.purpose, item.text, item.spoken, item.first_person_action, item.private_impulse].join("\n");
  return (!kind.value || kind.value === item.kind) && (!search.value.trim() || haystack.includes(search.value.trim()));
}));
const groups = computed(() => {
  const emptyCalls = (inspection.value?.calls || []).filter((call) =>
    !(inspection.value?.materials || []).some((material) => material.call_id === call.call_id)
    && (!kind.value || call.request.kind === kind.value)
    && (!search.value.trim() || [call.request.purpose, call.request.target, call.raw_response].join("\n").includes(search.value.trim())),
  );
  const ids = [...new Set([...filtered.value.map((item) => item.call_id), ...emptyCalls.map((call) => call.call_id)])];
  return ids.map((id) => ({ id, call: inspection.value?.calls.find((call) => call.call_id === id),
    materials: filtered.value.filter((item) => item.call_id === id) }));
});

watch(() => [props.projectRoot, props.transactionId, props.refreshKey], () => { void load(); }, { immediate: true });
watch(() => props.transactionId, () => { kind.value = ""; search.value = ""; });
async function load(): Promise<void> {
  const current = ++generation;
  if (!props.projectRoot || !props.transactionId) { inspection.value = null; return; }
  if (inspection.value?.transaction_id !== props.transactionId) inspection.value = null;
  loading.value = true;
  error.value = "";
  try {
    const response = await creativeLiveClient.materials(props.projectRoot, props.transactionId);
    if (current === generation) inspection.value = response.inspection;
  } catch (cause) {
    if (current === generation) { inspection.value = null; error.value = cause instanceof Error ? cause.message : "素材暂时无法读取"; }
  } finally { if (current === generation) loading.value = false; }
}
</script>

<template>
  <section class="material-inspector" aria-label="全部取材素材">
    <header class="material-inspector-heading">
      <div><h3>取材原稿</h3><p>{{ inspection?.calls.length || 0 }} 次委托 · {{ inspection?.candidate_count || 0 }} 条素材</p></div>
      <button type="button" :disabled="loading" @click="load">{{ loading ? '读取中…' : '刷新素材' }}</button>
    </header>
    <div class="material-inspector-filters">
      <label>创作者<select v-model="kind" aria-label="筛选取材类别"><option value="">全部五类</option><option v-for="(name, value) in names" :key="value" :value="value">{{ name }}</option></select></label>
      <label>查找<input v-model="search" aria-label="查找素材" placeholder="人物、委托或原文" /></label>
    </div>
    <p v-if="error" class="material-inspector-error" role="alert">{{ error }} <button type="button" @click="load">重试</button></p>
    <p v-for="warning in inspection?.warnings || []" :key="warning" class="material-inspector-error">{{ warning }}</p>
    <details v-if="inspection?.intent" class="material-inspector-intent"><summary>主创的创作意图</summary><p v-for="(label, key) in intentLabels" :key="key" v-show="inspection.intent[key]"><strong>{{ label }}</strong><br />{{ inspection.intent[key] }}</p></details>
    <details v-if="inspection?.transport" class="material-transport">
      <summary>整理过程 · {{ inspection.transport.local_records }} 份本地解析 · {{ inspection.transport.reuse_count }} 次复用 · {{ inspection.transport.model_calls }} 次整理调用</summary>
      <p>原文完整保留。以下计数为整理调用；供应商请求、缓存与 token 用量沿运行记录呈现。</p>
      <div v-for="record in inspection.transport.records" :key="record.record_id" class="material-note">
        <strong>{{ transportKinds[record.operation] || record.operation }} · {{ transportModes[record.mode] || record.mode }}</strong>
        <span>{{ record.model_calls }} 次整理调用 · {{ record.reuse_count }} 次复用{{ record.requested_thinking === 'off' ? ' · 请求非思考' : '' }}</span>
        <p v-if="record.error" class="material-inspector-error">{{ record.error }}</p>
      </div>
    </details>
    <article v-for="group in groups" :key="group.id || 'unlinked'" class="material-call">
      <header><span>{{ group.call ? `委托 ${group.call.sequence}` : '已保存素材' }}</span><h4>{{ names[group.call?.request.kind || group.materials[0]?.kind || ''] || '取材' }} · {{ group.call?.request.target || group.materials[0]?.target || '本段作品' }}</h4></header>
      <div v-if="group.call" class="material-request">
        <p v-if="group.call.request.purpose"><strong>文学用途</strong>{{ group.call.request.purpose }}</p>
        <p v-if="group.call.request.scene_moment"><strong>位置与时间</strong>{{ group.call.request.scene_moment }}</p>
        <p v-if="group.call.request.author_prompt"><strong>主创委托</strong>{{ group.call.request.author_prompt }}</p>
        <details v-if="group.call.request.cue"><summary>委托语境</summary><p>{{ group.call.request.cue }}</p></details>
        <details v-if="group.call.attachments.length"><summary>本次挂载 · {{ group.call.attachments.length }} 项</summary><pre v-for="(entry, index) in group.call.attachments" :key="index">{{ JSON.stringify(entry, null, 2) }}</pre></details>
      </div>
      <section v-for="(material, index) in group.materials" :key="`${material.candidate_id}-${index}`" class="material-candidate">
        <div class="material-candidate-label"><span>{{ material.candidate_id }}</span><span v-if="material.basis">{{ basis[material.basis] || material.basis }}</span><span :data-decision="material.decision">{{ decisions[material.decision] || '尚无取舍记录' }}</span></div>
        <p v-if="material.text" class="material-original">{{ material.text }}</p>
        <p v-if="material.spoken" class="material-original"><small>角色台词</small>{{ material.spoken }}</p>
        <p v-if="material.first_person_action" class="material-original"><small>角色动作</small>{{ material.first_person_action }}</p>
        <details v-if="material.private_impulse" class="material-private"><summary>角色内在冲动 · 演绎素材</summary><p class="material-original">{{ material.private_impulse }}</p></details>
        <p v-if="material.focus" class="material-note"><strong>创作者札记</strong>{{ material.focus }}</p>
        <p v-if="material.source_note" class="material-note"><strong>资料来处</strong>{{ material.source_note }}</p>
        <p v-if="material.decision_reason" class="material-note"><strong>主创取舍</strong>{{ material.decision_reason }}</p>
        <details v-if="material.usage_evidence" class="material-note"><summary>素材用途与正文落点</summary>
          <p v-if="material.usage_evidence.source_excerpt"><strong>选中来源片段{{ material.usage_evidence.source_excerpt_verified ? ' · 已核对' : ' · 待核对' }}</strong>{{ material.usage_evidence.source_excerpt }}</p>
          <p v-if="material.usage_evidence.prose_excerpt"><strong>正文原句{{ material.usage_evidence.prose_excerpt_verified ? ' · 已核对' : ' · 待核对' }}</strong>{{ material.usage_evidence.prose_excerpt }}</p>
          <p v-if="material.usage_evidence.prose_location">{{ material.usage_evidence.prose_location }}</p>
          <p v-if="material.usage_evidence.indirect_use"><strong>间接用途</strong>{{ material.usage_evidence.indirect_use }}</p>
          <p v-if="!material.usage_evidence.source_excerpt && !material.usage_evidence.indirect_use">尚未登记具体使用证据。</p>
          <p>取舍标签和字面复用均不能代表真实文学利用率。</p>
        </details>
      </section>
      <details v-if="group.call?.raw_response" class="material-raw"><summary>本次完整原始交付</summary><pre>{{ group.call.raw_response }}</pre></details>
      <p v-if="!group.materials.length" class="material-note">本次尚无已整理候选；已收到的原始交付可在上方展开。</p>
    </article>
    <p v-if="!loading && !error && !groups.length" class="material-inspector-empty">{{ inspection?.candidate_count ? '没有符合筛选条件的素材。' : '尚未保存取材结果；委托返回后可在这里阅读完整素材。' }}</p>
  </section>
</template>

<style scoped>
.material-inspector { min-width: 0; padding: 20px; color: #263831; font-family: var(--font-body); }
.material-inspector-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.material-inspector-heading h3 { margin: 0; font-family: var(--font-display); font-size: 22px; font-weight: 500; }
.material-inspector-heading p { margin: 6px 0; color: #60766a; font-size: 12px; }
.material-inspector button, .material-inspector select, .material-inspector input { padding: 8px 10px; border: 1px solid #bdd7c7; border-radius: 7px; background: #fff; color: #263831; font: inherit; }
.material-inspector button { cursor: pointer; font-size: 12px; }
.material-inspector :is(button, select, input, summary):focus-visible { outline: 2px solid #2f705d; outline-offset: 3px; }
.material-inspector-filters { display: flex; gap: 12px; margin: 14px 0; }
.material-inspector-filters label { display: grid; flex: 1; min-width: 0; gap: 6px; font-size: 12px; color: #60766a; }
.material-inspector :is(pre, p) { white-space: pre-wrap; overflow-wrap: anywhere; }
.material-inspector-filters :is(select, input) { width: 100%; min-width: 0; box-sizing: border-box; }
.material-call { margin: 24px 0; border-top: 2px solid #8eaf9b; }
.material-call > header { margin: 14px 0; }
.material-call > header > span { color: #60766a; font-size: 11px; }
.material-call h4 { margin: 5px 0; font-size: 15px; }
.material-request, .material-note { font-size: 12px; line-height: 1.8; color: #60766a; }
.material-request strong, .material-note strong { display: block; color: #3a5c4c; }
.material-candidate { padding: 16px 0; border-top: 1px solid #dbe5dc; }
.material-candidate-label { display: flex; flex-wrap: wrap; gap: 8px; color: #60766a; font-size: 11px; }
.material-candidate-label [data-decision='use'], .material-candidate-label [data-decision='adapt'] { color: #2f705d; font-weight: 600; }
.material-original { margin: 14px 0; font-size: 15px; line-height: 1.95; color: #263831; }
.material-original small { display: block; color: #60766a; font-size: 11px; }
.material-inspector summary { cursor: pointer; font-size: 12px; color: #3a5c4c; }
.material-inspector pre { font-size: 12px; line-height: 1.7; }
.material-private { border-left: 2px solid #bdd7c7; padding: 6px 12px; }
.material-inspector-intent { padding: 12px; background: #eef4ef; font-size: 13px; line-height: 1.8; }
.material-inspector-error { color: #a44434; font-size: 12px; }
.material-inspector-empty { color: #60766a; font-size: 13px; line-height: 1.8; }
@media (max-width: 540px) { .material-inspector { padding: 14px; } .material-inspector-filters { flex-direction: column; } }
</style>
