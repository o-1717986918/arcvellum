<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  Activity,
  ArrowRight,
  Beaker,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  CirclePause,
  Layers3,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Square,
} from "lucide-vue-next";
import { styleIdentity } from "../services/styleIdentity";
import type {
  StyleAuthor,
  StyleCompilePayload,
  StyleTaskDescriptor,
  StyleVersion,
  StyleWorkerEvent,
  StyleWorkerJob,
} from "../types";

type SourceRole = "training" | "holdout" | "unused";

const props = defineProps<{
  authors: StyleAuthor[];
  selectedAuthorId: string;
  selectedVersion: StyleVersion | null;
  job: StyleWorkerJob | null;
  task: StyleTaskDescriptor | null;
  events: StyleWorkerEvent[];
  busy: boolean;
  streamError: string;
}>();
const emit = defineEmits<{
  compile: [payload: Omit<StyleCompilePayload, "project_root">];
  advance: [authorId: string, profileId: string];
  build: [authorId: string, profileId: string];
  approveWriteback: [];
  rejectWriteback: [reason: string];
  retry: [];
  stop: [];
}>();

const expanded = ref(false);
const authorId = ref(props.selectedAuthorId);
const profileId = ref("");
const displayName = ref("");
const sourceRoles = ref<Record<string, SourceRole>>({});
const setupError = ref("");
const profileIdEdited = ref(false);

const author = computed(() =>
  props.authors.find((item) => item.author_id === authorId.value)
  || props.authors[0]
  || null,
);
const sources = computed(() =>
  (author.value?.works || []).flatMap((work) =>
    work.sources.map((source) => ({
      ...source,
      work_id: work.work_id,
      work_title: work.title,
      key: `${work.work_id}:${source.source_id}`,
    })),
  ),
);
const trainingSources = computed(() =>
  sources.value
    .filter((item) => sourceRoles.value[item.key] === "training")
    .map((item) => ({ work_id: item.work_id, source_id: item.source_id })),
);
const holdoutSources = computed(() =>
  sources.value
    .filter((item) => sourceRoles.value[item.key] === "holdout")
    .map((item) => ({ work_id: item.work_id, source_id: item.source_id })),
);
const compileReady = computed(() =>
  /^[a-z0-9][a-z0-9-]{1,63}$/.test(profileId.value)
  && displayName.value.trim().length > 0
  && trainingSources.value.length > 0
  && holdoutSources.value.length > 0,
);
const compileRequirement = computed(() => {
  if (!displayName.value.trim()) return "请先填写文风名称。";
  if (!/^[a-z0-9][a-z0-9-]{1,63}$/.test(profileId.value)) return "版本短名需由 2 至 64 个小写字母、数字或短横线组成。";
  if (!trainingSources.value.length) return "请至少指定一份用于学习的文本。";
  if (!holdoutSources.value.length) return "请至少指定一份只用于隔离评测的文本。";
  return "";
});
const active = computed(() => ["queued", "running", "stopping"].includes(props.job?.status || ""));
const jobMessage = computed(() =>
  String(props.job?.result?.message || props.job?.error || statusMessage(props.job?.status || "")),
);
const visibleEvents = computed(() => props.events.slice(-4).reverse());
const continuationIdentity = computed(() => ({
  authorId: props.selectedVersion?.author_id || authorId.value,
  profileId: props.selectedVersion?.profile_id || profileId.value,
}));
const canContinue = computed(() =>
  Boolean(continuationIdentity.value.authorId && continuationIdentity.value.profileId)
  && !active.value
  && props.job?.status !== "waiting_writeback",
);
const buildReady = computed(() =>
  props.selectedVersion?.state === "build-ready"
  || props.selectedVersion?.build_status === "ready",
);

watch(
  () => props.selectedAuthorId,
  (value) => {
    if (value) authorId.value = value;
  },
);
watch(authorId, () => initializeSourceRoles());
watch(sources, initializeSourceRoles, { immediate: true });
watch(displayName, (name) => {
  if (!profileIdEdited.value) profileId.value = styleIdentity(name, "style");
  setupError.value = "";
});
watch(sourceRoles, () => { setupError.value = ""; }, { deep: true });
watch(
  () => props.selectedVersion,
  (version) => {
    if (!version) return;
    if (!profileId.value) profileId.value = version.profile_id;
    if (!displayName.value) displayName.value = version.display_name || version.profile_id;
  },
  { immediate: true },
);
watch(
  () => props.job,
  (job) => {
    if (job) expanded.value = true;
  },
  { immediate: true },
);

