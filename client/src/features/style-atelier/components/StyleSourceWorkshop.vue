<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
  BookOpenCheck,
  FileInput,
  LibraryBig,
  ShieldCheck,
  UserRoundPlus,
  X,
} from "lucide-vue-next";
import type {
  StyleAuthor,
  StyleAuthorCreatePayload,
  StyleRightsMode,
  StyleSourceCreatePayload,
  StyleWorkCreatePayload,
} from "../types";

type WorkshopMode = "author" | "work" | "source";

const props = defineProps<{
  authors: StyleAuthor[];
  selectedAuthorId: string;
  selectedWorkId: string;
  busy: boolean;
}>();
const emit = defineEmits<{
  close: [];
  createAuthor: [payload: StyleAuthorCreatePayload];
  createWork: [payload: StyleWorkCreatePayload];
  importSource: [payload: StyleSourceCreatePayload];
}>();

const mode = ref<WorkshopMode>(props.authors.length ? "source" : "author");
const rightsModes: Array<{ value: StyleRightsMode; label: string; hint: string }> = [
  { value: "public-domain", label: "公版作品", hint: "版权保护期已结束或依法属于公有领域" },
  { value: "authorized", label: "已获授权", hint: "权利人明确允许用于本项目的文风分析" },
  { value: "user-owned", label: "本人作品", hint: "文本由你创作并拥有相应权利" },
  { value: "craft-only", label: "仅抽象技法", hint: "只归纳高层写作规律，不追求可识别表达" },
];
const authorForm = reactive<StyleAuthorCreatePayload>({
  author_id: "",
  name: "",
  rights_mode: "public-domain",
  rights_declaration: "",
});
const workForm = reactive<StyleWorkCreatePayload>({
  author_id: props.selectedAuthorId,
  work_id: "",
  title: "",
  year: "",
  notes: "",
});
const sourceForm = reactive<StyleSourceCreatePayload>({
  author_id: props.selectedAuthorId,
  work_id: props.selectedWorkId,
  filename: "source.txt",
  media_type: "text/plain",
  content: "",
  rights_mode: "public-domain",
  rights_declaration: "",
});

const selectedAuthor = computed(() =>
  props.authors.find((item) => item.author_id === sourceForm.author_id)
  || props.authors[0]
  || null,
);
const availableWorks = computed(() => selectedAuthor.value?.works || []);
const authorReady = computed(() =>
  /^[a-z0-9][a-z0-9-]{1,63}$/.test(authorForm.author_id)
  && authorForm.name.trim().length > 0
  && authorForm.rights_declaration.trim().length >= 12,
);
const workReady = computed(() =>
  Boolean(workForm.author_id)
  && /^[a-z0-9][a-z0-9-]{1,63}$/.test(workForm.work_id)
  && workForm.title.trim().length > 0,
);
const sourceReady = computed(() =>
  Boolean(sourceForm.author_id && sourceForm.work_id)
  && /\.(txt|md|markdown)$/i.test(sourceForm.filename)
  && sourceForm.content.trim().length > 0
  && sourceForm.rights_declaration.trim().length >= 12,
);

watch(
  () => props.selectedAuthorId,
  (authorId) => {
    if (!authorId) return;
    workForm.author_id = authorId;
    sourceForm.author_id = authorId;
    alignSourceWork();
  },
);
watch(
  () => props.selectedWorkId,
  (workId) => {
    if (workId && availableWorks.value.some((item) => item.work_id === workId)) {
      sourceForm.work_id = workId;
    }
  },
);
watch(() => sourceForm.author_id, alignSourceWork);
watch(() => sourceForm.media_type, (mediaType) => {
  const extension = mediaType === "text/markdown" ? ".md" : ".txt";
  sourceForm.filename = `${sourceForm.filename.replace(/\.(txt|md|markdown)$/i, "") || "source"}${extension}`;
});

function alignSourceWork(): void {
  if (!availableWorks.value.some((item) => item.work_id === sourceForm.work_id)) {
    sourceForm.work_id = availableWorks.value[0]?.work_id || "";
  }
}

function rightsHint(value: StyleRightsMode): string {
  return rightsModes.find((item) => item.value === value)?.hint || "";
}
</script>

