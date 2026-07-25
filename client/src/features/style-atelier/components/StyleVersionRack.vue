<script setup lang="ts">
import { Check, CircleAlert, Layers3, LockKeyhole, Radio } from "lucide-vue-next";
import type { StyleMount, StyleVersion } from "../types";

defineProps<{
  versions: StyleVersion[];
  activeMount: StyleMount;
  selectedKey: string;
}>();

defineEmits<{ select: [version: StyleVersion] }>();

function keyOf(version: StyleVersion): string {
  return `${version.style_id}:${version.version_id || version.planned_version_id || version.profile_id}`;
}

function stateLabel(version: StyleVersion): string {
  if (version.mounted) return "正在用于创作";
  if (version.state === "conflict") return "完整性冲突";
  if (version.built) return "可挂载版本";
  if (version.state === "build-ready") return "等待构建";
  if (version.review_status === "pass") return "已通过审查";
  return "工程处理中";
}

function versionLabel(version: StyleVersion): string {
  const identity = version.version_id || version.planned_version_id || "";
  if (!identity) return "等待编号";
  if (/^[a-f0-9]{24,}$/i.test(identity)) return `版本 ${identity.slice(0, 8)}`;
  return identity;
}
</script>

<template>
  <aside class="style-version-rack" aria-label="文风版本">
    <header>
      <span>版本架</span>
      <strong>不可变文风</strong>
    </header>
    <div v-if="activeMount.style_id" class="style-active-mount">
      <Radio :size="15" />
      <span><small>当前作品正在使用</small><strong>{{ activeMount.author || activeMount.profile_id || activeMount.style_id }}</strong></span>
    </div>
    <div class="style-version-list">
      <button
        v-for="version in versions"
        :key="keyOf(version)"
        :class="{ active: selectedKey === keyOf(version) }"
        :data-state="version.state"
        @click="$emit('select', version)"
      >
        <span class="style-version-icon">
          <CircleAlert v-if="version.state === 'conflict'" :size="14" />
          <Check v-else-if="version.mounted" :size="14" />
          <LockKeyhole v-else :size="14" />
        </span>
        <span>
          <strong>{{ version.display_name || version.profile_id || "未命名文风" }}</strong>
          <small>{{ stateLabel(version) }}</small>
        </span>
        <i :title="version.version_id || version.planned_version_id">{{ versionLabel(version) }}</i>
      </button>
    </div>
    <div v-if="!versions.length" class="style-rack-empty">
      <Layers3 :size="22" />
      <strong>还没有文风版本</strong>
      <p>抽象、评测与独立审查完成后，版本会在这里形成可追溯记录。</p>
    </div>
  </aside>
</template>
