<script setup lang="ts">
import {
  Activity,
  Archive,
  BookOpenText,
  Fingerprint,
  Gauge,
  GitBranch,
  PackageCheck,
  PanelsTopLeft,
  ScanSearch,
  ShieldCheck,
  SlidersHorizontal,
  Telescope,
  Waypoints,
} from "lucide-vue-next";
import { computed } from "vue";
import { useSpatialWindowsStore } from "@/stores/spatialWindows";
import type { SpatialWindowKind } from "@/types/spatialWindows";

const props = defineProps<{ pendingChoices: number; deliveryReady: boolean }>();
const emit = defineEmits<{ open: [kind: Exclude<SpatialWindowKind, "node">]; organize: [] }>();
const windows = useSpatialWindowsStore();

const openKinds = computed(() => new Set(windows.windows.filter((item) => !item.collapsed).map((item) => item.kind)));

const instruments = [
  { kind: "progress", label: "推进", title: "推进当前作品", icon: Gauge },
  { kind: "agent", label: "执行", title: "查看 Agent 任务与会话", icon: Activity },
  { kind: "decisions", label: "决策", title: "处理等待你的创作决定", icon: GitBranch },
  { kind: "rules", label: "规则", title: "查看创作规则与节奏", icon: SlidersHorizontal },
  { kind: "delivery", label: "交付", title: "查看交付准备状态与正式文件", icon: PackageCheck },
] as const;

const workspaces = [
  { kind: "reader", label: "正文", title: "阅读已晋升正文", icon: BookOpenText },
  { kind: "archive", label: "档案", title: "维护人物与世界资产", icon: Archive },
  { kind: "style", label: "文风", title: "打开文风工坊", icon: Fingerprint },
  { kind: "quality", label: "质量", title: "调整语言与审查规则", icon: ShieldCheck },
  { kind: "strategy", label: "策略", title: "查看创作计划与结构", icon: Waypoints },
  { kind: "observatory", label: "观测", title: "打开 Agent 观测台", icon: Telescope },
  { kind: "archaeology", label: "考古", title: "从已有作品反向建立工程", icon: ScanSearch },
] as const;
</script>

<template>
  <nav class="spatial-workspace-dock" aria-label="空间工作台">
    <div class="dock-group primary-tools">
      <button
        v-for="item in instruments"
        :key="item.kind"
        :class="{
          active: openKinds.has(item.kind),
          urgent: item.kind === 'decisions' && pendingChoices > 0,
          'delivery-ready': item.kind === 'delivery' && props.deliveryReady,
        }"
        :title="item.title"
        :data-count="item.kind === 'decisions' && pendingChoices ? pendingChoices : undefined"
        @click="emit('open', item.kind)"
      ><component :is="item.icon" :size="16" /><span>{{ item.label }}</span></button>
    </div>
    <i class="dock-seam"></i>
    <div class="dock-group workspace-tools">
      <button
        v-for="item in workspaces"
        :key="item.kind"
        :class="{ active: openKinds.has(item.kind) }"
        :title="item.title"
        @click="emit('open', item.kind)"
      ><component :is="item.icon" :size="16" /><span>{{ item.label }}</span></button>
    </div>
    <i class="dock-seam"></i>
    <button class="dock-organize" title="整理打开的窗口" @click="emit('organize')"><PanelsTopLeft :size="16" /><span>整理</span></button>
  </nav>
</template>
