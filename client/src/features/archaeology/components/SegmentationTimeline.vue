<script setup lang="ts">
import { FileText, Layers3, ScanLine } from "lucide-vue-next";
import type {
  ArchaeologySegmentation,
  ArchaeologySource,
} from "../types";

defineProps<{
  sources: ArchaeologySource[];
  segmentation: ArchaeologySegmentation;
}>();

function compactNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN", { notation: "compact" }).format(value);
}
</script>

<template>
  <section class="archaeology-source-ledger">
    <header>
      <span><FileText :size="15" />来源底稿</span>
      <small>{{ sources.length }} 份来源</small>
    </header>
    <div class="archaeology-source-list">
      <article v-for="source in sources" :key="source.source_id">
        <span class="archaeology-source-icon"><FileText :size="14" /></span>
        <div>
          <strong>{{ source.filename || source.title }}</strong>
          <small>{{ compactNumber(source.character_count) }} 字 · {{ source.extraction_method || "文本解析" }}</small>
        </div>
        <i title="来源内容已按哈希固化">已固化</i>
      </article>
    </div>
    <header class="archaeology-segment-heading">
      <span><Layers3 :size="15" />结构切片</span>
      <small>{{ segmentation.segment_count }} 个段落 · {{ segmentation.chunk_count }} 个分析块</small>
    </header>
    <ol v-if="segmentation.chunks.length" class="archaeology-chunk-list">
      <li v-for="(chunk, index) in segmentation.chunks" :key="chunk.chunk_id">
        <span><ScanLine :size="13" /></span>
        <div>
          <strong>{{ chunk.title || `分析块 ${index + 1}` }}</strong>
          <small>{{ chunk.kind || "连续文本" }} · {{ chunk.evidence_count }} 条证据锚点</small>
        </div>
      </li>
    </ol>
    <div v-else class="archaeology-panel-empty">结构切片尚未建立。</div>
  </section>
</template>
