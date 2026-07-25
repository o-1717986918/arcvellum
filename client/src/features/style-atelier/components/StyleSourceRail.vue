<script setup lang="ts">
import { BookOpen, Copyright, FileText, UserRound } from "lucide-vue-next";
import type { StyleAuthor, StyleWork } from "../types";

defineProps<{
  authors: StyleAuthor[];
  selectedAuthorId: string;
  selectedWorkId: string;
}>();

defineEmits<{
  selectAuthor: [authorId: string];
  selectWork: [workId: string];
}>();

function rightsLabel(author: StyleAuthor): string {
  if (author.rights.status !== "declared") return "权利信息待补";
  const labels: Record<string, string> = {
    public_domain: "公版语料",
    "public-domain": "公版语料",
    authorized: "已获授权",
    user_owned: "用户自有",
    "user-owned": "用户自有",
    craft_only: "仅学习技法",
    "craft-only": "仅学习技法",
  };
  return labels[String(author.rights.mode || "")] || "来源已声明";
}
</script>

<template>
  <aside class="style-source-rail" aria-label="作者与作品来源">
    <header>
      <span>语料谱系</span>
      <strong>作者项目</strong>
    </header>
    <div v-if="authors.length" class="style-author-list">
      <section v-for="author in authors" :key="author.author_id">
        <button
          class="style-author-button"
          :class="{ active: selectedAuthorId === author.author_id }"
          @click="$emit('selectAuthor', author.author_id)"
        >
          <span class="style-author-seal"><UserRound :size="15" /></span>
          <span>
            <strong>{{ author.name }}</strong>
            <small>{{ author.work_count }} 部作品 · {{ author.profile_count }} 份抽象</small>
          </span>
        </button>
        <div v-if="selectedAuthorId === author.author_id" class="style-author-body">
          <span class="style-rights" :data-state="author.rights.status">
            <Copyright :size="12" />{{ rightsLabel(author) }}
          </span>
          <button
            v-for="work in author.works"
            :key="work.work_id"
            class="style-work-button"
            :class="{ active: selectedWorkId === work.work_id }"
            @click="$emit('selectWork', work.work_id)"
          >
            <BookOpen :size="13" />
            <span><strong>{{ work.title }}</strong><small>{{ work.source_count }} 份来源</small></span>
          </button>
        </div>
      </section>
    </div>
    <div v-else class="style-rail-empty">
      <FileText :size="22" />
      <strong>还没有作者语料项目</strong>
      <p>下一步可从一位作者和一部作品开始建立来源记录。</p>
    </div>
  </aside>
</template>
