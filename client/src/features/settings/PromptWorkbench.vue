<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { Check, ChevronDown, ChevronRight, FileJson, Layers3 } from "lucide-vue-next";
import { settingsClient, type PromptCatalog, type PromptFlowNode, type PromptHistory, type PromptPreview } from "./services/settingsClient";

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
const expandedNodes = ref<string[]>(["scene", "scene.entry"]);
const selectedLayer = computed(() => catalog.value?.layers.find((layer) => layer.layer_id === layerId.value));
const visibleLayers = computed(() => (catalog.value?.layers || []).filter((layer) => {
  const matchesGroup = responsibility.value === "all" || layer.responsibility === responsibility.value;
  const needle = query.value.trim().toLocaleLowerCase();
  return matchesGroup && (!needle || `${layer.layer_id} ${layer.purpose} ${layer.owner} ${layer.flow_stage}`.toLocaleLowerCase().includes(needle));
}));
const filteredTree = computed(() => {
  const visible = new Set(visibleLayers.value.map((layer) => layer.layer_id));
  return (catalog.value?.flow_tree || []).map((node) => filterFlowNode(node, visible))
    .filter((node): node is PromptFlowNode => node !== null);
});
const fixedCount = computed(() => catalog.value?.layers.filter((layer) => !layer.editable).length || 0);
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
watch([query, responsibility, filteredTree], () => {
  if (!query.value.trim() && responsibility.value === "all") return;
  const branches = filteredTree.value.flatMap((group) => [group.id, ...(group.children || []).map((stage) => stage.id)]);
  expandedNodes.value = [...new Set([...expandedNodes.value, ...branches])];
});

