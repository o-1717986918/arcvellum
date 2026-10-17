<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { stylometryClient } from "../services/stylometryClient";
import type { StylePresetCatalog } from "../stylePresetTypes";
const props = defineProps<{ projectRoot: string; versions: { version_id: string; title: string }[]; refreshKey?: string; canRecalculate?: boolean }>();
const emit = defineEmits<{ select: [id: string, version: string]; refresh: [] }>();
const catalog = ref<StylePresetCatalog | null>(null), selected = ref("");
const busy = ref(false), error = ref(""), notice = ref("");
const baseline = ref("");
const dirty = computed(() => !!catalog.value && baseline.value !== JSON.stringify(catalog.value));
const current = computed(() => catalog.value?.presets.find(row => row.preset_id === selected.value));
const references = computed(() => catalog.value?.reference_catalog?.references || []);
let generation = 0;
async function load() {
  const token = ++generation;
  if (!props.projectRoot) { catalog.value = null; return; }
  busy.value = true; error.value = "";
  try {
    const result = await stylometryClient.presets(props.projectRoot);
    if (token !== generation) return;
    catalog.value = result;
    baseline.value = JSON.stringify(result);
    if (!result.presets.some(row => row.preset_id === selected.value)) selected.value = result.default_preset_id;
  } catch (cause) { if (token === generation) error.value = String(cause); }
  finally { if (token === generation) busy.value = false; }
}
watch(() => props.projectRoot, () => { catalog.value = null; baseline.value = ""; void load(); }, { immediate: true });
watch(() => props.refreshKey, () => {
  if (!dirty.value) void load();
  else notice.value = "参数版本已更新；此处保留了尚未保存的预设修改。保存冲突时刷新并重新选择版本。";
});
function select(id: string) {
  selected.value = id;
  const row = catalog.value?.presets.find(item => item.preset_id === id);
  if (row) emit("select", id, row.stylometry_version_id);
}
async function save() {
  if (!catalog.value) return;
  busy.value = true; error.value = "";
  try { await stylometryClient.savePresets(props.projectRoot, catalog.value); await load(); notice.value = "预设已保存，后续新交易生效。"; }
  catch (cause) { error.value = String(cause); }
  finally { busy.value = false; }
}
async function initialize() {
  busy.value = true; error.value = "";
  try { catalog.value = await stylometryClient.initializePresets(props.projectRoot); selected.value = catalog.value.default_preset_id; baseline.value = JSON.stringify(catalog.value); emit("refresh"); notice.value = "已从完整参照重新计算四类画像，可选择预设后拖动参数。"; }
  catch (cause) { error.value = String(cause); }
  finally { busy.value = false; }
}
async function recalculate() {
  if (!catalog.value || !current.value) return;
  const root = props.projectRoot, id = selected.value;
  busy.value = true; error.value = "";
  try {
    if (dirty.value) { await stylometryClient.savePresets(root, catalog.value); if (root !== props.projectRoot) return; await load(); }
    if (root !== props.projectRoot || !catalog.value) return;
    const result = await stylometryClient.recalculatePreset(root, id, catalog.value.revision);
    if (root !== props.projectRoot) return;
    catalog.value = result; baseline.value = JSON.stringify(result);
    const row = current.value;
    if (row) emit("select", row.preset_id, row.stylometry_version_id);
    emit("refresh"); notice.value = "已按选定参照生成新的真实画像和参数版本；已有交易沿用原快照。";
  } catch (cause) { if (root === props.projectRoot) error.value = String(cause); }
  finally { if (root === props.projectRoot) busy.value = false; }
}

