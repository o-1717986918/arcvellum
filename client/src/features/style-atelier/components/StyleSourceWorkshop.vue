<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
  BookOpenCheck,
  ClipboardPaste,
  FileInput,
  FileText,
  FileUp,
  LibraryBig,
  ShieldCheck,
  Trash2,
  UserRoundPlus,
  X,
} from "lucide-vue-next";
import {
  decodeStyleSourceFile,
  decodeStyleSourceFileLenient,
  sanitizeStyleSourceText,
  StyleSourceEncodingError,
  type StyleSourceEncoding,
  type PreparedStyleSource,
} from "../services/styleSourceFiles";
import { styleIdentity } from "../services/styleIdentity";
import type {
  StyleAuthor,
  StyleAuthorCreatePayload,
  StyleRightsMode,
  StyleSourceCreatePayload,
  StyleWorkCreatePayload,
} from "../types";

type WorkshopMode = "author" | "work" | "source";
type SourceInputMode = "file" | "paste";

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
  importSources: [payloads: StyleSourceCreatePayload[]];
}>();

const mode = ref<WorkshopMode>(props.authors.length ? "source" : "author");
const sourceInputMode = ref<SourceInputMode>("file");
const fileInput = ref<HTMLInputElement | null>(null);
const preparedFiles = ref<PreparedStyleSource[]>([]);
const fileError = ref("");
const sourceEncoding = ref<StyleSourceEncoding>("auto");
const lenientOffer = ref<{
  filename: string;
  replacementCount: number;
  file: File;
} | null>(null);
const formError = ref("");
const authorIdEdited = ref(false);
const workIdEdited = ref(false);
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
  && (
    sourceInputMode.value === "file"
      ? preparedFiles.value.length > 0
      : /\.(txt|md|markdown)$/i.test(sourceForm.filename) && sourceForm.content.trim().length > 0
  )
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
watch(mode, () => { formError.value = ""; });
watch(() => authorForm.name, (name) => {
  if (!authorIdEdited.value) authorForm.author_id = styleIdentity(name, "author");
  formError.value = "";
});
watch(() => workForm.title, (title) => {
  if (!workIdEdited.value) workForm.work_id = styleIdentity(title, "work");
  formError.value = "";
});
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

async function chooseSourceFiles(event: Event): Promise<void> {
  fileError.value = "";
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  if (!files.length) return;
  if (preparedFiles.value.length + files.length > 20) {
    fileError.value = "一次最多登记 20 份文本，请分批导入。";
    input.value = "";
    return;
  }
  const additions: PreparedStyleSource[] = [];
  for (const file of files) {
    try {
      const prepared = await decodeStyleSourceFile(file, sourceEncoding.value);
      if (!preparedFiles.value.some((item) => item.file_key === prepared.file_key)
        && !additions.some((item) => item.file_key === prepared.file_key)) {
        additions.push(prepared);
      }
    } catch (cause) {
      if (
        cause instanceof StyleSourceEncodingError
        && cause.replacementCount > 0
      ) {
        lenientOffer.value = {
          filename: file.name,
          replacementCount: cause.replacementCount,
          file,
        };
      } else {
        fileError.value = cause instanceof Error ? cause.message : "文件没有成功读取。";
        break;
      }
    }
  }
  preparedFiles.value = [...preparedFiles.value, ...additions];
  input.value = "";
}

async function confirmLenientImport(): Promise<void> {
  const offer = lenientOffer.value;
  if (!offer) return;
  try {
    const prepared = await decodeStyleSourceFileLenient(
      offer.file,
      sourceEncoding.value,
    );
    preparedFiles.value = [...preparedFiles.value, prepared];
    lenientOffer.value = null;
  } catch (cause) {
    fileError.value = cause instanceof Error ? cause.message : "文件没有成功读取。";
  }
}

function cancelLenientOffer(): void {
  lenientOffer.value = null;
}

function removePreparedFile(fileKey: string): void {
  preparedFiles.value = preparedFiles.value.filter((item) => item.file_key !== fileKey);
}

function submitAuthor(): void {
  formError.value = "";
  if (!authorReady.value) {
    formError.value = !authorForm.name.trim()
      ? "请填写作者名称。"
      : !/^[a-z0-9][a-z0-9-]{1,63}$/.test(authorForm.author_id)
        ? "资料短名需由 2 至 64 个小写字母、数字或短横线组成。"
        : "请用至少 12 个字符说明文本的权利依据。";
    return;
  }
  emit("createAuthor", { ...authorForm });
}

