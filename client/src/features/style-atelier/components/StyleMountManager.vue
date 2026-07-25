<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowRight,
  Check,
  GitCompareArrows,
  History,
  LockKeyhole,
  ShieldCheck,
  TriangleAlert,
  X,
} from "lucide-vue-next";
import type {
  StyleMount,
  StyleMountPreview,
  StyleVersion,
} from "../types";
import "../styleMountManager.css";

const props = defineProps<{
  version: StyleVersion;
  activeMount: StyleMount;
  preview: StyleMountPreview | null;
  busy: boolean;
}>();

defineEmits<{
  preview: [];
  confirm: [];
  close: [];
}>();

const mountable = computed(() => Boolean(
  props.version.built
  && props.version.style_id
  && props.version.version_id
  && props.version.content_hash
  && props.version.state !== "conflict",
));
const mounted = computed(() => Boolean(
  props.version.mounted
  || (
    props.activeMount.style_id === props.version.style_id
    && props.activeMount.version_id === props.version.version_id
    && props.activeMount.content_hash === props.version.content_hash
  ),
));

function short(value: unknown): string {
  const text = String(value || "");
  return text ? `${text.slice(0, 8)}…${text.slice(-5)}` : "未建立";
}

function stageLabel(stage: string): string {
  const labels: Record<string, string> = {
    context: "上下文",
    composition: "场景编排",
    generation: "生成契约",
    candidate: "候选正文",
    review: "审查",
    revision: "修订",
  };
  return labels[stage] || stage;
}
</script>

<template>
  <section class="style-mount-manager" :data-state="mounted ? 'mounted' : version.state">
    <div class="style-mount-manager-copy">
      <span class="style-mount-seal">
        <Check v-if="mounted" :size="15" />
        <LockKeyhole v-else :size="15" />
      </span>
      <span>
        <small>作品挂载</small>
        <strong>{{ mounted ? "当前创作正在使用此版本" : mountable ? "可成为作品的正式文风" : "尚未到达挂载条件" }}</strong>
      </span>
    </div>
    <button
      v-if="!mounted"
      class="style-mount-preview-button"
      :disabled="busy || !mountable"
      @click="$emit('preview')"
    >
      <GitCompareArrows :size="15" />
      <span>{{ busy ? "正在核对影响" : mountable ? "比较并挂载" : "等待构建与审查" }}</span>
    </button>
    <span v-else class="style-mount-live"><ShieldCheck :size="14" />精确快照已锁定</span>
  </section>

  <Teleport to="body">
    <div v-if="preview" class="style-mount-dialog-layer" @click.self="$emit('close')">
      <section class="style-mount-dialog" role="dialog" aria-modal="true" aria-labelledby="style-mount-title">
        <header>
          <div>
            <span class="style-section-label">Mount gate</span>
            <h2 id="style-mount-title">确认作品文风版本</h2>
            <p>这次确认只切换表达约束。已晋升正文保留原有版本证据，不会被静默改写。</p>
          </div>
          <button class="style-icon-button" title="关闭挂载预览" @click="$emit('close')">
            <X :size="18" />
          </button>
        </header>

        <div class="style-mount-identity">
          <span>
            <small>当前版本</small>
            <strong>{{ short(preview.current.version_id) }}</strong>
          </span>
          <ArrowRight :size="20" />
          <span>
            <small>目标版本</small>
            <strong>{{ short(preview.target.version_id) }}</strong>
          </span>
          <span class="style-mount-lock">
            <LockKeyhole :size="13" />
            {{ short(preview.target.content_hash) }}
          </span>
        </div>

        <section class="style-mount-comparison">
          <header>
            <GitCompareArrows :size="16" />
            <strong>版本证据对照</strong>
            <small>{{ preview.comparison.changes.length }} 项变化</small>
          </header>
          <div class="style-mount-comparison-grid">
            <article
              v-for="row in preview.comparison.evidence"
              :key="row.field"
              :data-changed="row.changed"
            >
              <small>{{ row.label }}</small>
              <span><i>{{ row.before }}</i><ArrowRight :size="12" /><strong>{{ row.after }}</strong></span>
            </article>
          </div>
        </section>

        <section class="style-mount-impact" :data-state="preview.impact.status">
          <header>
            <TriangleAlert v-if="preview.impact.affected_scene_count" :size="16" />
            <History v-else :size="16" />
            <strong>
              {{ preview.impact.affected_scene_count
                ? `${preview.impact.affected_scene_count} 个未晋升场景需要刷新`
                : "没有未晋升场景需要返工" }}
            </strong>
            <small>历史正文始终保留</small>
          </header>
          <div v-if="preview.impact.entries.length" class="style-mount-impact-list">
            <article v-for="entry in preview.impact.entries" :key="entry.scene_id">
              <span><strong>{{ entry.scene_id }}</strong><small>{{ entry.artifact_count }} 项旧证据</small></span>
              <div>
                <i v-for="stage in entry.stages" :key="stage">{{ stageLabel(stage) }}</i>
              </div>
            </article>
          </div>
          <p v-else>下一项创作任务会直接读取目标版本，不需要重做已有工作。</p>
        </section>

        <footer>
          <button class="style-secondary-button" :disabled="busy" @click="$emit('close')">返回检查</button>
          <button class="style-confirm-mount" :disabled="busy" @click="$emit('confirm')">
            <ShieldCheck :size="16" />
            <span>{{ busy ? "正在锁定版本" : "确认挂载这个版本" }}</span>
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
