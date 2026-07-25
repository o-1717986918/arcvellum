<script setup lang="ts">
import { Braces, FileCode2, LoaderCircle } from "lucide-vue-next";
import { archiveAssetLabel } from "../registry/assetViews";
import type { ArchiveAssetDetail, ArchiveStructuredDocument } from "../types";
import AdvancedYamlEditor from "./AdvancedYamlEditor.vue";
import StructuredAssetEditor from "./StructuredAssetEditor.vue";

defineProps<{
  asset: ArchiveAssetDetail;
  modelValue: string;
  mode: "structure" | "source";
  structure: ArchiveStructuredDocument | null;
  busy?: boolean;
}>();
const emit = defineEmits<{
  "update:modelValue": [value: string];
  "update:mode": [value: "structure" | "source"];
  "apply-structure": [fields: Record<string, unknown>];
}>();
</script>

<template>
  <section class="archive-editor-pane">
    <header>
      <div>
        <span>{{ archiveAssetLabel(asset.asset_type) }} · 正式资产</span>
        <h2>{{ asset.title }}</h2>
        <p>{{ asset.source_path }} · {{ asset.revision.slice(0, 18) }}…</p>
      </div>
      <div class="archive-mode-switch" role="group" aria-label="编辑模式">
        <button :class="{ active: mode === 'structure' }" @click="emit('update:mode', 'structure')">
          <Braces :size="14" />结构化编辑
        </button>
        <button :class="{ active: mode === 'source' }" @click="emit('update:mode', 'source')">
          <FileCode2 :size="14" />专家源文本
        </button>
      </div>
    </header>

    <StructuredAssetEditor
      v-if="mode === 'structure' && structure"
      :document="structure"
      :busy="busy"
      @apply="emit('apply-structure', $event)"
    />
    <div v-else-if="mode === 'structure'" class="archive-structure-loading">
      <LoaderCircle :size="18" />
      <span>正在建立字段契约…</span>
    </div>
    <AdvancedYamlEditor
      v-else
      :model-value="modelValue"
      :document-format="structure?.document_format"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </section>
</template>
