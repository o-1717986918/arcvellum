<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { Braces, FileCode2, LocateFixed } from "lucide-vue-next";
import { archiveAssetLabel, archiveFieldLabel } from "../registry/assetViews";
import type { ArchiveAssetDetail } from "../types";

const props = defineProps<{ asset: ArchiveAssetDetail; modelValue: string; mode: "structure" | "source" }>();
const emit = defineEmits<{ "update:modelValue": [value: string]; "update:mode": [value: "structure" | "source"] }>();
const editor = ref<HTMLTextAreaElement | null>(null);
const fields = computed(() => props.asset.writable_fields || []);

async function focusField(field: string): Promise<void> {
  const match = new RegExp(`^${escapeRegExp(field)}\\s*:`, "m").exec(props.modelValue);
  if (!match) return;
  await nextTick();
  editor.value?.focus();
  editor.value?.setSelectionRange(match.index, match.index + field.length);
  const line = props.modelValue.slice(0, match.index).split("\n").length;
  if (editor.value) editor.value.scrollTop = Math.max(0, (line - 3) * 21);
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
</script>

<template>
  <section class="archive-editor-pane">
    <header>
      <div>
        <span>{{ archiveAssetLabel(asset.asset_type) }} · 正式资产</span>
        <h2>{{ asset.title }}</h2>
        <p>{{ asset.source_path }} · {{ asset.revision.slice(0, 18) }}…</p>
      </div>
      <div class="archive-mode-switch" role="group" aria-label="编辑模式">
        <button :class="{ active: mode === 'structure' }" @click="emit('update:mode', 'structure')"><Braces :size="14" />结构导航</button>
        <button :class="{ active: mode === 'source' }" @click="emit('update:mode', 'source')"><FileCode2 :size="14" />完整文本</button>
      </div>
    </header>

    <div class="archive-editor-body" :class="{ 'source-only': mode === 'source' }">
      <aside v-if="mode === 'structure'" class="archive-field-rail">
        <span>可修改字段</span>
        <button v-for="field in fields" :key="field" @click="focusField(field)">
          <LocateFixed :size="12" />{{ archiveFieldLabel(field) }}
        </button>
        <p>复杂字段保留原有层级。点击字段会定位到对应内容，不会重排文件。</p>
      </aside>
      <label class="archive-source-editor">
        <span>{{ mode === "structure" ? "受控内容" : "专家模式 · 保存时仍会经过结构与引用检查" }}</span>
        <textarea
          ref="editor"
          spellcheck="false"
          :value="modelValue"
          @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
        ></textarea>
      </label>
    </div>
  </section>
</template>
