<script setup lang="ts">
import {
  Archive,
  BookOpenCheck,
  Boxes,
  FileStack,
  Fingerprint,
  ScanSearch,
  ShieldCheck,
} from "lucide-vue-next";
import type { ArchaeologyJourneyStage } from "../types";

defineProps<{ stages: ArchaeologyJourneyStage[] }>();

const icons = {
  source: BookOpenCheck,
  segments: FileStack,
  chunks: ScanSearch,
  identity: Fingerprint,
  reconstruction: Boxes,
  review: ShieldCheck,
  archive: Archive,
};
</script>

<template>
  <ol class="archaeology-journey" aria-label="作品整理进度">
    <li v-for="stage in stages" :key="stage.id" :data-state="stage.status">
      <span class="archaeology-journey-node">
        <component :is="icons[stage.id as keyof typeof icons] || ScanSearch" :size="14" />
      </span>
      <span>
        <strong>{{ stage.label }}</strong>
        <small v-if="stage.status === 'complete'">已完成<template v-if="stage.count"> · {{ stage.count }}</template></small>
        <small v-else-if="stage.status === 'active'">正在进行<template v-if="stage.count"> · {{ stage.count }}</template></small>
        <small v-else>等待前序结果</small>
      </span>
    </li>
  </ol>
</template>
