<script setup lang="ts">
import { onMounted, ref } from "vue";
import { FileText, LockKeyhole, Scale } from "lucide-vue-next";
import { api } from "@/services/api";

interface LegalSection { title: string; body: string }
interface LegalDocument { id: string; title: string; summary: string; sections: LegalSection[] }
const documents = ref<LegalDocument[]>([]);
const active = ref("terms");

onMounted(async () => {
  const payload = await api<{ documents: LegalDocument[] }>("/application/legal");
  documents.value = payload.documents || [];
});
</script>

<template>
  <div class="view legal-view">
    <header><span class="eyebrow">说明与约定</span><h1>创作保持开放，责任保持清楚</h1><p>这里说明 ArcVellum、本地数据、Agent、模型服务与公开发布之间的边界。</p></header>
    <div class="legal-layout">
      <nav aria-label="协议目录">
        <button v-for="document in documents" :key="document.id" :class="{ active: active === document.id }" @click="active = document.id">
          <Scale v-if="document.id === 'terms'" :size="17" />
          <LockKeyhole v-else-if="document.id === 'privacy'" :size="17" />
          <FileText v-else :size="17" />
          <span>{{ document.title }}</span>
        </button>
      </nav>
      <article v-for="document in documents" v-show="active === document.id" :key="document.id">
        <header><span>{{ document.title }}</span><p>{{ document.summary }}</p></header>
        <section v-for="section in document.sections" :key="section.title"><h2>{{ section.title }}</h2><p>{{ section.body }}</p></section>
      </article>
    </div>
  </div>
</template>