function toggleReference(id: string, checked: boolean) {
  if (!current.value) return;
  current.value.reference_ids = checked ? [...new Set([...current.value.reference_ids, id])] : current.value.reference_ids.filter(item => item !== id);
}
function addPreset() {
  if (!catalog.value) return;
  const id = "preset-" + Date.now();
  catalog.value.presets.push({ preset_id: id, title: "新的文风组合", literary_intent: "", narrative_modes: [],
    reference_ids: [], stylometry_version_id: props.versions[0]?.version_id || "", active: true, combine: "append", usage: "guide" });
  selected.value = id;
}
</script>
<template>
  <details class="stylo-presets" aria-label="叙述方式文风预设">
    <summary>叙述方式与文风预设 · 版本 {{ catalog?.revision || 0 }}</summary>
    <p>主创在新交易开场阅读完整目录，根据章节任务选择预设和参照。选择后冻结实际文风。</p>
    <p v-if="error" role="alert" class="stylo-error">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
    <button v-if="!catalog?.revision" :disabled="busy || !projectRoot" @click="initialize">计算四类初始文风预设</button>
    <fieldset v-if="catalog?.presets.length" :disabled="busy">
      <label><input v-model="catalog.enabled" type="checkbox" />启用主创自主选预设</label>
      <label>默认预设<select v-model="catalog.default_preset_id"><option v-for="row in catalog.presets" :key="row.preset_id" :value="row.preset_id">{{ row.title }}</option></select></label>
      <nav class="stylo-actions"><button v-for="row in catalog.presets" :key="row.preset_id" :aria-pressed="selected === row.preset_id" @click="select(row.preset_id)">{{ row.title }}</button></nav>
      <button :disabled="busy || !versions.length || catalog.presets.length >= 32" @click="addPreset">新增文风组合</button>
      <template v-if="current">
        <label>名称<input v-model="current.title" maxlength="80" /></label>
        <label>文学用途<textarea v-model="current.literary_intent" rows="3" maxlength="8000" /></label>
        <label>计量版本<select v-model="current.stylometry_version_id"><option v-for="row in versions" :key="row.version_id" :value="row.version_id">{{ row.title }} · {{ row.version_id.slice(0, 8) }}</option></select></label>
        <div class="stylo-actions"><label>组合<select v-model="current.combine"><option value="append">补充通用文风</option><option value="replace">替换通用文风</option></select></label><label>用途<select v-model="current.usage"><option value="guide">参与创作</option><option value="observe">仅观测</option></select></label><label><input v-model="current.active" type="checkbox" />可供主创选择</label></div>
        <button v-if="canRecalculate" :disabled="busy || current.reference_ids.length < 2" @click="recalculate">按所选参照重新统计</button>
        <p>最后一条参照用于留出观察，其余用于统计；重新计算生成新的计量版本。</p>
        <p>点选此预设后，下方参数面板加载对应画像；拖动并应用参数会更新此预设的计量版本。</p>
        <details><summary>参照全文与来源 · {{ current.reference_ids.length }} 项建议参照</summary>
          <details v-for="row in references" :key="row.unit_id"><summary>{{ row.unit_id }} · {{ row.source_title }} · {{ row.source_kind === 'verified_literary_original' ? '核验原文' : '用户样段' }}</summary>
            <label><input type="checkbox" :checked="current.reference_ids.includes(row.unit_id)" @change="toggleReference(row.unit_id, ($event.target as HTMLInputElement).checked)" />作为本预设的候选参照</label>
            <p>{{ row.technique_axes.join('、') }}</p><a v-if="row.source_url" :href="row.source_url" target="_blank" rel="noopener">原始出处</a><pre>{{ row.text }}</pre><small>{{ row.source_digest }}</small>
          </details>
        </details>
      </template>
      <button :disabled="busy" @click="save">保存预设配置</button><button :disabled="busy" @click="load">刷新</button>
    </fieldset>
  </details>
</template>
<style scoped>
.stylo-presets { margin: 1rem 0; padding: 1rem; border: 1px solid var(--border, #ccc); border-radius: 8px; min-width: 0; }
.stylo-presets fieldset { padding: 0; border: 0; min-width: 0; }
.stylo-presets label { display: block; margin: .6rem 0; } .stylo-presets textarea, .stylo-presets select, .stylo-presets input:not([type=checkbox]) { width: 100%; max-width: 100%; }
.stylo-presets pre { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 26rem; overflow: auto; } .stylo-presets small { overflow-wrap: anywhere; }
</style>
