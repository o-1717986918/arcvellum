<script setup lang="ts">
import { Boxes, CircleAlert, CircleCheck, ShieldQuestion } from "lucide-vue-next";
import type { ArchaeologyReconstruction } from "../types";

defineProps<{ reconstruction: ArchaeologyReconstruction }>();

function domainLabel(value: string): string {
  return {
    character: "人物",
    world: "世界",
    plot: "情节",
    style: "文风观察",
    promise: "承诺与伏笔",
  }[value] || value || "未分类";
}

function assetTypeLabel(value: string): string {
  return {
    character: "人物档案",
    world: "世界规则",
    location: "地点",
    organization: "组织",
    plot: "情节规划",
    style: "文风观察",
    promise: "承诺与伏笔",
  }[value] || value || "候选资料";
}
</script>

<template>
  <section class="archaeology-reconstruction">
    <header>
      <span><Boxes :size="15" />候选项目重建</span>
      <small>{{ reconstruction.assets.length }} 份候选资料</small>
    </header>
    <div v-if="reconstruction.domains.length" class="archaeology-domain-strip">
      <article v-for="domain in reconstruction.domains" :key="domain.domain" :data-state="domain.status">
        <CircleCheck v-if="domain.status === 'pass'" :size="13" />
        <CircleAlert v-else-if="domain.blockers.length" :size="13" />
        <ShieldQuestion v-else :size="13" />
        <span><strong>{{ domainLabel(domain.domain) }}</strong><small>{{ domain.blockers.length ? `${domain.blockers.length} 项阻断` : domain.warnings.length ? `${domain.warnings.length} 项备注` : "已复核" }}</small></span>
      </article>
    </div>
    <div v-if="reconstruction.assets.length" class="archaeology-asset-grid">
      <article v-for="asset in reconstruction.assets" :key="asset.candidate_id">
        <span>
          <strong>{{ asset.candidate_id }}</strong>
          <i>{{ assetTypeLabel(asset.asset_type) }}</i>
        </span>
        <div>
          <small>{{ asset.evidence_count }} 条证据</small>
          <small v-if="asset.unresolved_count" class="warning">{{ asset.unresolved_count }} 项未决</small>
          <small v-else>无未决项</small>
        </div>
        <footer>
          <span :data-decision="asset.decision || asset.recommendation">
            {{ asset.decision === "promote" ? "建议入档" : asset.recommendation === "analysis_only" ? "仅作分析" : "等待复核" }}
          </span>
          <strong>{{ asset.confidence == null ? "—" : `${Math.round(asset.confidence * 100)}%` }}</strong>
        </footer>
      </article>
    </div>
    <div v-else class="archaeology-panel-empty">
      全书身份与冲突复核后，候选人物、世界、情节和文风资料会在这里出现。
    </div>
  </section>
</template>