<template>
  <div class="style-source-workshop-backdrop" role="presentation" @click.self="emit('close')">
    <section class="style-source-workshop" role="dialog" aria-modal="true" aria-labelledby="style-source-workshop-title">
      <header>
        <div>
          <span>Source ledger</span>
          <h2 id="style-source-workshop-title"><LibraryBig :size="18" />登记文风来源</h2>
          <p>先说明文本权利，再建立可追溯的作者、作品与来源谱系。</p>
        </div>
        <button title="关闭来源登记台" @click="emit('close')"><X :size="17" /></button>
      </header>

      <nav class="style-source-workshop-tabs" aria-label="来源登记步骤">
        <button :class="{ active: mode === 'author' }" @click="mode = 'author'">
          <UserRoundPlus :size="14" /><span><small>01</small>作者</span>
        </button>
        <button :class="{ active: mode === 'work' }" :disabled="!authors.length" @click="mode = 'work'">
          <BookOpenCheck :size="14" /><span><small>02</small>作品</span>
        </button>
        <button :class="{ active: mode === 'source' }" :disabled="!authors.some((item) => item.works.length)" @click="mode = 'source'">
          <FileInput :size="14" /><span><small>03</small>文本</span>
        </button>
      </nav>

      <form v-if="mode === 'author'" class="style-source-workshop-form" @submit.prevent="emit('createAuthor', { ...authorForm })">
        <div class="style-source-workshop-intro">
          <UserRoundPlus :size="19" /><span><strong>建立作者资料</strong><small>作者资料只保存身份与权利声明，不保存来源正文。</small></span>
        </div>
        <div class="style-source-form-grid">
          <label><span>作者名称</span><input v-model="authorForm.name" autocomplete="off" placeholder="例如：某位公版作家" /></label>
          <label><span>资料短名</span><input v-model="authorForm.author_id" autocomplete="off" placeholder="例如：classic-author" /><small>使用小写字母、数字和短横线</small></label>
        </div>
        <label>
          <span>权利依据</span>
          <select v-model="authorForm.rights_mode">
            <option v-for="item in rightsModes" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <small>{{ rightsHint(authorForm.rights_mode) }}</small>
        </label>
        <label>
          <span>权利说明</span>
          <textarea v-model="authorForm.rights_declaration" rows="3" placeholder="说明来源为何可以用于文风分析，至少 12 个字符。"></textarea>
        </label>
        <footer><span><ShieldCheck :size="14" />成功后会生成不可改写的事务回执</span><button class="primary" :disabled="!authorReady || busy">建立作者</button></footer>
      </form>

      <form v-else-if="mode === 'work'" class="style-source-workshop-form" @submit.prevent="emit('createWork', { ...workForm })">
        <div class="style-source-workshop-intro">
          <BookOpenCheck :size="19" /><span><strong>登记一部作品</strong><small>作品用于组织来源，不会自动成为可挂载文风。</small></span>
        </div>
        <div class="style-source-form-grid">
          <label><span>所属作者</span><select v-model="workForm.author_id"><option v-for="author in authors" :key="author.author_id" :value="author.author_id">{{ author.name }}</option></select></label>
          <label><span>作品名称</span><input v-model="workForm.title" autocomplete="off" placeholder="作品正式名称" /></label>
          <label><span>资料短名</span><input v-model="workForm.work_id" autocomplete="off" placeholder="例如：work-one" /><small>使用小写字母、数字和短横线</small></label>
          <label><span>创作年份</span><input v-model="workForm.year" autocomplete="off" placeholder="可选" /></label>
        </div>
        <label><span>备注</span><textarea v-model="workForm.notes" rows="3" placeholder="可选：版本、译本或来源背景。"></textarea></label>
        <footer><span>下一步可以为这部作品导入一份或多份文本。</span><button class="primary" :disabled="!workReady || busy">登记作品</button></footer>
      </form>

      <form v-else class="style-source-workshop-form style-source-text-form" @submit.prevent="emit('importSource', { ...sourceForm })">
        <div class="style-source-workshop-intro">
          <FileInput :size="19" /><span><strong>固化来源文本</strong><small>原文只进入受控资料库；工作台仅显示摘要与指纹。</small></span>
        </div>
        <div class="style-source-form-grid">
          <label><span>作者</span><select v-model="sourceForm.author_id"><option v-for="author in authors" :key="author.author_id" :value="author.author_id">{{ author.name }}</option></select></label>
          <label><span>作品</span><select v-model="sourceForm.work_id"><option v-for="work in availableWorks" :key="work.work_id" :value="work.work_id">{{ work.title }}</option></select></label>
          <label><span>文件名</span><input v-model="sourceForm.filename" autocomplete="off" placeholder="source.txt" /></label>
          <label><span>文本格式</span><select v-model="sourceForm.media_type"><option value="text/plain">纯文本</option><option value="text/markdown">Markdown</option></select></label>
          <label><span>权利依据</span><select v-model="sourceForm.rights_mode"><option v-for="item in rightsModes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label><span>权利说明</span><input v-model="sourceForm.rights_declaration" autocomplete="off" placeholder="说明这份文本的权利依据" /></label>
        </div>
        <label class="style-source-body"><span>来源正文</span><textarea v-model="sourceForm.content" rows="10" spellcheck="false" placeholder="粘贴用于分析的完整文本。导入后不会在工作台中回显。"></textarea></label>
        <footer><span><ShieldCheck :size="14" />系统会拒绝重复文本、路径文件名与无效编码</span><button class="primary" :disabled="!sourceReady || busy">导入并固化</button></footer>
      </form>
    </section>
  </div>
</template>
