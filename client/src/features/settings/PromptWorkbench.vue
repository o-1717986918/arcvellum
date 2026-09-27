<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { Check, FileJson, Layers3 } from "lucide-vue-next";
import { settingsClient, type PromptCatalog, type PromptHistory, type PromptPreview } from "./services/settingsClient";

const props = defineProps<{ projectRoot: string }>();
const catalog = ref<PromptCatalog | null>(null);
const history = ref<PromptHistory | null>(null);
const preview = ref<PromptPreview | null>(null);
const layerId = ref("scene.creator.identity");
const scope = ref<"global" | "project">("global");
const draft = ref("");
const busy = ref(false);
const feedback = ref("");
const query = ref("");
const responsibility = ref("all");
const selectedLayer = computed(() => catalog.value?.layers.find((layer) => layer.layer_id === layerId.value));
const visibleLayers = computed(() => (catalog.value?.layers || []).filter((layer) => {
  const matchesGroup = responsibility.value === "all" || layer.responsibility === responsibility.value;
  const needle = query.value.trim().toLocaleLowerCase();
  return matchesGroup && (!needle || `${layer.layer_id} ${layer.purpose} ${layer.owner}`.toLocaleLowerCase().includes(needle));
}));
const hasDiff = computed(() => !!selectedLayer.value && selectedLayer.value.effective_text !== selectedLayer.value.default_text);
const canReset = computed(() => selectedLayer.value?.editable && (
  scope.value === "global" ? selectedLayer.value.source === "global"
    : selectedLayer.value.source === "project" || (selectedLayer.value.source === "project-asset" && hasDiff.value)
));
const scopedRoot = computed(() => scope.value === "project" ? props.projectRoot : "");

onMounted(() => { void loadCatalog(); });
watch(layerId, () => { void loadSelection(); });
watch(scope, () => { void loadCatalog(); });
watch(() => props.projectRoot, () => { void loadCatalog(); });

async function loadCatalog(): Promise<void> {
  busy.value = true;
  try {
    catalog.value = await settingsClient.promptCatalog(scopedRoot.value);
    await loadSelection();
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "提示词目录无法读取。";
  } finally { busy.value = false; }
}

async function loadSelection(): Promise<void> {
  const layer = selectedLayer.value;
  draft.value = layer?.effective_text || "";
  preview.value = null;
  if (!layer?.editable || (scope.value === "project" && !scopedRoot.value)) {
    history.value = null;
    return;
  }
  try {
    history.value = await settingsClient.promptHistory(layerId.value, scope.value, scopedRoot.value);
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "版本历史无法读取。";
  }
}

async function saveLayer(): Promise<void> {
  if (!selectedLayer.value?.editable || !draft.value.trim()) return;
  busy.value = true;
  try {
    await settingsClient.savePromptLayer(layerId.value, {
      scope: scope.value, project_root: scopedRoot.value, text: draft.value,
      expected_digest: selectedLayer.value.digest,
    });
    await loadCatalog();
    feedback.value = "提示词新版本已保存；已开始的任务继续使用其已生成的提示词。";
  } catch (cause) { feedback.value = cause instanceof Error ? cause.message : "提示词没有保存。"; }
  finally { busy.value = false; }
}

async function activateVersion(version: number): Promise<void> {
  busy.value = true;
  try {
    await settingsClient.activatePromptVersion(layerId.value, {
      scope: scope.value, project_root: scopedRoot.value, version,
      expected_digest: selectedLayer.value?.digest,
    });
    await loadCatalog();
    feedback.value = `已激活第 ${version} 版。`;
  } catch (cause) { feedback.value = cause instanceof Error ? cause.message : "版本回退失败。"; }
  finally { busy.value = false; }
}

async function resetLayer(): Promise<void> {
  if (!canReset.value || !selectedLayer.value) return;
  busy.value = true;
  try {
    await settingsClient.resetPromptLayer(layerId.value, {
      scope: scope.value, project_root: scopedRoot.value,
      expected_digest: selectedLayer.value.digest,
    });
    await loadCatalog();
    feedback.value = "已撤销此范围的覆盖，历史版本仍可重新激活。";
  } catch (cause) { feedback.value = cause instanceof Error ? cause.message : "恢复默认失败。"; }
  finally { busy.value = false; }
}

async function previewAssembly(): Promise<void> {
  busy.value = true;
  try {
    preview.value = await settingsClient.previewPromptLayers([layerId.value], scopedRoot.value);
  } catch (cause) { feedback.value = cause instanceof Error ? cause.message : "组装预览失败。"; }
  finally { busy.value = false; }
}
</script>