function submitWork(): void {
  formError.value = "";
  if (!workReady.value) {
    formError.value = !workForm.author_id
      ? "请先选择所属作者。"
      : !workForm.title.trim()
        ? "请填写作品名称。"
        : "资料短名需由 2 至 64 个小写字母、数字或短横线组成。";
    return;
  }
  emit("createWork", { ...workForm });
}

function submitSources(): void {
  formError.value = "";
  if (sourceInputMode.value === "paste") {
    const sanitized = sanitizeStyleSourceText(sourceForm.content);
    if (!sanitized.ok) {
      formError.value = sanitized.message || "请填写来源正文。";
      return;
    }
    sourceForm.content = sanitized.content;
  }
  if (!sourceReady.value) {
    formError.value = !sourceForm.author_id || !sourceForm.work_id
      ? "请先选择作者和作品。"
      : sourceForm.rights_declaration.trim().length < 12
        ? "请用至少 12 个字符说明这批文本的权利依据。"
        : sourceInputMode.value === "file"
          ? "请先选择至少一份 TXT 或 Markdown 文件。"
          : "请填写合法文件名并粘贴来源正文。";
    return;
  }
  const shared = {
    author_id: sourceForm.author_id,
    work_id: sourceForm.work_id,
    rights_mode: sourceForm.rights_mode,
    rights_declaration: sourceForm.rights_declaration,
  };
  const payloads: StyleSourceCreatePayload[] = sourceInputMode.value === "file"
    ? preparedFiles.value.map((item) => ({
        ...shared,
        filename: item.filename,
        media_type: item.media_type,
        content: item.content,
      }))
    : [{ ...sourceForm }];
  emit("importSources", payloads);
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

      <form v-if="mode === 'author'" class="style-source-workshop-form" @submit.prevent="submitAuthor">
        <div class="style-source-workshop-intro">
          <UserRoundPlus :size="19" /><span><strong>建立作者资料</strong><small>作者资料只保存身份与权利声明，不保存来源正文。</small></span>
        </div>
        <div class="style-source-form-grid">
          <label><span>作者名称</span><input v-model="authorForm.name" autocomplete="off" placeholder="例如：某位公版作家" @input="formError = ''" /></label>
          <label><span>资料短名</span><input v-model="authorForm.author_id" autocomplete="off" placeholder="例如：classic-author" @input="authorIdEdited = true; formError = ''" /><small>已自动生成，也可改为小写字母、数字和短横线</small></label>
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
            <textarea v-model="authorForm.rights_declaration" rows="3" placeholder="说明来源为何可以用于文风分析，至少 12 个字符。" @input="formError = ''"></textarea>
        </label>
        <p v-if="formError" class="style-source-file-error" role="alert">{{ formError }}</p>
        <footer><span><ShieldCheck :size="14" />成功后会生成不可改写的事务回执</span><button class="primary" :disabled="busy">建立作者</button></footer>
      </form>

      <form v-else-if="mode === 'work'" class="style-source-workshop-form" @submit.prevent="submitWork">
        <div class="style-source-workshop-intro">
          <BookOpenCheck :size="19" /><span><strong>登记一部作品</strong><small>作品用于组织来源，不会自动成为可挂载文风。</small></span>
        </div>
        <div class="style-source-form-grid">
          <label><span>所属作者</span><select v-model="workForm.author_id"><option v-for="author in authors" :key="author.author_id" :value="author.author_id">{{ author.name }}</option></select></label>
          <label><span>作品名称</span><input v-model="workForm.title" autocomplete="off" placeholder="作品正式名称" @input="formError = ''" /></label>
          <label><span>资料短名</span><input v-model="workForm.work_id" autocomplete="off" placeholder="例如：work-one" @input="workIdEdited = true; formError = ''" /><small>已自动生成，也可改为小写字母、数字和短横线</small></label>
          <label><span>创作年份</span><input v-model="workForm.year" autocomplete="off" placeholder="可选" /></label>
        </div>
        <label><span>备注</span><textarea v-model="workForm.notes" rows="3" placeholder="可选：版本、译本或来源背景。"></textarea></label>
        <p v-if="formError" class="style-source-file-error" role="alert">{{ formError }}</p>
        <footer><span>下一步可以为这部作品导入一份或多份文本。</span><button class="primary" :disabled="busy">登记作品</button></footer>
      </form>

      <form v-else class="style-source-workshop-form style-source-text-form" @submit.prevent="submitSources">
        <div class="style-source-workshop-intro">
          <FileInput :size="19" /><span><strong>固化来源文本</strong><small>原文只进入受控资料库；工作台仅显示摘要与指纹。</small></span>
        </div>
        <div class="style-source-form-grid">
          <label><span>作者</span><select v-model="sourceForm.author_id"><option v-for="author in authors" :key="author.author_id" :value="author.author_id">{{ author.name }}</option></select></label>
          <label><span>作品</span><select v-model="sourceForm.work_id"><option v-for="work in availableWorks" :key="work.work_id" :value="work.work_id">{{ work.title }}</option></select></label>
          <label><span>权利依据</span><select v-model="sourceForm.rights_mode"><option v-for="item in rightsModes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label><span>权利说明</span><input v-model="sourceForm.rights_declaration" autocomplete="off" placeholder="说明这份文本的权利依据" @input="formError = ''" /></label>
        </div>
        <div class="style-source-input-switch" role="tablist" aria-label="语料输入方式">
          <button type="button" :class="{ active: sourceInputMode === 'file' }" @click="sourceInputMode = 'file'"><FileUp :size="14" />选择文件</button>
          <button type="button" :class="{ active: sourceInputMode === 'paste' }" @click="sourceInputMode = 'paste'"><ClipboardPaste :size="14" />粘贴文本</button>
        </div>
        <section v-if="sourceInputMode === 'file'" class="style-source-file-import">
          <label class="style-source-encoding">
            <span>文件编码</span>
            <select v-model="sourceEncoding">
              <option value="auto">自动检测</option>
              <option value="utf-8">UTF-8</option>
              <option value="gb18030">GB18030 / GBK</option>
              <option value="big5">BIG5</option>
              <option value="utf-16">UTF-16</option>
            </select>
          </label>
          <input ref="fileInput" class="style-source-file-input" type="file" accept=".txt,.md,.markdown,text/plain,text/markdown" multiple @change="chooseSourceFiles" />
          <button type="button" class="style-source-file-picker" @click="fileInput?.click()">
            <FileUp :size="21" />
            <span><strong>从电脑选择语料文件</strong><small>支持 TXT、Markdown 与常见中文编码（UTF-8/GB18030/BIG5/UTF-16）；一次最多 20 份</small></span>
          </button>
          <p v-if="fileError" class="style-source-file-error" role="alert">{{ fileError }}</p>
          <div v-if="lenientOffer" class="style-source-lenient-offer" role="alert">
            <p>“{{ lenientOffer.filename }}”包含 {{ lenientOffer.replacementCount }} 个无法还原的替换字符（�）。移除这些字符后导入，文风分析会缺少这些位置的原字。</p>
            <footer>
              <button type="button" @click="cancelLenientOffer">取消</button>
              <button type="button" class="primary" @click="confirmLenientImport">移除 {{ lenientOffer.replacementCount }} 个并导入</button>
            </footer>
          </div>
          <div v-if="preparedFiles.length" class="style-source-file-queue" aria-label="待导入语料">
            <article v-for="file in preparedFiles" :key="file.file_key">
              <FileText :size="15" />
              <span><strong>{{ file.filename }}</strong><small>{{ file.character_count.toLocaleString('zh-CN') }} 字符 · {{ file.media_type === 'text/markdown' ? 'Markdown' : '纯文本' }}</small></span>
              <small v-if="file.replacement_count" class="style-source-lossy-note">已移除 {{ file.replacement_count }} 个损坏字符</small>
              <button type="button" :title="`移除 ${file.filename}`" @click="removePreparedFile(file.file_key)"><Trash2 :size="14" /></button>
            </article>
          </div>
        </section>
        <template v-else>
          <div class="style-source-form-grid">
            <label><span>文件名</span><input v-model="sourceForm.filename" autocomplete="off" placeholder="source.txt" /></label>
            <label><span>文本格式</span><select v-model="sourceForm.media_type"><option value="text/plain">纯文本</option><option value="text/markdown">Markdown</option></select></label>
          </div>
          <label class="style-source-body"><span>来源正文</span><textarea v-model="sourceForm.content" rows="10" spellcheck="false" placeholder="粘贴用于分析的完整文本。导入后不会在工作台中回显。"></textarea></label>
        </template>
        <p v-if="formError" class="style-source-file-error" role="alert">{{ formError }}</p>
        <footer><span><ShieldCheck :size="14" />系统会拒绝重复文本、路径文件名与无效编码</span><button class="primary" :disabled="busy">导入并固化{{ sourceInputMode === 'file' && preparedFiles.length > 1 ? `（${preparedFiles.length} 份）` : '' }}</button></footer>
      </form>
    </section>
  </div>
</template>
