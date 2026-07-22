<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { Activity, CircleAlert, RefreshCw, Save, Waves } from "lucide-vue-next";
import { api, query } from "@/services/api";
import { useAppStore } from "@/stores/app";

const props = defineProps<{ compact?: boolean }>();

interface TensionCurve { entry: number; peak: number; exit: number }
type RhythmProfileId = "layered" | "balanced" | "pulse" | "contemplative";
interface BookProfile {
  profile_id: RhythmProfileId;
  arc: { opening: number; ascent: number; midpoint: number; crisis: number; finale: number };
  breathing_interval: number;
  set_piece_ratio: number;
  narrative_distance: "balanced" | "varied" | "close_varied" | "observant";
  ending_policy: "varied" | "momentum" | "afterglow" | "quiet";
  directive: string;
}
interface BookMacro {
  expected_curve: number[];
  actual_curve: number[];
  chapter_ids: string[];
  scene_count: number;
  set_piece_count: number;
  set_piece_ratio: number;
  issues: Array<{ code: string; severity: string; message: string; scene_ids: string[] }>;
}
interface RhythmEntry {
  scene_id: string;
  volume_id: string;
  chapter_id: string;
  title: string;
  pace: string;
  rhythm_role: string;
  scene_function: string[];
  tension_curve: TensionCurve;
  detail_level: "summary" | "lean" | "standard" | "expanded" | "set_piece";
  word_count_target: number;
  timeline_order: number;
  story_time: string;
  spatial_time_gap_before: number;
  source: string;
}
interface RhythmPlan {
  revision: number;
  digest: string;
  entries: RhythmEntry[];
  chapters: Record<string, { status: string; issues: Array<{ code: string; severity: string; message: string; scene_ids: string[] }> }>;
  volumes: Record<string, { status: string; issues: Array<{ code: string; severity: string; message: string; scene_ids: string[] }> }>;
  book: { status: string; issues: Array<{ code: string; severity: string; message: string; scene_ids: string[] }>; macro?: BookMacro };
  book_profile: BookProfile;
}

const PROFILE_PRESETS: Record<RhythmProfileId, Omit<BookProfile, "profile_id" | "directive">> = {
  layered: { arc: { opening: 2, ascent: 3, midpoint: 4, crisis: 3, finale: 5 }, breathing_interval: 3, set_piece_ratio: 18, narrative_distance: "varied", ending_policy: "varied" },
  balanced: { arc: { opening: 2, ascent: 3, midpoint: 4, crisis: 4, finale: 5 }, breathing_interval: 2, set_piece_ratio: 20, narrative_distance: "balanced", ending_policy: "varied" },
  pulse: { arc: { opening: 3, ascent: 4, midpoint: 3, crisis: 5, finale: 5 }, breathing_interval: 2, set_piece_ratio: 26, narrative_distance: "close_varied", ending_policy: "momentum" },
  contemplative: { arc: { opening: 2, ascent: 2, midpoint: 4, crisis: 3, finale: 4 }, breathing_interval: 4, set_piece_ratio: 14, narrative_distance: "observant", ending_policy: "afterglow" },
};

const store = useAppStore();
const plan = ref<RhythmPlan | null>(null);
const chapter = ref("");
const selectedId = ref("");
const workspace = ref<"book" | "chapter">("book");
const saving = ref(false);
const message = ref("");