<template>
  <section class="settings-section prompt-workbench">
    <header><span class="section-icon iris"><FileJson :size="18" /></span><div><h2>提示词工作台</h2><p>按职责查看提示词，调整文学指引，并保留每个版本。协议与事实边界固定。</p></div></header>
    <p v-if="feedback" class="inline-feedback">{{ feedback }}</p>
    <div class="prompt-workbench-controls">
      <label class="field"><span>搜索用途或 ID</span><input v-model="query" type="search" aria-label="搜索提示词" placeholder="例如：主创、审读、formal.asset" /></label>
      <label class="field"><span>职责层</span><select v-model="responsibility" aria-label="提示词职责筛选">
        <option value="all">全部职责</option><option value="identity">身份初始化</option><option value="stage">阶段任务</option>
        <option value="protocol">固定协议</option><option value="formal-asset">正式任务正文</option>
        <option value="dynamic">动态资料</option><option value="repair">修复与旧路径</option>
      </select></label>
      <label class="field"><span>职责层与用途</span><select v-model="layerId" aria-label="提示词层">
        <option v-for="layer in visibleLayers" :key="layer.layer_id" :value="layer.layer_id">{{ layer.responsibility }} · {{ layer.purpose }} · {{ layer.layer_id }}</option>
      </select></label>
      <label class="field"><span>编辑范围</span><select v-model="scope" aria-label="提示词范围">
        <option value="global">所有作品</option><option value="project" :disabled="!projectRoot">当前作品</option>
      </select></label>
    </div>
    <p v-if="selectedLayer" class="prompt-layer-meta">{{ selectedLayer.layer_id }} · 当前采用 {{ selectedLayer.source }} 第 {{ selectedLayer.version }} 版 · {{ selectedLayer.owner }} · {{ selectedLayer.usage_status === 'legacy' ? '旧路径' : selectedLayer.usage_status === 'legacy-project' ? '旧作品模板' : selectedLayer.usage_status === 'dynamic' ? '运行时资料' : selectedLayer.usage_status === 'formal-route' ? '正式任务' : '运行中' }}</p>
    <p v-if="selectedLayer" class="prompt-layer-meta">{{ hasDiff ? '有效版本与随包默认不同' : '当前使用随包默认文本' }} · {{ selectedLayer.purpose }}</p>
    <div v-if="selectedLayer" class="prompt-workbench-columns">
      <label class="field"><span>随包默认</span><textarea :value="selectedLayer.default_text" readonly rows="12" /></label>
      <label class="field"><span>{{ selectedLayer.editable ? '可编辑提示词正文' : '固定协议或动态资料说明' }}</span>
        <textarea v-model="draft" :readonly="!selectedLayer.editable" rows="12" :maxlength="12000" />
      </label>
    </div>
    <div class="button-row">
      <button class="primary-button" :disabled="busy || !selectedLayer?.editable || !draft.trim() || (scope === 'project' && !projectRoot)" @click="saveLayer"><Check :size="16" />保存新版本</button>
      <button class="secondary-button" :disabled="busy || !canReset" @click="resetLayer">恢复此范围默认</button>
      <button class="secondary-button" :disabled="busy || !selectedLayer" @click="previewAssembly"><Layers3 :size="16" />预览所选组装</button>
    </div>
    <div v-if="history?.versions.length" class="prompt-version-list"><h3>此范围的历史版本</h3>
      <div v-for="entry in history.versions" :key="entry.version"><span>第 {{ entry.version }} 版 · {{ entry.created_at }}</span><button class="secondary-button" :disabled="busy" @click="activateVersion(entry.version)">激活此版</button></div>
    </div>
    <div v-if="preview" class="prompt-assembly-preview"><h3>组装预览</h3><small>摘要 {{ preview.digest }}；运行时资料以占位符显示。</small>
      <article v-if="preview.assembled_template"><strong>固定协议与有效文学层的组合</strong><pre>{{ preview.assembled_template }}</pre></article>
      <article v-for="layer in preview.layers" :key="String(layer.layer_id)"><strong>{{ layer.layer_id }} · {{ layer.source }} {{ layer.version }}</strong><pre>{{ preview.texts[String(layer.layer_id)] }}</pre></article>
    </div>
    <div v-if="projectRoot" class="prompt-owned-assets">
      <span>作品表达层由原有编辑器维护：</span>
      <a href="#/agent?workspace=style">编辑作品文风</a>
      <a href="#/agent?workspace=archive">编辑人物档案</a>
    </div>
    <p class="privacy-note">正式 PromptAsset 共 {{ catalog?.formal_assets.length || 0 }} 项，正文可在这里保存版本；元数据、权限及 PromptProgram v3 合同保持固定。</p>
  </section>
</template>
