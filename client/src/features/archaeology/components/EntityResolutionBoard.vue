<script setup lang="ts">
import { CircleHelp, Fingerprint, UsersRound } from "lucide-vue-next";
import type { ArchaeologyEntities } from "../types";

defineProps<{ entities: ArchaeologyEntities }>();

function confidence(value: number | null): string {
  return value == null ? "待评估" : `${Math.round(value * 100)}%`;
}

function typeLabel(value: string): string {
  return {
    character: "人物",
    location: "地点",
    organization: "组织",
    object: "物件",
  }[value] || "实体";
}

function resolutionLabel(value: string): string {
  return {
    single: "单一身份",
    merged: "别名已合并",
    keep_distinct: "保持区分",
    unresolved: "仍有歧义",
    partial: "部分确认",
  }[value] || "等待解析";
}
</script>

<template>
  <section class="archaeology-entity-board">
    <header>
      <span><Fingerprint :size="15" />人物与别名</span>
      <small>{{ entities.resolved_count }} 组身份 · {{ entities.occurrence_count }} 次出现</small>
    </header>
    <div v-if="entities.groups.length" class="archaeology-entity-list">
      <article v-for="entity in entities.groups" :key="entity.entity_id" :data-resolution="entity.resolution">
        <span class="archaeology-entity-avatar"><UsersRound :size="16" /></span>
        <div class="archaeology-entity-copy">
          <span><strong>{{ entity.display_name }}</strong><i>{{ typeLabel(entity.entity_type) }}</i></span>
          <small v-if="entity.aliases.length">{{ entity.aliases.join(" · ") }}</small>
          <small v-else>没有发现其他称呼</small>
          <p v-if="entity.unknowns.length"><CircleHelp :size="12" />{{ entity.unknowns[0] }}</p>
        </div>
        <div class="archaeology-confidence">
          <strong>{{ confidence(entity.confidence) }}</strong>
          <small>{{ resolutionLabel(entity.resolution) }}</small>
        </div>
      </article>
    </div>
    <div v-else class="archaeology-panel-empty">
      分块理解完成后，人物、地点与别名会在这里汇合。
    </div>
  </section>
</template>