const chapters = computed(() => [...new Set((plan.value?.entries || []).map((entry) => entry.chapter_id))]);
const entries = computed(() => (plan.value?.entries || []).filter((entry) => entry.chapter_id === chapter.value));
const selected = computed(() => entries.value.find((entry) => entry.scene_id === selectedId.value) || entries.value[0] || null);
const bookStats = computed(() => chapters.value.map((chapterId) => {
  const chapterEntries = (plan.value?.entries || []).filter((entry) => entry.chapter_id === chapterId);
  const target = chapterEntries.reduce((sum, entry) => sum + Number(entry.word_count_target || 0), 0);
  const peak = chapterEntries.length ? Math.max(...chapterEntries.map((entry) => Number(entry.tension_curve.peak || 0))) : 0;
  const setPieces = chapterEntries.filter((entry) => entry.detail_level === "set_piece").length;
  return { chapterId, volumeId: chapterEntries[0]?.volume_id || "unassigned", sceneCount: chapterEntries.length, target, peak, setPieces };
}));
const bookTarget = computed(() => bookStats.value.reduce((sum, item) => sum + item.target, 0));
const volumeStats = computed(() => {
  const grouped = new Map<string, { volumeId: string; chapterCount: number; sceneCount: number; target: number; peak: number; setPieces: number }>();
  bookStats.value.forEach((item) => {
    const existing = grouped.get(item.volumeId) || { volumeId: item.volumeId, chapterCount: 0, sceneCount: 0, target: 0, peak: 0, setPieces: 0 };
    existing.chapterCount += 1;
    existing.sceneCount += item.sceneCount;
    existing.target += item.target;
    existing.peak = Math.max(existing.peak, item.peak);
    existing.setPieces += item.setPieces;
    grouped.set(item.volumeId, existing);
  });
  return [...grouped.values()];
});
const bookRiskCount = computed(() => plan.value?.book?.issues?.length || 0);
const bookProfile = computed(() => plan.value?.book_profile || null);
const bookMacro = computed(() => plan.value?.book?.macro || null);
const bookExpectedCurve = computed(() => bookMacro.value?.expected_curve || interpolateArc(bookProfile.value?.arc, bookStats.value.length));
const bookActualCurve = computed(() => bookMacro.value?.actual_curve || bookStats.value.map((item) => item.peak));
const macroIssues = computed(() => bookMacro.value?.issues || []);
const chartPoints = computed(() => {
  const values: string[] = [];
  const count = Math.max(1, entries.value.length * 3 - 1);
  entries.value.forEach((entry, sceneIndex) => {
    [entry.tension_curve.entry, entry.tension_curve.peak, entry.tension_curve.exit].forEach((value, pointIndex) => {
      const index = sceneIndex * 3 + pointIndex;
      const x = 34 + (index / count) * 732;
      const y = 184 - (Math.max(1, Math.min(5, Number(value))) - 1) * 35;
      values.push(`${x},${y}`);
    });
  });
  return values.join(" ");
});
const bookExpectedPoints = computed(() => curvePoints(bookExpectedCurve.value, 770, 38, 176));
const bookActualPoints = computed(() => curvePoints(bookActualCurve.value, 770, 38, 176));
const localRisks = computed(() => {
  const items = entries.value;
  const risks: string[] = [];
  for (let start = 0; start <= items.length - 3; start += 1) {
    const run = items.slice(start, start + 3);
    if (run.every((entry) => entry.pace === run[0].pace)) risks.push(`${run[0].scene_id} 至 ${run[2].scene_id} 连续采用同一种速度。`);
    if (run.every((entry) => entry.tension_curve.peak >= 4 && entry.tension_curve.exit >= 3)) risks.push(`${run[0].scene_id} 至 ${run[2].scene_id} 持续高压，缺少回落。`);
  }
  if (items.length >= 3) {
    const peaks = items.map((entry) => entry.tension_curve.peak);
    if (Math.max(...peaks) - Math.min(...peaks) <= 1) risks.push("本章峰值停留在狭窄区间，曲线容易显得平均。 ");
  }
  return [...new Set(risks)];
});

watch(chapter, () => { selectedId.value = entries.value[0]?.scene_id || ""; });
onMounted(() => void load());

async function load(): Promise<void> {
  if (!store.currentProjectPath) return;
  const result = await api<{ plan: RhythmPlan }>(`/project/rhythm-plan?${query({ project_root: store.currentProjectPath })}`);
  plan.value = result.plan;
  plan.value.book_profile = normalizeProfile(plan.value.book_profile);
  chapter.value = chapters.value.includes(chapter.value) ? chapter.value : chapters.value[0] || "";
  selectedId.value = entries.value[0]?.scene_id || "";
}

