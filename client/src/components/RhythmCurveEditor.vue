<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { Activity, CircleAlert, RefreshCw, Save, Waves } from "lucide-vue-next";
import { api, query } from "@/services/api";
import { useAppStore } from "@/stores/app";

const props = defineProps<{ compact?: boolean }>();

interface TensionCurve { entry: number; peak: number; exit: number }
interface RhythmEntry {
  scene_id: string;
  chapter_id: string;
  title: string;
  pace: string;
  rhythm_role: string;
  scene_function: string[];
  tension_curve: TensionCurve;
  source: string;
}
interface RhythmPlan {
  revision: number;
  digest: string;
  entries: RhythmEntry[];
  chapters: Record<string, { status: string; issues: Array<{ code: string; severity: string; message: string; scene_ids: string[] }> }>;
}

const store = useAppStore();
const plan = ref<RhythmPlan | null>(null);
const chapter = ref("");
const selectedId = ref("");
const saving = ref(false);
const message = ref("");

const chapters = computed(() => [...new Set((plan.value?.entries || []).map((entry) => entry.chapter_id))]);
const entries = computed(() => (plan.value?.entries || []).filter((entry) => entry.chapter_id === chapter.value));
const selected = computed(() => entries.value.find((entry) => entry.scene_id === selectedId.value) || entries.value[0] || null);
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
      body: JSON.stringify({ project_root: store.currentProjectPath, entries: plan.value.entries }),
    });
    plan.value = result.plan;
    message.value = "节奏计划已进入正式创作链路；现有候选需要按新曲线重新审查。";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <section class="rhythm-editor" :class="{ compact: props.compact }" v-if="plan">
    <header class="rhythm-editor-heading">
      <div><span class="eyebrow">叙事节奏曲线</span><h2>让章节有蓄势、峰值与呼吸</h2><p>数字是创作锚点，不是机械配方。正文仍要用人物选择、信息差和代价真正完成张力变化。</p></div>
      <div class="rhythm-editor-tools"><label>查看章节<select v-model="chapter"><option v-for="item in chapters" :key="item" :value="item">{{ item }}</option></select></label><button class="icon-button" title="重新读取节奏计划" @click="load"><RefreshCw :size="16" /></button></div>
    </header>

    <div v-if="entries.length" class="rhythm-editor-body">
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
        </div>
        <label class="rhythm-function">场景功能<input :value="selected.scene_function.join('；')" placeholder="推进主线；改变关系" @input="selected.scene_function = ($event.target as HTMLInputElement).value.split(/[；;]/).map(v => v.trim()).filter(Boolean)" /></label>
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