function initializeSourceRoles(): void {
  const next: Record<string, SourceRole> = {};
  sources.value.forEach((item, index) => {
    next[item.key] = sourceRoles.value[item.key]
      || (index === sources.value.length - 1 && sources.value.length > 1 ? "holdout" : "training");
  });
  sourceRoles.value = next;
}

function startCompilation(): void {
  setupError.value = compileRequirement.value;
  if (!compileReady.value) return;
  emit("compile", {
    author_id: authorId.value,
    profile_id: profileId.value,
    display_name: displayName.value.trim(),
    training_sources: trainingSources.value,
    holdout_sources: holdoutSources.value,
    runtime: "pi-worker",
  });
}

function continueCurrent(): void {
  const identity = continuationIdentity.value;
  if (!identity.authorId || !identity.profileId) return;
  if (buildReady.value) emit("build", identity.authorId, identity.profileId);
  else emit("advance", identity.authorId, identity.profileId);
}

function stateLabel(value: string): string {
  const labels: Record<string, string> = {
    "style-profile": "提炼文风机制",
    "style-prompt-task-file": "准备约束任务",
    "style-prompt-agent-task": "撰写文风约束",
    "style-prompt-quality": "校准约束质量",
    "style-eval-setup": "核对隔离评测",
    "style-eval-task-file": "准备盲测",
    "style-eval-agent-task": "生成盲测样本",
    "style-eval-score-file": "计算评测结果",
    "style-eval-revision": "根据证据修订",
    "style-eval-readiness": "确认评测门禁",
    "style-review-task-file": "准备独立审查",
    "style-review-agent-task": "执行独立审查",
    "style-review-readiness": "确认审查结论",
    "style-version-build": "固化不可变版本",
  };
  return labels[value] || "推进文风工程";
}

function statusLabel(value: string): string {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "正在执行",
    stopping: "正在停止",
    complete: "本步完成",
    route_ready: "工程完成",
    waiting_writeback: "等待写回确认",
    waiting_human: "等待人工决定",
    waiting_host_agent: "等待 Agent 连接",
    failed: "执行失败",
    runtime_failed: "Agent 运行失败",
    core_command_failed: "确定性步骤失败",
    cancelled: "已取消",
  };
  return labels[value] || "等待开始";
}

function statusMessage(value: string): string {
  if (value === "queued") return "任务已经进入正式队列。";
  if (value === "running") return "Agent 正在依据当前任务包工作。";
  if (value === "complete") return "这一步已通过门禁，可以领取下一步。";
  if (value === "waiting_writeback") return "候选成果已经通过预检，正式项目尚未改变。";
  if (value.includes("failed")) return "这一步没有完成，可保留上下文后受控重试。";
  return "文风工程会在这里显示真实状态。";
}

function eventLabel(event: string): string {
  const labels: Record<string, string> = {
    "task.opened": "已读取正式任务包",
    "sandbox.prepared": "隔离工作区已就绪",
    "core.command_started": "正在执行确定性步骤",
    "core.command_completed": "确定性步骤已返回",
    "runner.process.started": "Agent 进程已连接",
    "runner.session.started": "Agent 会话已开始",
    "runner.first_event": "已经收到首个输出",
    "validation.started": "正在核对候选成果",
    "validation.failed": "预检要求修订",
    "repair.started": "正在同会话修订",
    "validation.passed": "候选成果已通过检查",
    "file.imported": "成果已写入正式项目",
  };
  return labels[event] || (event.endsWith("completed") ? "当前动作已完成" : "任务状态已更新");
}
</script>

