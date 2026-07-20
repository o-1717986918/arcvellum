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
        <h1>正文在创作中生长，也在这里成为一部书。</h1>
        <p>只展示已经通过正式门禁的内容。候选稿、审查记录和工程标记不会进入阅读长卷。</p>
      </div>
      <div class="reader-tally">
        <strong>{{ new Intl.NumberFormat('zh-CN').format(store.readerManifest?.total_chinese_content_chars || 0) }}</strong>
        <span>已晋升汉字与标点</span>
      </div>
    </section>
    <ManuscriptReader immersive />
  </div>
</template>
