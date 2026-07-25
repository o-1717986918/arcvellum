<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  CheckCircle2,
  FilePlus2,
  FileSearch,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-vue-next";
import { archiveAssetLabel } from "../registry/assetViews";
import type {
  ArchiveCreationOption,
  ArchiveCreationPayload,
  ArchiveCreationPreview,
} from "../types";

const props = defineProps<{
  options: ArchiveCreationOption[];
  preview: ArchiveCreationPreview | null;
  busy: boolean;
}>();
const emit = defineEmits<{
  close: [];
  resetPreview: [];
  preview: [payload: ArchiveCreationPayload];
  create: [payload: ArchiveCreationPayload];
}>();

const selectedType = ref("");
const localId = ref("");
const content = ref("");
const reason = ref("");
const ownerWaiver = ref(false);
const generatedContent = ref("");

const selected = computed(() =>
  props.options.find((item) => item.asset_type === selectedType.value) || null,
);
const validation = computed(() => props.preview?.validation || {});
const impact = computed(() => props.preview?.impact || {});
const issues = computed(() => {
  const value = validation.value.issues;
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];
});
const assetId = computed(() => {
  if (!selected.value) return "";
  const stable = selected.value.fixed_id || localId.value.trim();
  return stable ? `${selected.value.asset_type}:${stable}` : "";
});
const readyForPreview = computed(() =>
  Boolean(
    selected.value?.available
    && assetId.value
    && content.value.trim()
    && !content.value.includes("__ASSET_ID__")
    && reason.value.trim().length >= 6
    && ownerWaiver.value,
  ),
);
const payload = computed<ArchiveCreationPayload>(() => ({
  asset_type: selected.value?.asset_type || "",
  local_id: selected.value?.fixed_id || localId.value.trim(),
  content: content.value,
  semantic_review: "waived",
  reason: reason.value.trim(),
  expected_impacts: impactNames(impact.value),
}));

watch(
  () => props.options,
  (options) => {
    if (!selectedType.value) {
      const first = options.find((item) => item.available);
      if (first) selectOption(first);
    }
  },
  { immediate: true },
);

watch(localId, () => {
  if (!selected.value || selected.value.fixed_id) return;
  if (!content.value || content.value === generatedContent.value) applyTemplate();
  else invalidatePreview();
});

watch([content, reason, ownerWaiver], invalidatePreview);

function selectOption(option: ArchiveCreationOption): void {
  selectedType.value = option.asset_type;
  localId.value = option.fixed_id || "";
  reason.value = "";
  ownerWaiver.value = false;
  applyTemplate();
  emit("resetPreview");
}

function applyTemplate(): void {
  if (!selected.value) return;
  const stable = selected.value.fixed_id || localId.value.trim();
  generatedContent.value = selected.value.template.replaceAll("__ASSET_ID__", stable || "__ASSET_ID__");
  content.value = generatedContent.value;
  emit("resetPreview");
}

function invalidatePreview(): void {
  if (props.preview) emit("resetPreview");
}

function impactNames(value: Record<string, unknown>): string[] {
  const categories = value.stale_categories;
  return Array.isArray(categories) ? categories.map(String) : [];
}
</script>

<template>
  <div class="archive-create-backdrop" role="presentation" @click.self="emit('close')">
    <section class="archive-create-panel" role="dialog" aria-modal="true" aria-labelledby="archive-create-title">
      <header>
        <div>
          <span>作者事务 · 新建正式资料</span>
          <h2 id="archive-create-title"><FilePlus2 :size="19" />建立作品资产</h2>
          <p>选择受支持的资料类型。创建前会核对身份、结构、引用和目标占用。</p>
        </div>
        <button title="关闭" @click="emit('close')"><X :size="17" /></button>
      </header>

      <div class="archive-create-grid">
        <aside class="archive-create-types">
          <span>资料类型</span>
          <button
            v-for="option in options"
            :key="option.asset_type"
            :class="{ active: option.asset_type === selectedType }"
            :disabled="!option.available"
            @click="selectOption(option)"
          >
            <FilePlus2 :size="14" />
            <span>
              <strong>{{ archiveAssetLabel(option.asset_type) }}</strong>
              <small>{{ option.available ? option.editor_kind : option.unavailable_reason }}</small>
            </span>
          </button>
        </aside>

        <main class="archive-create-editor">
          <div class="archive-create-identity">
            <label v-if="selected && !selected.fixed_id">
              <span>稳定 ID</span>
              <input v-model="localId" placeholder="例如 new_character" />
            </label>
            <label v-else>
              <span>正式身份</span>
              <input :value="assetId" readonly />
            </label>
            <button :disabled="!selected" title="重新套用该类型的标准模板" @click="applyTemplate">
              <RefreshCw :size="14" />套用模板
            </button>
          </div>
          <label class="archive-create-source">
            <span>资料内容</span>
            <textarea v-model="content" spellcheck="false"></textarea>
          </label>
          <label class="archive-create-reason">
            <span>创建原因</span>
            <textarea v-model="reason" placeholder="说明这份正式资料在作品中的作用"></textarea>
          </label>
          <label class="archive-owner-check">
            <input v-model="ownerWaiver" type="checkbox" />
            <span>以作者决定创建正式资产，并保留完整版本与影响记录</span>
          </label>
        </main>

        <aside class="archive-create-review">
          <header><FileSearch :size="15" /><strong>创建前检查</strong></header>
          <div v-if="!preview" class="archive-create-empty">
            <ShieldCheck :size="24" />
            <strong>尚未检查</strong>
            <p>填写稳定 ID、内容和原因后，先检查再创建。</p>
          </div>
          <template v-else>
            <div class="archive-create-verdict" :class="{ pass: preview.committable }">
              <CheckCircle2 :size="17" />
              <span><strong>{{ preview.committable ? "可以创建" : "仍有阻断" }}</strong><small>{{ assetId }}</small></span>
            </div>
            <ul v-if="issues.length">
              <li v-for="issue in issues" :key="String(issue.code)">{{ issue.message }}</li>
            </ul>
            <dl>
              <div><dt>直接引用</dt><dd>{{ impact.reference_count || 0 }}</dd></div>
              <div><dt>受影响类别</dt><dd>{{ impactNames(impact).join("、") || "无" }}</dd></div>
            </dl>
          </template>
        </aside>
      </div>

      <footer>
        <span>{{ assetId || "请先选择类型并填写稳定 ID" }}</span>
        <div>
          <button :disabled="!readyForPreview || busy" @click="emit('preview', payload)">
            <FileSearch :size="14" />检查资料
          </button>
          <button class="primary" :disabled="!preview?.committable || busy" @click="emit('create', payload)">
            <FilePlus2 :size="14" />创建正式资料
          </button>
        </div>
      </footer>
    </section>
  </div>
</template>
