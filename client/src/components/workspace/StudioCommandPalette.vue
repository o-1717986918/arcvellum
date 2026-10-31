<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { ArrowUpRight, Command, Search, X } from "lucide-vue-next";
import { projectAgentWorkspaces, type ProjectAgentWorkspaceId } from "@/workspaces/projectAgentWorkspaceRegistry";

interface StudioCommand { id: string; title: string; detail: string; kind: "workspace" | "session" | "conversation" | "new" | "orrery" }
const props = defineProps<{
  sessions: Array<{ session_id: string; title: string; project_root: string }>;
  projectLabels: Record<string, string>;
  hasProject: boolean;
}>();
const emit = defineEmits<{ close: []; workspace: [id: ProjectAgentWorkspaceId]; session: [id: string]; conversation: []; create: []; orrery: [] }>();
const dialog = ref<HTMLDialogElement | null>(null);
const query = ref("");
const selected = ref(0);
const opener = document.activeElement as HTMLElement | null;
const aliases: Record<string, string> = {
  reader: "阅读 小说 正文", archive: "人物 地点 世界 设定 资料", "character-chat": "人物 角色 对话",
  delivery: "下载 导出 docx markdown", settings: "模型 api key 密钥 外观 更新", projects: "新建 导入 切换作品",
};
const commands = computed<StudioCommand[]>(() => [
  { id: "conversation", kind: "conversation", title: "回到当前对话", detail: "继续刚才的想法" },
  { id: "new", kind: "new", title: "新对话", detail: "为一部作品展开新的讨论" },
  ...(props.hasProject ? [{ id: "orrery", kind: "orrery" as const, title: "进入星仪", detail: "收起界面，走进作品的叙事空间" }] : []),
  ...projectAgentWorkspaces.all().map(item => ({ id: item.id, kind: "workspace" as const, title: item.title,
    detail: item.requiresProject && !props.hasProject ? "先选择一部作品" : item.description })),
  ...props.sessions.map(item => ({ id: item.session_id, kind: "session" as const, title: item.title,
    detail: `会话 · ${props.projectLabels[item.project_root] || "作品库"}` })),
]);
const results = computed(() => {
  const terms = query.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return commands.value.filter(item => terms.every(term =>
    `${item.title} ${item.detail} ${aliases[item.id] || ""}`.toLocaleLowerCase().includes(term)));
});
watch(query, () => { selected.value = 0; });
onMounted(() => { dialog.value?.showModal(); });

function close(): void {
  dialog.value?.close();
  emit("close");
  void nextTick(() => { if (opener?.isConnected) opener.focus({ preventScroll: true }); });
}
function choose(item?: StudioCommand): void {
  if (!item) return;
  close();
  if (item.kind === "workspace") emit("workspace", item.id as ProjectAgentWorkspaceId);
  else if (item.kind === "session") emit("session", item.id);
  else if (item.kind === "conversation") emit("conversation");
  else if (item.kind === "new") emit("create");
  else emit("orrery");
}
function navigate(event: KeyboardEvent): void {
  if (event.isComposing) return;
  if (event.key === "Enter") { event.preventDefault(); choose(results.value[selected.value]); return; }
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const count = results.value.length;
  if (!count) return;
  if (event.key === "Home") selected.value = 0;
  else if (event.key === "End") selected.value = count - 1;
  else selected.value = (selected.value + (event.key === "ArrowDown" ? 1 : -1) + count) % count;
  void nextTick(() => dialog.value?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" }));
}
</script>

<template>
  <dialog ref="dialog" class="studio-command-dialog" aria-label="快速切换" @cancel.prevent="close" @click="($event.target === dialog) && close()">
    <div class="studio-command-body">
      <header><Search :size="21" /><input v-model="query" autofocus role="combobox" aria-label="搜索功能或会话" aria-autocomplete="list"
        aria-expanded="true" aria-controls="studio-command-results" :aria-activedescendant="results.length ? `studio-command-${selected}` : undefined"
        placeholder="想去哪里？搜索功能、作品或会话…" @keydown="navigate" /><button title="关闭快速切换" @click="close"><X :size="18" /></button></header>
      <div id="studio-command-results" class="studio-command-results" role="listbox" aria-label="功能与会话">
        <button v-for="(item, index) in results" :id="`studio-command-${index}`" :key="`${item.kind}:${item.id}`" role="option" tabindex="-1"
          :aria-selected="selected === index" @mousemove="selected = index" @click="choose(item)">
          <span class="studio-command-kind">{{ item.kind === 'session' ? '对话' : item.kind === 'workspace' ? '工具' : '工作台' }}</span>
          <span><strong>{{ item.title }}</strong><small>{{ item.detail }}</small></span><ArrowUpRight :size="16" />
        </button>
        <div v-if="!results.length" class="studio-command-empty"><Search :size="24" /><strong>没有找到「{{ query }}」</strong><p>试试“人物”“导出”“模型”，或作品的名字。</p><button @click="query = ''">查看全部功能</button></div>
      </div>
      <footer><span><Command :size="12" /> Ctrl / ⌘ K 随时打开</span><span>↑ ↓ 选择 · Enter 打开 · Esc 返回</span></footer>
    </div>
  </dialog>
</template>
