<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
  BookOpenText,
  Check,
  ChevronRight,
  FileArchive,
  FileText,
  ShieldCheck,
  Upload,
  X,
} from "lucide-vue-next";
import type {
  ArchaeologyImportForm,
  ArchaeologyModeId,
  ArchaeologyOptions,
} from "../types";

const props = defineProps<{
  open: boolean;
  options: ArchaeologyOptions | null;
  busy: boolean;
}>();

const emit = defineEmits<{
  close: [];
  import: [file: File, form: ArchaeologyImportForm];
}>();

const fileInput = ref<HTMLInputElement | null>(null);
const selectedFile = ref<File | null>(null);
const localError = ref("");
const form = reactive<ArchaeologyImportForm>({
  title: "",
  work_id: "",
  mode: "continuation",
  rights_declaration: "",
  chunk_size: 6000,
  overwrite: false,
});

const maxBytes = computed(() => props.options?.max_source_bytes || 25 * 1024 * 1024);
const accept = computed(() => (props.options?.supported_extensions || [".txt", ".md", ".docx"]).join(","));
const canSubmit = computed(
  () => Boolean(selectedFile.value && form.rights_declaration.trim() && !localError.value && !props.busy),
);

watch(
  () => props.open,
  (open) => {
    if (!open) return;
    localError.value = "";
  },
);

function chooseFile(): void {
  fileInput.value?.click();
}

function selectFile(event: Event): void {
  const file = (event.target as HTMLInputElement).files?.[0] || null;
  localError.value = "";
  if (!file) {
    selectedFile.value = null;
    return;
  }
  const suffix = `.${file.name.split(".").pop()?.toLowerCase() || ""}`;
  if (!props.options?.supported_extensions.includes(suffix)) {
    localError.value = "请选择 TXT、Markdown 或 DOCX 文件。";
    selectedFile.value = null;
    return;
  }
  if (file.size > maxBytes.value) {
    localError.value = `文件不能超过 ${formatBytes(maxBytes.value)}。`;
    selectedFile.value = null;
    return;
  }
  selectedFile.value = file;
  if (!form.title.trim()) form.title = file.name.replace(/\.[^.]+$/, "");
}

function submit(): void {
  if (!selectedFile.value || !canSubmit.value) return;
  emit("import", selectedFile.value, { ...form });
}

function setMode(mode: ArchaeologyModeId): void {
  form.mode = mode;
}

function formatBytes(value: number): string {
  return value >= 1024 * 1024
    ? `${Math.round(value / 1024 / 1024)} MB`
    : `${Math.round(value / 1024)} KB`;
}
</script>

<template>
  <Teleport to="body">
    <Transition name="archaeology-dialog">
      <div v-if="open" class="archaeology-import-backdrop" role="presentation" @mousedown.self="emit('close')">
        <section class="archaeology-import-dialog" role="dialog" aria-modal="true" aria-label="导入已有作品">
          <header>
            <span class="archaeology-dialog-sigil"><FileArchive :size="22" /></span>
            <div>
              <small>已有作品</small>
              <h2>导入并建立证据底稿</h2>
              <p>原文会被完整保全，提取结果先进入候选区。</p>
            </div>
            <button class="icon-button" title="关闭" @click="emit('close')"><X :size="17" /></button>
          </header>

          <div class="archaeology-import-body">
            <section class="archaeology-file-drop" :data-ready="Boolean(selectedFile)" @click="chooseFile">
              <input ref="fileInput" type="file" :accept="accept" @change="selectFile" />
              <span><FileText :size="24" /></span>
              <div v-if="selectedFile">
                <strong>{{ selectedFile.name }}</strong>
                <small>{{ formatBytes(selectedFile.size) }} · 已准备导入</small>
              </div>
              <div v-else>
                <strong>选择 TXT、Markdown 或 DOCX</strong>
                <small>单个文件不超过 {{ formatBytes(maxBytes) }}</small>
              </div>
              <button type="button"><Upload :size="14" />选择文件</button>
            </section>
            <p v-if="localError" class="archaeology-field-error">{{ localError }}</p>

            <fieldset class="archaeology-mode-picker">
              <legend>这次准备怎样使用原作</legend>
              <button
                v-for="mode in options?.modes || []"
                :key="mode.id"
                type="button"
                :class="{ active: form.mode === mode.id }"
                @click="setMode(mode.id)"
              >
                <span><Check v-if="form.mode === mode.id" :size="13" /></span>
                <strong>{{ mode.label }}</strong>
                <small>{{ mode.intent }}</small>
              </button>
            </fieldset>

            <div class="archaeology-import-fields">
              <label>
                <span>作品名称</span>
                <input v-model="form.title" placeholder="默认使用文件名" />
              </label>
              <label>
                <span>内部识别名 <small>可留空</small></span>
                <input v-model="form.work_id" placeholder="例如 old-manuscript" />
              </label>
            </div>

            <label class="archaeology-rights-field">
              <span><ShieldCheck :size="15" />使用依据</span>
              <textarea
                v-model="form.rights_declaration"
                rows="3"
                placeholder="说明你有权分析和使用这份文本，例如：本人创作并授权用于项目整理。"
              ></textarea>
            </label>

            <div class="archaeology-import-controls">
              <label>
                <span>每段分析规模</span>
                <input v-model.number="form.chunk_size" type="range" min="1000" max="20000" step="1000" />
                <strong>{{ form.chunk_size.toLocaleString("zh-CN") }} 字符</strong>
              </label>
              <label class="archaeology-overwrite">
                <input v-model="form.overwrite" type="checkbox" />
                <span>若识别名重复，以这次导入重建候选底稿</span>
              </label>
            </div>
          </div>

          <footer>
            <span><BookOpenText :size="14" />导入不会直接改变正式人物、世界观或正文。</span>
            <button class="archaeology-primary" :disabled="!canSubmit" @click="submit">
              {{ busy ? "正在保全原文" : "开始导入" }}<ChevronRight :size="15" />
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
