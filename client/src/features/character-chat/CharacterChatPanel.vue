<script setup lang="ts">
import { onMounted, ref, watch, nextTick } from "vue";
import { characterChatClient as client } from "./services/characterChatClient";
import type { CharacterCard, CharacterChatSession, CharacterChatSetup, KnownAttachment } from "./types";
import "./characterChat.css";

const props = defineProps<{ projectRoot: string; initialTarget?: string }>();
const emit = defineEmits<{ close: [] }>();
const setup = ref<CharacterChatSetup | null>(null);
const session = ref<CharacterChatSession | null>(null);
const sections = ref<Record<string, string>>({});
const target = ref(props.initialTarget || "");
const context = ref("");
const sourceRefs = ref("");
const sourcePath = ref("");
const startLine = ref<number | null>(null);
const endLine = ref<number | null>(null);
const attachments = ref<KnownAttachment[]>([]);
const entries = ref<Array<{ path: string; status: string }>>([]);
const cursor = ref<number | null>(0);
const preview = ref("");
const previewOffset = ref<number | null>(null);
const message = ref("");
const busy = ref(false);
const error = ref("");
const selectedCard = ref("");
const showEditor = ref(false);
const transcript = ref<HTMLElement | null>(null);
const panel = ref<HTMLElement | null>(null);
let generation = 0;
const sourceLabels: Record<string,string> = { canon:'作品设定', character_archive:'人物档案', planning:'创作规划',
  scene_prose:'已提交正文', mixed_continuity:'连续性记录', user_direction:'作者方向', archive_reference:'参考资料' };
const labels: Record<string, string> = {
  PERSONA_LOAD: "人格加载", CORE_IDENTITY: "核心身份", PERSONALITY_LAYERS: "人格层次",
  PRIVATE_BEHAVIOR_MODES: "私下行为模式", INTERACTION_LIBRARY: "互动库",
  SUMMARY_PRIVATE: "私下面貌小结", SELF_IDENTITY: "自我认同", SELF_CLAIM_RULES: "自称习惯",
  PERSONALITY_CORE: "人格核心", PERSONALITY_PUBLIC: "公开表现", PERSONALITY_PRIVATE: "私密表现",
  PERSONALITY_CONTRADICTION: "人格矛盾", PERSONALITY_SUMMARY: "人格总结",
  SELF_CLAIM_EXAMPLES: "自称例句", FOOD_PREFERENCE: "食物偏好", REAL_SELF_BEHAVIOR: "真实自我行为",
};