async function save(): Promise<void> {
  if (!store.currentProjectPath || !plan.value || saving.value) return;
  saving.value = true;
  message.value = "";
  try {
    const result = await api<{ plan: RhythmPlan }>("/project/rhythm-plan", {
      method: "PUT",
      body: JSON.stringify({ project_root: store.currentProjectPath, entries: plan.value.entries, book_profile: plan.value.book_profile }),
    });
    plan.value = result.plan;
    plan.value.book_profile = normalizeProfile(plan.value.book_profile);
    message.value = "全书曲线与场景节奏已进入正式创作链路；现有候选需要按新曲线重新审查。";
    await store.refreshWorkspace();
  } finally {
    saving.value = false;
  }
}

function normalizeProfile(value: BookProfile | undefined): BookProfile {
  const source = value || ({} as BookProfile);
  const id = (Object.prototype.hasOwnProperty.call(PROFILE_PRESETS, source.profile_id) ? source.profile_id : "layered") as RhythmProfileId;
  const defaults = PROFILE_PRESETS[id];
  return {
    profile_id: id,
    arc: {
      opening: tension(source.arc?.opening, defaults.arc.opening),
      ascent: tension(source.arc?.ascent, defaults.arc.ascent),
      midpoint: tension(source.arc?.midpoint, defaults.arc.midpoint),
      crisis: tension(source.arc?.crisis, defaults.arc.crisis),
      finale: tension(source.arc?.finale, defaults.arc.finale),
    },
    breathing_interval: bounded(source.breathing_interval, defaults.breathing_interval, 1, 8),
    set_piece_ratio: bounded(source.set_piece_ratio, defaults.set_piece_ratio, 5, 45),
    narrative_distance: ["balanced", "varied", "close_varied", "observant"].includes(source.narrative_distance) ? source.narrative_distance : defaults.narrative_distance,
    ending_policy: ["varied", "momentum", "afterglow", "quiet"].includes(source.ending_policy) ? source.ending_policy : defaults.ending_policy,
    directive: String(source.directive || "").slice(0, 500),
  };
}

function applyBookProfile(profileId: RhythmProfileId): void {
  if (!plan.value) return;
  const preset = PROFILE_PRESETS[profileId];
  plan.value.book_profile = {
    profile_id: profileId,
    arc: { ...preset.arc },
    breathing_interval: preset.breathing_interval,
    set_piece_ratio: preset.set_piece_ratio,
    narrative_distance: preset.narrative_distance,
    ending_policy: preset.ending_policy,
    directive: plan.value.book_profile?.directive || "",
  };
}

function openChapter(chapterId: string): void {
  chapter.value = chapterId;
  workspace.value = "chapter";
}

function curvePoints(values: number[], width: number, left: number, bottom: number): string {
  if (!values.length) return "";
  const span = Math.max(1, values.length - 1);
  return values.map((value, index) => `${left + (index / span) * width},${bottom - (tension(value, 3) - 1) * 34}`).join(" ");
}

function interpolateArc(arc: BookProfile["arc"] | undefined, count: number): number[] {
  const anchors = [arc?.opening || 2, arc?.ascent || 3, arc?.midpoint || 4, arc?.crisis || 3, arc?.finale || 5];
  if (!count) return [];
  if (count === 1) return [anchors[0]];
  return Array.from({ length: count }, (_, index) => {
    const scaled = (index / (count - 1)) * (anchors.length - 1);
    const left = Math.floor(scaled);
    const right = Math.min(anchors.length - 1, left + 1);
    return tension(Math.round(anchors[left] + (anchors[right] - anchors[left]) * (scaled - left)), 3);
  });
}

function tension(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(1, Math.min(5, Math.round(parsed))) : fallback;
}

function bounded(value: unknown, fallback: number, min: number, max: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(min, Math.min(max, Math.round(parsed))) : fallback;
}
</script>

