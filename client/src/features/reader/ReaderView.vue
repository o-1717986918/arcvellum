<script setup lang="ts">
import { onMounted } from "vue";
import ManuscriptReader from "@/components/ManuscriptReader.vue";
import { useAppStore } from "@/stores/app";

const store = useAppStore();
onMounted(() => store.loadReaderManifest());
</script>

<template>
  <div class="view reader-view">
    <section class="reader-page-intro">
      <div>
        <span class="eyebrow">作品阅读</span>
        <h1>{{ store.currentProject?.title || '正文长卷' }}</h1>
        <p>正式正文 · 随创作推进持续收录，候选稿与审查记录留在创作现场。</p>
      </div>
      <div class="reader-tally">
        <strong>{{ new Intl.NumberFormat('zh-CN').format(store.readerManifest?.total_chinese_content_chars || 0) }}</strong>
        <span>正文汉字与标点</span>
      </div>
    </section>
    <ManuscriptReader immersive />
  </div>
</template>