<template>
  <section class="style-engineering-console" :data-status="job?.status || 'idle'">
    <header>
      <div class="style-engineering-title">
        <span class="style-engineering-pulse"><Activity :size="16" /></span>
        <span><small>Formal style runtime</small><strong>{{ job ? statusLabel(job.status) : "形成可挂载文风" }}</strong></span>
      </div>
      <div class="style-engineering-current">
        <span>{{ task ? stateLabel(task.current_state) : selectedVersion ? stateLabel(selectedVersion.state) : "尚未启动" }}</span>
        <button :title="expanded ? '收起文风工程控制台' : '展开文风工程控制台'" @click="expanded = !expanded">
          <ChevronUp v-if="expanded" :size="15" /><ChevronDown v-else :size="15" />
        </button>
      </div>
    </header>

    <div v-if="expanded" class="style-engineering-body">
      <section v-if="!job" class="style-engineering-setup">
        <div class="style-engineering-fields">
          <label>
            <span>作者资料</span>
            <select v-model="authorId">
              <option v-for="item in authors" :key="item.author_id" :value="item.author_id">{{ item.name }}</option>
            </select>
          </label>
          <label><span>文风名称</span><input v-model="displayName" placeholder="例如：克制而有余波的叙事" /></label>
          <label><span>版本短名</span><input v-model="profileId" placeholder="例如：restrained-prose" @input="profileIdEdited = true; setupError = ''" /><small>已自动生成，也可改为小写字母、数字和短横线</small></label>
        </div>

        <div class="style-source-partition">
          <header><span><Layers3 :size="14" />分配学习与隔离评测文本</span><small>训练集与评测集不得重叠</small></header>
          <article v-for="source in sources" :key="source.key">
            <span><strong>{{ source.filename }}</strong><small>{{ source.work_title }} · {{ source.character_count }} 字</small></span>
            <select v-model="sourceRoles[source.key]" :aria-label="`${source.filename} 的用途`">
              <option value="training">用于学习</option>
              <option value="holdout">仅用于隔离评测</option>
              <option value="unused">本次不使用</option>
            </select>
          </article>
          <div v-if="sources.length < 2" class="style-partition-warning">
            <CircleAlert :size="15" />至少需要两份合法来源，才能把学习文本与隔离评测文本分开。
          </div>
        </div>

        <footer>
          <span :class="{ danger: Boolean(setupError) }"><CircleAlert v-if="setupError" :size="14" /><Beaker v-else :size="14" />{{ setupError || `${trainingSources.length} 份学习 · ${holdoutSources.length} 份隔离评测` }}</span>
          <button class="primary" :disabled="busy" @click="startCompilation">
            <Play :size="14" />开始正式工程
          </button>
        </footer>
      </section>

      <section v-else class="style-engineering-live">
        <div class="style-engineering-signal" :data-active="active">
          <RefreshCw v-if="active" :size="22" />
          <CheckCircle2 v-else-if="job.status === 'complete' || job.status === 'route_ready'" :size="22" />
          <CirclePause v-else :size="22" />
        </div>
        <div class="style-engineering-status">
          <span>{{ statusLabel(job.status) }}</span>
          <strong>{{ task ? stateLabel(task.current_state) : "文风工程任务" }}</strong>
          <p>{{ jobMessage }}</p>
          <small v-if="streamError">{{ streamError }}</small>
        </div>
        <ol v-if="visibleEvents.length" class="style-engineering-events" aria-label="最近任务状态">
          <li v-for="event in visibleEvents" :key="`${event.sequence}-${event.event}`">
            <i></i><span><strong>{{ eventLabel(event.event) }}</strong><small>{{ event.at ? new Date(event.at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : "刚刚" }}</small></span>
          </li>
        </ol>
        <div class="style-engineering-actions">
          <button v-if="active" :disabled="busy" title="在安全节点停止任务" @click="emit('stop')"><Square :size="13" />停止</button>
          <template v-else-if="job.status === 'waiting_writeback'">
            <button :disabled="busy" @click="emit('rejectWriteback', '退回候选成果，保留正式项目不变。')"><RotateCcw :size="13" />退回</button>
            <button class="primary" :disabled="busy" @click="emit('approveWriteback')"><ShieldCheck :size="13" />确认写回</button>
          </template>
          <button v-else-if="job.status.includes('failed') || job.status === 'waiting_host_agent'" :disabled="busy" @click="emit('retry')"><RefreshCw :size="13" />保留上下文重试</button>
          <button v-else-if="canContinue" class="primary" :disabled="busy" @click="continueCurrent">
            <ArrowRight :size="13" />{{ buildReady ? "固化不可变版本" : "继续下一阶段" }}
          </button>
        </div>
      </section>
    </div>

    <button v-else class="style-engineering-collapsed" @click="expanded = true">
      <Beaker :size="15" />
      <span>{{ selectedVersion ? "继续完善当前文风证据链" : "选择学习文本和隔离评测文本" }}</span>
      <ArrowRight :size="14" />
    </button>
  </section>
</template>