async function loadCatalog(): Promise<void> {
  busy.value = true;
  try {
    catalog.value = await settingsClient.promptCatalog(scopedRoot.value);
    if (!catalog.value.layers.some((layer) => layer.layer_id === layerId.value)) {
      layerId.value = catalog.value.layers[0]?.layer_id || "";
    }
    expandSelectedPath();
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

function filterFlowNode(node: PromptFlowNode, visible: Set<string>): PromptFlowNode | null {
  if (node.layer_id) return visible.has(node.layer_id) ? node : null;
  const children = (node.children || []).map((child) => filterFlowNode(child, visible))
    .filter((child): child is PromptFlowNode => child !== null);
  return children.length ? { ...node, children, count: children.reduce((sum, child) => sum + (child.count || 1), 0) } : null;
}

function isExpanded(id: string): boolean { return expandedNodes.value.includes(id); }
function toggleNode(id: string): void {
  expandedNodes.value = expandedNodes.value.includes(id)
    ? expandedNodes.value.filter((item) => item !== id) : [...expandedNodes.value, id];
}
function selectLeaf(id: string): void { layerId.value = id; expandSelectedPath(); }
function expandSelectedPath(): void {
  const stage = selectedLayer.value?.flow_stage;
  if (!stage) return;
  const group = catalog.value?.flow_tree.find((node) => node.children?.some((child) => child.id === stage));
  expandedNodes.value = [...new Set([...expandedNodes.value, stage, ...(group ? [group.id] : [])])];
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
    <header><span class="section-icon iris"><FileJson :size="18" /></span><div><h2>提示词工作台</h2><p>沿创作流程查看文学指引与固定结构；可编辑层按作品或全局保存版本。</p></div></header>
    <p v-if="feedback" class="inline-feedback">{{ feedback }}</p>
    <div class="prompt-workbench-controls">
      <label class="field"><span>搜索用途或 ID</span><input v-model="query" type="search" aria-label="搜索提示词" placeholder="例如：主创、审读、formal.asset" /></label>
      <label class="field"><span>职责层</span><select v-model="responsibility" aria-label="提示词职责筛选">
        <option value="all">全部职责</option><option value="identity">身份初始化</option><option value="stage">阶段任务</option>
        <option value="protocol">固定结构模板</option><option value="formal-asset">正式任务正文</option>
      </select></label>
      <label class="field"><span>编辑范围</span><select v-model="scope" aria-label="提示词范围">
        <option value="global">所有作品</option><option value="project" :disabled="!projectRoot">当前作品</option>
      </select></label>
    </div>
    <div class="prompt-workbench-layout">
      <nav class="prompt-flow-tree" aria-label="创作流程提示词">
        <p class="prompt-flow-summary">{{ catalog?.layers.length || 0 }} 个有效条目 · {{ fixedCount }} 个固定结构</p>
        <p v-if="!filteredTree.length" class="prompt-flow-empty">没有符合筛选条件的提示词。</p>
        <div v-for="group in filteredTree" :key="group.id" class="prompt-flow-group">
          <button class="prompt-tree-branch" type="button" :aria-expanded="isExpanded(group.id)" @click="toggleNode(group.id)">
            <ChevronDown v-if="isExpanded(group.id)" :size="15" /><ChevronRight v-else :size="15" />
            <span>{{ group.label }}</span><small>{{ group.count }}</small>
          </button>
          <div v-if="isExpanded(group.id)" class="prompt-flow-stages">
            <div v-for="stage in group.children" :key="stage.id" class="prompt-flow-stage">
              <button class="prompt-tree-branch prompt-tree-stage" type="button" :aria-expanded="isExpanded(stage.id)" @click="toggleNode(stage.id)">
                <ChevronDown v-if="isExpanded(stage.id)" :size="14" /><ChevronRight v-else :size="14" />
                <span>{{ stage.label }}</span><small>{{ stage.count }}</small>
              </button>
              <div v-if="isExpanded(stage.id)" class="prompt-flow-leaves">
                <button v-for="leaf in stage.children" :key="leaf.id" class="prompt-tree-leaf" type="button"
                  :class="{ active: layerId === leaf.layer_id }" :aria-current="layerId === leaf.layer_id ? 'true' : undefined"
                  @click="selectLeaf(leaf.layer_id!)">
                  <span>{{ leaf.label }}</span><small>{{ leaf.layer_id }}</small>
                  <em v-if="!catalog?.layers.find((layer) => layer.layer_id === leaf.layer_id)?.editable">固定</em>
                </button>
              </div>
            </div>
          </div>
        </div>
      </nav>
      <div v-if="selectedLayer" class="prompt-workbench-detail">
        <div class="prompt-detail-heading"><div><h3>{{ selectedLayer.purpose }}</h3><p>{{ selectedLayer.layer_id }}</p></div><span>{{ selectedLayer.editable ? '可编辑提示词' : '固定结构模板 · 只读' }}</span></div>
        <p class="prompt-layer-meta">当前采用 {{ selectedLayer.source }} 第 {{ selectedLayer.version }} 版 · {{ selectedLayer.owner }} · {{ { 'formal-route': '正式任务', 'active': '创作流程', 'opt-in': '待启用', 'historical': '历史留档', 'experimental': '实验开关控制' }[selectedLayer.usage_status] }}</p>
        <p class="prompt-layer-meta">{{ hasDiff ? '有效版本与随包默认不同' : '当前使用随包默认文本' }}</p>
        <div v-if="selectedLayer.editable" class="prompt-workbench-columns">
          <label class="field"><span>随包默认</span><textarea :value="selectedLayer.default_text" readonly rows="12" /></label>
          <label class="field"><span>可编辑提示词正文</span><textarea v-model="draft" rows="12" :maxlength="12000" /></label>
        </div>
        <section v-else class="prompt-fixed-template"><h4>完整结构与占位槽位</h4><pre>{{ selectedLayer.effective_text }}</pre></section>
        <div class="button-row">
          <button v-if="selectedLayer.editable" class="primary-button" :disabled="busy || !draft.trim() || (scope === 'project' && !projectRoot)" @click="saveLayer"><Check :size="16" />保存新版本</button>
          <button v-if="selectedLayer.editable" class="secondary-button" :disabled="busy || !canReset" @click="resetLayer">恢复此范围默认</button>
          <button class="secondary-button" :disabled="busy" @click="previewAssembly"><Layers3 :size="16" />预览所选组装</button>
        </div>
        <div v-if="history?.versions.length" class="prompt-version-list"><h3>此范围的历史版本</h3>
          <div v-for="entry in history.versions" :key="entry.version"><span>第 {{ entry.version }} 版 · {{ entry.created_at }}</span><button class="secondary-button" :disabled="busy" @click="activateVersion(entry.version)">激活此版</button></div>
        </div>
        <div v-if="preview" class="prompt-assembly-preview"><h3>组装预览</h3><small>摘要 {{ preview.digest }}；运行时资料以占位符显示。</small>
          <article v-if="preview.assembled_template"><strong>固定协议与有效文学层的组合</strong><pre>{{ preview.assembled_template }}</pre></article>
          <article v-for="layer in preview.layers" :key="String(layer.layer_id)"><strong>{{ layer.layer_id }} · {{ layer.source }} {{ layer.version }}</strong><pre>{{ preview.texts[String(layer.layer_id)] }}</pre></article>
        </div>
      </div>
    </div>
    <div v-if="projectRoot" class="prompt-owned-assets">
      <span>作品表达层由原有编辑器维护：</span>
      <a href="#/agent?workspace=style">编辑作品文风</a>
      <a href="#/agent?workspace=archive">编辑人物档案</a>
    </div>
    <p class="privacy-note">正式 Agent 提示资产 {{ catalog?.formal_assets.length || 0 }} 项；固定结构、任务元数据与权限只读。</p>
  </section>
</template>
