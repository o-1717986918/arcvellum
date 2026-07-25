<script setup lang="ts">
import { computed, ref } from "vue";
import { Braces, ChevronDown, ChevronUp, ListPlus, Plus, Trash2 } from "lucide-vue-next";

defineOptions({ name: "StructuredValueEditor" });
const props = withDefaults(
  defineProps<{ modelValue: unknown; table?: boolean; depth?: number }>(),
  { table: false, depth: 0 },
);
const emit = defineEmits<{ "update:modelValue": [value: unknown] }>();
const newKey = ref("");

const isArray = computed(() => Array.isArray(props.modelValue));
const isObject = computed(
  () => Boolean(props.modelValue) && typeof props.modelValue === "object" && !isArray.value,
);
const objectEntries = computed(() =>
  isObject.value ? Object.entries(props.modelValue as Record<string, unknown>) : [],
);

function updateArray(index: number, value: unknown): void {
  const next = [...(props.modelValue as unknown[])];
  next[index] = value;
  emit("update:modelValue", next);
}

function removeArray(index: number): void {
  emit("update:modelValue", (props.modelValue as unknown[]).filter((_, itemIndex) => itemIndex !== index));
}

function moveArray(index: number, offset: number): void {
  const next = [...(props.modelValue as unknown[])];
  const target = index + offset;
  if (target < 0 || target >= next.length) return;
  [next[index], next[target]] = [next[target], next[index]];
  emit("update:modelValue", next);
}

function appendArray(value: unknown): void {
  emit("update:modelValue", [...(props.modelValue as unknown[]), value]);
}

function updateObject(key: string, value: unknown): void {
  emit("update:modelValue", { ...(props.modelValue as Record<string, unknown>), [key]: value });
}

function removeObject(key: string): void {
  const next = { ...(props.modelValue as Record<string, unknown>) };
  delete next[key];
  emit("update:modelValue", next);
}

function addObjectKey(): void {
  const key = newKey.value.trim();
  if (!key || Object.prototype.hasOwnProperty.call(props.modelValue || {}, key)) return;
  updateObject(key, "");
  newKey.value = "";
}

function updatePrimitive(event: Event): void {
  const target = event.target as HTMLInputElement;
  if (typeof props.modelValue === "number") {
    emit("update:modelValue", target.value === "" ? 0 : Number(target.value));
  } else if (typeof props.modelValue === "boolean") {
    emit("update:modelValue", target.checked);
  } else {
    emit("update:modelValue", target.value);
  }
}
</script>

<template>
  <div v-if="isArray" class="archive-value-list" :class="{ table }">
    <article v-for="(item, index) in (modelValue as unknown[])" :key="index">
      <header>
        <span>{{ table ? `条目 ${index + 1}` : `第 ${index + 1} 项` }}</span>
        <div>
          <button title="上移" :disabled="index === 0" @click="moveArray(index, -1)"><ChevronUp :size="12" /></button>
          <button title="下移" :disabled="index === (modelValue as unknown[]).length - 1" @click="moveArray(index, 1)"><ChevronDown :size="12" /></button>
          <button title="删除" @click="removeArray(index)"><Trash2 :size="12" /></button>
        </div>
      </header>
      <StructuredValueEditor
        :model-value="item"
        :depth="depth + 1"
        @update:model-value="updateArray(index, $event)"
      />
    </article>
    <div class="archive-value-actions">
      <button @click="appendArray('')"><Plus :size="12" />新增文本</button>
      <button v-if="table || !(modelValue as unknown[]).length || typeof (modelValue as unknown[])[0] === 'object'" @click="appendArray({})">
        <ListPlus :size="12" />新增条目
      </button>
    </div>
  </div>

  <div v-else-if="isObject" class="archive-value-object">
    <article v-for="[key, value] in objectEntries" :key="key">
      <header>
        <span>{{ key.replaceAll("_", " ") }}</span>
        <button title="删除属性" @click="removeObject(key)"><Trash2 :size="11" /></button>
      </header>
      <StructuredValueEditor
        :model-value="value"
        :depth="depth + 1"
        @update:model-value="updateObject(key, $event)"
      />
    </article>
    <div class="archive-object-add">
      <Braces :size="12" />
      <input v-model="newKey" placeholder="新增属性名" @keyup.enter="addObjectKey" />
      <button :disabled="!newKey.trim()" @click="addObjectKey"><Plus :size="12" /></button>
    </div>
  </div>

  <label v-else-if="typeof modelValue === 'boolean'" class="archive-value-boolean">
    <input type="checkbox" :checked="modelValue" @change="updatePrimitive" />
    <span>{{ modelValue ? "是" : "否" }}</span>
  </label>
  <input
    v-else
    class="archive-value-input"
    :type="typeof modelValue === 'number' ? 'number' : 'text'"
    :value="modelValue == null ? '' : String(modelValue)"
    @input="updatePrimitive"
  />
</template>