<template>
  <section class="rhythm-editor" :class="{ compact: props.compact }" v-if="plan">
    <header class="rhythm-editor-heading">
      <div><span class="eyebrow">叙事节奏曲线</span><h2>让章节有蓄势、峰值与呼吸</h2><p>数字是创作锚点，不是机械配方。正文仍要用人物选择、信息差和代价真正完成张力变化。</p></div>
      <div class="rhythm-editor-tools"><label v-if="workspace === 'chapter'">查看章节<select v-model="chapter"><option v-for="item in chapters" :key="item" :value="item">{{ item }}</option></select></label><button class="icon-button" title="重新读取节奏计划" @click="load"><RefreshCw :size="16" /></button></div>
    </header>

    <nav class="rhythm-workspace-switch" aria-label="节奏管理层级">
      <button :class="{ active: workspace === 'book' }" @click="workspace = 'book'"><Waves :size="14" />全书曲线</button>
      <button :class="{ active: workspace === 'chapter' }" @click="workspace = 'chapter'"><Activity :size="14" />章节细调</button>
      <span>保存后会进入后续生成、审查与章节工作台。</span>
    </nav>

    <nav v-if="bookStats.length" class="rhythm-book-overview" aria-label="全书节奏概览">
      <button class="rhythm-book-total" type="button" :class="{ active: workspace === 'book' }" @click="workspace = 'book'"><span>全书编排</span><strong>{{ bookStats.reduce((sum, item) => sum + item.sceneCount, 0) }} 场</strong><small>{{ bookTarget ? `${bookTarget.toLocaleString('zh-CN')} 字目标` : '待补齐字数目标' }}{{ bookRiskCount ? ` · ${bookRiskCount} 项全书风险` : '' }}</small></button>
      <span v-for="volume in volumeStats" :key="volume.volumeId" class="rhythm-volume-marker"><b>{{ volume.volumeId === 'unassigned' ? '未分卷' : volume.volumeId }}</b><small>{{ volume.chapterCount }} 章 · {{ volume.sceneCount }} 场 · {{ volume.setPieces }} 重点场</small></span>
      <button v-for="item in bookStats" :key="item.chapterId" type="button" :class="{ active: item.chapterId === chapter && workspace === 'chapter' }" @click="openChapter(item.chapterId)"><span>{{ item.chapterId }}</span><i :style="{ height: `${Math.max(12, item.peak * 18)}%` }"></i><small>{{ item.sceneCount }} 场 · {{ item.setPieces }} 重点</small></button>
    </nav>

    <section v-if="workspace === 'book' && bookProfile" class="rhythm-macro-workbench">
      <header class="rhythm-macro-heading">
        <div><span>全书节奏控制器</span><h3>先决定整部作品怎样呼吸</h3><p>这条意图曲线会写入每一场的正式节奏合同。它约束的是起伏、详略与收束方式，不代替人物和情节的具体判断。</p></div>
        <div class="rhythm-macro-facts"><strong>{{ bookMacro?.scene_count || bookStats.reduce((sum, item) => sum + item.sceneCount, 0) }} 场</strong><small>{{ bookMacro?.set_piece_count || 0 }} 个重点场</small></div>
      </header>

      <div class="rhythm-profile-pills" role="group" aria-label="全书叙事节奏预设">
        <button v-for="(preset, id) in PROFILE_PRESETS" :key="id" :class="{ active: bookProfile.profile_id === id }" @click="applyBookProfile(id as RhythmProfileId)"><strong>{{ ({ layered: '层层蓄压', balanced: '均衡推进', pulse: '强起伏脉冲', contemplative: '沉静回响' } as Record<string, string>)[id] }}</strong><small>{{ ({ layered: '渐进抬升，保留余波', balanced: '稳定升级，高潮清晰', pulse: '大起伏，推进感更强', contemplative: '留白更多，回响更长' } as Record<string, string>)[id] }}</small></button>
      </div>

      <div class="rhythm-macro-grid">
        <div class="rhythm-book-chart">
          <div class="rhythm-book-chart-heading"><span>章节张力走向</span><small><i></i>意图曲线 <b></b>当前分布</small></div>
          <svg viewBox="0 0 860 202" preserveAspectRatio="none" role="img" aria-label="全书目标和实际章节张力曲线">
            <line v-for="level in [1,2,3,4,5]" :key="level" x1="30" x2="822" :y1="176 - (level - 1) * 34" :y2="176 - (level - 1) * 34" />
            <polyline class="intent" :points="bookExpectedPoints" />
            <polyline class="actual" :points="bookActualPoints" />
            <circle v-for="(value, index) in bookActualCurve" :key="`actual-${index}`" :cx="38 + (index / Math.max(1, bookActualCurve.length - 1)) * 770" :cy="176 - (Math.max(1, Math.min(5, value)) - 1) * 34" r="4" />
          </svg>
          <div class="rhythm-phase-labels"><span>开端</span><span>蓄势</span><span>中段</span><span>危机</span><span>收束</span></div>
          <p v-if="macroIssues.length" class="rhythm-macro-warning"><CircleAlert :size="14" />{{ macroIssues[0].message }}</p>
          <p v-else class="rhythm-macro-clean"><Activity :size="14" />当前章节分布与全书意图可以被一起检查。</p>
        </div>

        <aside class="rhythm-macro-controls">
          <label v-for="(label, key) in ({ opening: '开端', ascent: '蓄势', midpoint: '中段', crisis: '危机', finale: '收束' } as Record<string, string>)" :key="key"><span>{{ label }}<small>{{ bookProfile.arc[key as keyof BookProfile['arc']] }}</small></span><input v-model.number="bookProfile.arc[key as keyof BookProfile['arc']]" type="range" min="1" max="5" /></label>
          <div class="rhythm-macro-fields">
            <label>连续高压后留白<input v-model.number="bookProfile.breathing_interval" type="number" min="1" max="8" /><small>场</small></label>
            <label>重点场目标<input v-model.number="bookProfile.set_piece_ratio" type="number" min="5" max="45" /><small>%</small></label>
          </div>
          <label>叙述距离<select v-model="bookProfile.narrative_distance"><option value="varied">随场景切换远近</option><option value="balanced">远近均衡</option><option value="close_varied">贴近人物，关键处拉远</option><option value="observant">观察性叙述</option></select></label>
          <label>章节收束<select v-model="bookProfile.ending_policy"><option value="varied">不重复同一种章末</option><option value="momentum">行动启动与未竟压力</option><option value="afterglow">情绪余波与信息落点</option><option value="quiet">静默与留白</option></select></label>
        </aside>
      </div>

      <label class="rhythm-book-directive"><span>这部作品的节奏补充</span><textarea v-model.trim="bookProfile.directive" rows="2" maxlength="500" placeholder="例如：前半部不要急着解释谜团，每次高压之后至少给人物一个看似平静但关系变形的场景。"></textarea><small>它会原样进入后续场景的节奏合同，适合写你不想被预设覆盖的文学判断。</small></label>
    </section>

    <div v-else-if="entries.length" class="rhythm-editor-body">
      <div class="rhythm-chart">
        <div class="rhythm-chart-scale"><span v-for="level in [5,4,3,2,1]" :key="level">{{ level }}</span></div>
        <svg viewBox="0 0 800 210" preserveAspectRatio="none" role="img" aria-label="本章场景张力曲线">
          <line v-for="level in [1,2,3,4,5]" :key="level" x1="24" x2="776" :y1="184 - (level - 1) * 35" :y2="184 - (level - 1) * 35" />
          <polyline :points="chartPoints" />
          <template v-for="(entry, sceneIndex) in entries" :key="entry.scene_id">
            <circle v-for="(value, pointIndex) in [entry.tension_curve.entry, entry.tension_curve.peak, entry.tension_curve.exit]" :key="pointIndex" :cx="34 + ((sceneIndex * 3 + pointIndex) / Math.max(1, entries.length * 3 - 1)) * 732" :cy="184 - (value - 1) * 35" :class="{ peak: pointIndex === 1, selected: entry.scene_id === selectedId }" r="4" />
          </template>
        </svg>
        <div class="rhythm-scene-strip"><button v-for="entry in entries" :key="entry.scene_id" :class="{ active: entry.scene_id === selectedId }" @click="selectedId = entry.scene_id"><span>{{ entry.scene_id }}</span><strong>{{ entry.title }}</strong></button></div>
      </div>

      <aside v-if="selected" class="rhythm-scene-editor">
        <header><span><Waves :size="16" /></span><div><small>当前场景</small><h3>{{ selected.title }}</h3><p>{{ selected.scene_id }} · {{ selected.source === 'rhythm-plan' ? '用户节奏计划' : '现有场景契约' }}</p></div></header>
        <div class="rhythm-selectors">
          <label>节奏角色<select v-model="selected.rhythm_role"><option value="setup">铺垫</option><option value="transition">过场</option><option value="information">信息</option><option value="emotion">情绪</option><option value="conflict">冲突</option><option value="action">行动</option><option value="turn">转折</option><option value="aftermath">余波</option><option value="mixed">混合</option></select></label>
          <label>推进速度<select v-model="selected.pace"><option value="slow">慢</option><option value="slow_to_fast">由慢到快</option><option value="balanced">均衡</option><option value="fast_to_slow">由快到慢</option><option value="fast">快</option></select></label>
          <label>详略等级<select v-model="selected.detail_level"><option value="summary">概述</option><option value="lean">简写</option><option value="standard">标准</option><option value="expanded">展开</option><option value="set_piece">重点场</option></select></label>
        </div>
        <div class="rhythm-temporal-control">
          <div><span>故事时间</span><strong>{{ selected.story_time || (selected.timeline_order ? `时间序 ${selected.timeline_order}` : "尚未标注") }}</strong><small>读取场景的故事时间；时间跳跃会自动拉开章节间距，闪回仍保持阅读顺序。</small></div>
          <label>本场前间距<input v-model.number="selected.spatial_time_gap_before" type="number" min="0" max="3.2" step="0.1" /><small>0 为自动；0.6–3.2 仅调整星图距离，不改写正文时间。</small></label>
        </div>
        <label class="rhythm-function">场景功能<input :value="selected.scene_function.join('；')" placeholder="推进主线；改变关系" @input="selected.scene_function = ($event.target as HTMLInputElement).value.split(/[；;]/).map(v => v.trim()).filter(Boolean)" /><small>目标 {{ Number(selected.word_count_target || 0).toLocaleString('zh-CN') || '待设定' }} 字；详略会作为生成和审查约束，而不是单纯拉长句子。</small></label>
        <div class="rhythm-levels">
          <label><span>入场张力<small>接住上一场</small></span><input v-model.number="selected.tension_curve.entry" type="range" min="1" max="5" /><output>{{ selected.tension_curve.entry }}</output></label>
          <label><span>场内峰值<small>选择与代价</small></span><input v-model.number="selected.tension_curve.peak" type="range" min="1" max="5" /><output>{{ selected.tension_curve.peak }}</output></label>
          <label><span>出场张力<small>交给下一场</small></span><input v-model.number="selected.tension_curve.exit" type="range" min="1" max="5" /><output>{{ selected.tension_curve.exit }}</output></label>
        </div>
      </aside>
    </div>

    <div v-if="entries.length" class="rhythm-editor-footer">
      <div class="rhythm-risk" :class="{ clean: !localRisks.length }"><Activity v-if="!localRisks.length" :size="16" /><CircleAlert v-else :size="16" /><span><strong>{{ localRisks.length ? `${localRisks.length} 项曲线风险` : '曲线具有可辨识变化' }}</strong><small>{{ localRisks[0] || '章节中存在蓄势、峰值与回落。' }}</small></span></div>
      <p>{{ message || `第 ${plan.revision || 0} 版 · 保存后影响未来候选，旧候选需要重新审查。` }}</p>
      <button class="primary-button" :disabled="saving" @click="save"><Save :size="16" />{{ saving ? "正在保存" : "保存节奏计划" }}</button>
    </div>
    <div v-else class="rhythm-empty"><Waves :size="24" /><strong>还没有可规划的场景</strong><p>先完成章节与场景库存，节奏曲线会自动出现在这里。</p></div>
  </section>
</template>
