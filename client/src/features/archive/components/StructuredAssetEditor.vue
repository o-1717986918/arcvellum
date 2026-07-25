<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Check, Plus, RotateCcw, Trash2 } from "lucide-vue-next";
import MarkdownAssetEditor from "./MarkdownAssetEditor.vue";
import StructuredValueEditor from "./StructuredValueEditor.vue";
import type { ArchiveStructuredDocument, ArchiveStructuredField } from "../types";

const props = defineProps<{ document: ArchiveStructuredDocument; busy?: boolean }>();
const emit = defineEmits<{ apply: [fields: Record<string, unknown>] }>();
const values = ref<Record<string, unknown>>({});
const baseline = ref<Record<string, unknown>>({});
const documentFields = computed(() =>
  Array.isArray(props.document.fields) ? props.document.fields : [],
);

const sections = computed(() => {
  const grouped = new Map<string, ArchiveStructuredField[]>();
  for (const field of documentFields.value) {
    const items = grouped.get(field.section) || [];
    items.push(field);
    grouped.set(field.section, items);
  }
  return [...grouped.entries()].map(([name, fields]) => ({ name, fields }));
});
const changedFields = computed(() => {
  const changed: Record<string, unknown> = {};
  for (const field of documentFields.value) {
    if (stableValue(values.value[field.name]) !== stableValue(baseline.value[field.name])) {
      changed[field.name] = cloneValue(values.value[field.name]);
    }
  }
  return changed;
});
const hasChanges = computed(() => Object.keys(changedFields.value).length > 0);

watch(
  () => props.document.source_revision,
  () => hydrate(),
  { immediate: true },
);

function hydrate(): void {
  const next: Record<string, unknown> = {};
  for (const field of documentFields.value) {
    next[field.name] = field.defined ? cloneValue(field.value) : emptyValue(field);
  }
  values.value = next;
  baseline.value = cloneValue(next) as Record<string, unknown>;
}

function update(name: string, value: unknown): void {
  values.value = { ...values.value, [name]: value };
}

function updateText(name: string, event: Event): void {
  update(name, (event.target as HTMLInputElement).value);
}

function updateNumber(name: string, event: Event): void {
  const value = (event.target as HTMLInputElement).value;
  update(name, value === "" ? 0 : Number(value));
}

function updateStringList(name: string, index: number, value: string): void {
  const next = [...asStringList(values.value[name])];
  next[index] = value;
  update(name, next);
}

function removeStringList(name: string, index: number): void {
  update(name, asStringList(values.value[name]).filter((_, itemIndex) => itemIndex !== index));
}

function resetField(name: string): void {
  update(name, cloneValue(baseline.value[name]));
}

function applyChanges(): void {
  if (hasChanges.value) emit("apply", changedFields.value);
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function emptyValue(field: ArchiveStructuredField): unknown {
  if (["string-list", "table"].includes(field.kind)) return [];
  if (field.kind === "object") return {};
  if (field.kind === "number") return 0;
  return "";
}

function stableValue(value: unknown): string {
  return JSON.stringify(value) ?? "undefined";
}

function cloneValue<T>(value: T): T {
  return value === undefined ? value : JSON.parse(JSON.stringify(value)) as T;
}
</script>

<template>
  <div class="archive-structured-editor">
    <header class="archive-structured-toolbar">
      <div>
        <strong>结构化校勘</strong>
        <span>{{ document.document_format.toUpperCase() }} · 仅修改 Registry 允许的字段</span>
      </div>
      <button class="primary" :disabled="!hasChanges || busy" @click="applyChanges">
        <Check :size="13" />应用 {{ Object.keys(changedFields).length || "" }} 项到草稿
      </button>
    </header>

    <div class="archive-structured-scroll">
      <section v-for="section in sections" :key="section.name" class="archive-form-section">
        <header>
          <span>{{ section.name }}</span>
          <small>{{ section.fields.length }} 个字段</small>
        </header>
        <div class="archive-form-fields">
          <label
            v-for="field in section.fields"
            :key="field.name"
            class="archive-form-field"
            :class="{ 'archive-form-field-wide': ['markdown', 'object', 'table'].includes(field.kind) }"
          >
            <header>
              <span>{{ field.label }}<i v-if="field.required">必填</i></span>
              <button
                v-if="stableValue(values[field.name]) !== stableValue(baseline[field.name])"
                type="button"
                title="撤销本字段修改"
                @click="resetField(field.name)"
              ><RotateCcw :size="11" /></button>
            </header>
            <small v-if="field.help_text">{{ field.help_text }}</small>

            <select
              v-if="field.kind === 'choice'"
              :value="String(values[field.name] ?? '')"
              @change="updateText(field.name, $event)"
            >
              <option v-for="option in field.options || []" :key="option" :value="option">{{ option }}</option>
            </select>
            <input
              v-else-if="field.kind === 'number'"
              type="number"
              :value="Number(values[field.name] ?? 0)"
              @input="updateNumber(field.name, $event)"
            />
            <MarkdownAssetEditor
              v-else-if="field.kind === 'markdown'"
              :model-value="String(values[field.name] ?? '')"
              @update:model-value="update(field.name, $event)"
            />
            <div v-else-if="field.kind === 'string-list'" class="archive-string-list">
              <div v-for="(item, index) in asStringList(values[field.name])" :key="index">
                <input :value="item" @input="updateStringList(field.name, index, ($event.target as HTMLInputElement).value)" />
                <button type="button" title="删除" @click="removeStringList(field.name, index)"><Trash2 :size="12" /></button>
              </div>
              <button type="button" @click="update(field.name, [...asStringList(values[field.name]), ''])"><Plus :size="12" />新增一项</button>
            </div>
            <StructuredValueEditor
              v-else-if="field.kind === 'object' || field.kind === 'table'"
              :model-value="values[field.name]"
              :table="field.kind === 'table'"
              @update:model-value="update(field.name, $event)"
            />
            <input
              v-else
              type="text"
              :value="String(values[field.name] ?? '')"
              @input="updateText(field.name, $event)"
            />
          </label>
        </div>
      </section>
    </div>
  </div>
</template>
