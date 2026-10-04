<script setup lang="ts">
import { ref, watch } from "vue";
import { source, sourceChoices, sourceFromArchive, sourceFromFile } from "../services/stylometrySources";
import type { CorpusSource } from "../stylometryTypes";
import type { ArchiveAssetItem } from "@/features/archive/types";
const props = defineProps<{ projectRoot: string; sources: CorpusSource[]; busy: boolean }>();
const emit = defineEmits<{ "update:sources": [CorpusSource[]] }>();
const pasted = ref(""), error = ref(""), importing = ref(false);
const archive = ref<ArchiveAssetItem[]>([]), archiveId = ref("");
watch(() => props.projectRoot, () => { archive.value = []; archiveId.value = ""; pasted.value = ""; error.value = ""; });
function append(row: CorpusSource) { emit("update:sources", [...props.sources, row]); }
function paste() { if (pasted.value.trim()) { append(source(pasted.value)); pasted.value = ""; } }
async function files(event: Event) {
  const input = event.target as HTMLInputElement, epoch = props.projectRoot;
  importing.value = true; error.value = "";
  try {
    const rows = await Promise.all(Array.from(input.files || []).map(sourceFromFile));
    if (props.projectRoot === epoch) emit("update:sources", [...props.sources, ...rows]);
  } catch (problem) { error.value = String(problem); }
  finally { importing.value = false; input.value = ""; }
}
async function loadArchive() {
  const epoch = props.projectRoot;
  try { const rows = await sourceChoices(epoch); if (epoch === props.projectRoot) archive.value = rows; }
  catch (problem) { error.value = String(problem); }
}
async function importArchive() {
  const epoch = props.projectRoot;
  importing.value = true;
  try { const row = await sourceFromArchive(epoch, archiveId.value); if (epoch === props.projectRoot) append(row); }
  catch (problem) { error.value = String(problem); }
  finally { importing.value = false; }
}
</script>
<template>
  <div class="stylo-source-import">
    <div class="stylo-actions">
      <label class="stylo-file-button">导入 TXT / Markdown<input type="file" accept=".txt,.md,.markdown" multiple :disabled="busy || importing" @change="files" /></label>
      <button :disabled="busy || importing" @click="loadArchive">选择作品档案</button>
    </div>
    <div v-if="archive.length" class="stylo-actions">
      <select v-model="archiveId" aria-label="选择作品档案"><option value="">选择条目</option><option v-for="item in archive" :key="item.asset_id" :value="item.asset_id">{{ item.title }} · {{ item.asset_type }}</option></select>
      <button :disabled="!archiveId || busy || importing" @click="importArchive">加入语料</button>
    </div>
    <label>粘贴文本<textarea v-model="pasted" rows="5" placeholder="可先统计一个片段；建立画像时加入训练与留出两组语料。" /></label>
    <button :disabled="!pasted.trim() || busy || importing" @click="paste">加入文本</button>
    <p v-if="error" role="alert" class="stylo-error">{{ error }}</p>
    <p class="stylo-hint">作品编号用小写字母、数字和连字符。来自同一作品的篇章使用相同编号，留出语料可用于观察跨作品差异。</p>
    <article v-for="(row, index) in sources" :key="row.source_id" class="stylo-source-row">
      <header><strong>{{ row.origin || row.source_id }}</strong><small>{{ row.text.length.toLocaleString() }} 字符</small><button :disabled="busy" @click="emit('update:sources', sources.filter((_, i) => i !== index))">移除</button></header>
      <div class="stylo-source-fields">
        <label>作品编号<input v-model="row.work_id" /></label>
        <label>用途<select v-model="row.split"><option value="train">训练</option><option value="holdout">留出</option></select></label>
        <label>题材<input v-model="row.topic" /></label><label>体裁<input v-model="row.genre" /></label>
      </div>
      <details><summary>核对文本及来源</summary><textarea v-model="row.text" rows="5" /><code>{{ row.source_id }} · {{ row.revision || '导入副本' }}</code><label><input v-model="row.markdown" type="checkbox" />按 Markdown 提取正文</label></details>
    </article>
  </div>
</template>