async function action(task: (current:()=>boolean, root:string) => Promise<void>): Promise<void> {
  const epoch = generation, root=props.projectRoot;
  const current=()=>epoch===generation && root===props.projectRoot;
  busy.value = true;
  error.value = "";
  try { await task(current,root); }
  catch (cause) { if(current()) error.value = cause instanceof Error ? cause.message : String(cause); }
  finally { if(current()) busy.value = false; }
}
async function load(): Promise<void> {
  await action(async (current,root) => {
    const loaded = await client.setup(root);
    if(!current()) return;
    setup.value = loaded;
    sections.value = Object.fromEntries(setup.value.sections.map((key) => [key, ""]));
    entries.value = [];
    cursor.value = 0;
    await moreArchives(current,root);
  });
}
async function moreArchives(current:()=>boolean, root:string): Promise<void> {
  if (cursor.value === null) return;
  const page = await client.archive(root, cursor.value);
  if(!current()) return;
  entries.value.push(...page.entries);
  cursor.value = page.next_cursor;
}
function chooseCard(): void {
  const found = setup.value?.cards.find((item) => item.digest === selectedCard.value);
  if (!found) { showEditor.value = true; return; }
  target.value = found.card.target;
  sections.value = { ...found.card.sections };
  sourceRefs.value = found.card.source_refs.join("\n");
}
function attach(): void {
  if (!sourcePath.value) return;
  attachments.value.push({ path: sourcePath.value, start_line: startLine.value || null,
    end_line: endLine.value || null, knowledge: "known" });
}
async function showSource(more = false): Promise<void> {
  await action(async (current,root) => {
    const page = await client.readArchive(root, sourcePath.value, more ? previewOffset.value || 0 : 0);
    if(!current()) return;
    preview.value = more ? preview.value + page.content : page.content;
    previewOffset.value = page.next_offset;
  });
}
async function create(): Promise<void> {
  await action(async (current,root) => {
    const card: CharacterCard = { schema: "arcvellum/actor-character-card/v1", target: target.value,
      sections: { ...sections.value }, source_refs: sourceRefs.value.split("\n").map((s) => s.trim()).filter(Boolean),
      notes: "" };
    const created = await client.create(root, card, attachments.value, context.value);
    if(!current()) return;
    session.value = created.session;
    const loaded = await client.setup(root);
    if(current()) setup.value = loaded;
  });
}
async function draftCard(): Promise<void> {
  await action(async (current,root) => {
    const draft = await client.draftCard(root, target.value, attachments.value, context.value);
    if(!current()) return;
    sections.value = { ...draft.card.sections };
    sourceRefs.value = draft.card.source_refs.join("\n");
    selectedCard.value = "";
    showEditor.value = true;
  });
}
async function resume(sessionId: string): Promise<void> {
  await action(async (current,root) => { const loaded = await client.session(root, sessionId); if(current()) session.value=loaded.session; });
}
async function send(): Promise<void> {
  if (!session.value || !message.value.trim()) return;
  await action(async (current,root) => {
    const answered = await client.ask(root, session.value!.session_id, message.value);
    if(!current()) return;
    session.value=answered.session;
    message.value = "";
    await nextTick();
    transcript.value?.scrollTo({ top: transcript.value.scrollHeight, behavior: "smooth" });
  });
}
function trapFocus(event: KeyboardEvent): void {
  if (event.key !== "Tab") return;
  const nodes = panel.value?.querySelectorAll<HTMLElement>("button:not(:disabled), input, textarea, select, summary");
  if (!nodes?.length) return;
  const first = nodes[0], last = nodes[nodes.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
watch(() => props.projectRoot, () => {
  generation++; session.value=null; attachments.value=[]; setup.value=null;
  target.value=''; context.value=''; sourceRefs.value=''; selectedCard.value=''; sourcePath.value='';
  startLine.value=null; endLine.value=null; preview.value=''; previewOffset.value=null; message.value='';
  void load();
});
onMounted(async () => { panel.value?.focus(); await load(); });
</script>

<template>
  <Teleport to="body">
    <div class="character-chat-overlay" @keydown.esc="emit('close')">
      <section ref="panel" tabindex="-1" class="character-chat-panel" role="dialog" aria-modal="true"
        aria-labelledby="character-chat-title" @keydown="trapFocus">
        <header><div><small>PRIVATE CONVERSATION</small><h2 id="character-chat-title">与角色交谈</h2>
          <p>为这段对话单独加载角色卡、已知资料和场景。记录独立保存。</p></div>
          <button aria-label="关闭角色对话" @click="emit('close')">关闭</button></header>
        <p v-if="error" class="character-chat-error" role="alert">{{ error }}</p>
        <div class="character-chat-body">
          <aside>
            <h3>加载人物</h3>
            <label>主创已填写的角色卡
              <select v-model="selectedCard" :disabled="busy" @change="chooseCard">
                <option value="">手动填写角色卡</option>
                <option v-for="item in setup?.cards" :key="item.digest" :value="item.digest">
                  {{ item.card.target }} · {{ item.scene_id }}
                </option>
              </select>
            </label>
            <label>人物名<input v-model="target" :disabled="busy" /></label>
            <button @click="showEditor = !showEditor">{{ showEditor ? '收起角色卡' : '查看与编辑角色卡' }}</button>
            <div v-if="showEditor" class="character-card-fields">
              <label v-for="key in setup?.sections" :key="key">{{ labels[key] || key }}
                <textarea v-model="sections[key]" :disabled="busy" rows="3" />
              </label>
              <label>角色卡来源（每行一个）<textarea v-model="sourceRefs" :disabled="busy" rows="2" /></label>
            </div>
            <h3>角色已知资料</h3>
            <label>档案条目<select v-model="sourcePath" :disabled="busy" @change="preview = ''">
              <option value="">选择条目</option>
              <option v-for="item in entries" :key="item.path" :value="item.path">{{ item.path }} · {{ sourceLabels[item.status] || item.status }}</option>
            </select></label>
            <button v-if="cursor !== null" :disabled="busy" @click="action(moreArchives)">更多条目</button>
            <div class="character-chat-range"><label>起始行<input v-model.number="startLine" type="number" min="1" /></label>
              <label>结束行<input v-model.number="endLine" type="number" min="1" /></label></div>
            <small>两项留空挂整条；填写两项挂指定行段。</small>
            <div class="character-chat-buttons">
              <button :disabled="busy || !sourcePath" @click="showSource()">预览原文</button>
              <button :disabled="busy || !sourcePath" @click="attach">加入已知资料</button>
            </div>
            <pre v-if="preview" class="character-source-preview">{{ preview }}</pre>
            <button v-if="previewOffset !== null" :disabled="busy" @click="showSource(true)">继续读取</button>
            <ul class="character-attachments"><li v-for="(item, index) in attachments" :key="index">
              <span>{{ item.path }} · {{ item.start_line ? item.start_line + '–' + item.end_line : '完整条目' }}</span>
              <button :disabled="busy" :aria-label="'移除 ' + item.path" @click="attachments.splice(index, 1)">×</button>
            </li></ul>
            <label>这段对话的场景<textarea v-model="context" rows="4" :disabled="busy"
              placeholder="此刻在哪里，你以什么身份与角色交谈，刚刚发生了什么…" /></label>
            <small>写下你的名字、与角色的关系和发生时刻。例如：新来的维修工小陆，第一次来到食堂，在后门与许钉交谈。</small>
            <button :disabled="busy || !target" @click="draftCard">按已知资料生成本段角色卡</button>
            <button class="character-chat-primary" :disabled="busy || !target" @click="create">加载并开始新对话</button>
            <h3>已有对话</h3>
            <button v-for="item in setup?.sessions" :key="item.session_id" :disabled="busy"
              :class="{ selected: session?.session_id === item.session_id }" @click="resume(item.session_id)">
              {{ item.target }} · {{ new Date(item.updated_at).toLocaleString() }}
            </button>
          </aside>
          <main>
            <template v-if="session">
              <h3>{{ session.target }} <small>{{ session.turns.length }} / 16 轮</small></h3>
              <details><summary>本段加载的上下文与系统角色卡</summary><pre>{{ session.context }}</pre>
                <pre v-for="item in session.known_archive" :key="item.path">
{{ item.path }} · {{ item.line_range.join('–') }}
{{ item.content }}</pre><pre>{{ session.system_prompt }}</pre></details>
              <div ref="transcript" class="character-chat-transcript" aria-live="polite">
                <article v-for="(turn, index) in session.turns" :key="index">
                  <p class="character-chat-user"><b>你</b>{{ turn.message }}</p>
                  <p class="character-chat-answer"><b>{{ session.target }}</b>{{ turn.answer }}</p>
                </article>
                <p v-if="busy">正在等待回应…</p>
              </div>
              <form @submit.prevent="send"><label>对角色说<textarea v-model="message" rows="3"
                :disabled="busy || session.turns.length >= 16" /></label>
                <button class="character-chat-primary" :disabled="busy || !message.trim() || session.turns.length >= 16">
                  发送
                </button></form>
            </template>
            <div v-else class="character-chat-empty"><h3>给人物一个此刻</h3>
              <p>选择角色卡和他已知的资料，写下这段对话的场景，然后开始交谈。</p>
              <p v-if="setup && !setup.cards.length">主创生成的角色卡会显示在左侧。你也可以展开十六区块，填写自己的卡。</p>
            </div>
          </main>
        </div>
      </section>
    </div>
  </Teleport>
</template>

