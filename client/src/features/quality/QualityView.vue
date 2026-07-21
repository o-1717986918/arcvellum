<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { CircleAlert, CircleCheck, FlaskConical, Plus, RefreshCw, Save, ShieldCheck, Sparkles, Trash2 } from "lucide-vue-next";
import { api } from "@/services/api";
import { useAppStore } from "@/stores/app";
import RhythmCurveEditor from "@/components/RhythmCurveEditor.vue";

const props = defineProps<{ instrument?: boolean }>();

type Mode = "off" | "note" | "blocking";
interface QualityException { rule: string; scope: string; reason: string; mode: Mode; expires_at: string }
interface QualityProfile {
  name: string;
  preset: string;
  revision: number;
  digest: string;
  thresholds: Record<string, number>;
  rule_modes: Record<string, Mode>;
  custom_banned_phrases: string[];
  preferred_habits: string[];
  exceptions: QualityException[];
  [key: string]: unknown;
}

const store = useAppStore();
const profile = ref<QualityProfile | null>(null);
const previewText = ref("灶上的鱼羹热了第三遍，她还没等到那个人回来。门外不是风声，而是有人停在台阶下。她嘴角微扬，仿佛命运的齿轮终于开始转动。");
const preview = ref<Record<string, any> | null>(null);
const previewScope = ref("");
const saving = ref(false);
const message = ref("");
const advanced = ref(false);
const instrumentTab = ref<"rhythm" | "language" | "preview" | "rules">("rhythm");

const rules = [
  ["mechanical-contrast-frame", "生硬对照", "拦住“不是……而是……”及其标点变体。"],
  ["contrast-evasion-frame", "换皮转折", "识别“看似……其实……”等同功能替换。"],
  ["plain-narration-banned-expression", "套话与器官反应", "提示嘴角、眼底、呼吸等高频代写。"],
  ["dash-overuse", "破折号密度", "按每 100 个叙事单元和单段双重判断。"],
  ["staccato-period-overuse", "碎句密度", "避免把同一语义链切成均匀短句。"],
  ["mechanical-transition-overuse", "显性转折词", "控制但是、然而、于是、突然的机械接榫。"],
  ["simile-dependency", "比喻依赖", "避免用好像、仿佛和万能比喻撑情绪。"],
  ["slogan-like-ending", "金句式收尾", "提醒主题直说和整齐反转句。"],
] as const;

const statusLabel = computed(() => preview.value?.status === "blocking" ? "需要修改" : preview.value?.status === "notes" ? "有表达提醒" : "通过当前规则");
const findings = computed(() => [...(preview.value?.blocking || []), ...(preview.value?.notes || [])]);

onMounted(() => void load());

async function load(): Promise<void> {
  if (!store.currentProjectPath) return;
  const result = await api<{ profile: QualityProfile }>(`/project/creative-quality?project_root=${encodeURIComponent(store.currentProjectPath)}`);
  profile.value = result.profile;
  await runPreview();
}

async function runPreview(): Promise<void> {
  if (!profile.value || !store.currentProjectPath) return;
  preview.value = await api<Record<string, unknown>>("/project/creative-quality/preview", {
    method: "POST",
    body: JSON.stringify({ project_root: store.currentProjectPath, text: previewText.value, profile: profile.value, scope: previewScope.value }),
  });
}

async function save(): Promise<void> {
  if (!profile.value || !store.currentProjectPath) return;
  saving.value = true;
  message.value = "";
  try {
    const result = await api<{ profile: QualityProfile }>("/project/creative-quality", {
      method: "PUT",
      body: JSON.stringify({ project_root: store.currentProjectPath, profile: profile.value }),
    });
    profile.value = result.profile;
    message.value = "规则已保存。它会从下一份候选正文开始生效，旧稿需要重新审查。";
    await runPreview();
  } finally {
    saving.value = false;
  }
}

async function applyPreset(preset: string): Promise<void> {
  if (!profile.value) return;
  profile.value.preset = preset;
  const values: Record<string, number[]> = {
    balanced: [2, 2, 4, 2], plainspoken: [1, .5, 2, 1], "style-led": [3, 4, 5, 4],
  };
  const [soft, dash, transitions, simile] = values[preset] || values.balanced;
  Object.assign(profile.value.thresholds, {
    soft_density_per_100_units: soft,
    dash_per_100_units: dash,
    transition_per_100_units: transitions,
    simile_per_100_units: simile,
  });
  await runPreview();
}

function addException(): void {
  if (!profile.value) return;
  profile.value.exceptions ||= [];
  profile.value.exceptions.push({ rule: "mechanical-contrast-frame", scope: "scene_0001", reason: "本场景的已登记文风需要", mode: "note", expires_at: "" });
}

function removeException(index: number): void {
  profile.value?.exceptions.splice(index, 1);
  void runPreview();
}
</script>

<template>
  <div v-if="profile && props.instrument" class="quality-instrument">
    <header class="quality-instrument-heading">
      <div><span class="eyebrow">创作控制</span><h2>规则与叙事节奏</h2><p>在候选正文生成前，直接规定语言质地与场景张力。</p></div>
      <div class="quality-instrument-revision"><ShieldCheck :size="15" /><span>第 {{ profile.revision }} 版</span><small>{{ profile.digest.slice(0, 8) }}</small></div>
    </header>

    <nav class="quality-instrument-tabs" aria-label="规则仪表工作面">
      <button :class="{ active: instrumentTab === 'rhythm' }" @click="instrumentTab = 'rhythm'">节奏曲线</button>
      <button :class="{ active: instrumentTab === 'language' }" @click="instrumentTab = 'language'">语言质地</button>
      <button :class="{ active: instrumentTab === 'preview' }" @click="instrumentTab = 'preview'">即时样文</button>
      <button :class="{ active: instrumentTab === 'rules' }" @click="instrumentTab = 'rules'">逐条规则</button>
    </nav>

    <RhythmCurveEditor v-if="instrumentTab === 'rhythm'" compact />

    <section v-else-if="instrumentTab === 'language'" class="quality-instrument-language">
      <div class="quality-instrument-presets">
        <button :class="{ active: profile.preset === 'balanced' }" @click="applyPreset('balanced')"><Sparkles :size="15" /><strong>均衡</strong><span>保留表达空间</span></button>
        <button :class="{ active: profile.preset === 'plainspoken' }" @click="applyPreset('plainspoken')"><CircleCheck :size="15" /><strong>克制</strong><span>减少套话与修饰</span></button>
        <button :class="{ active: profile.preset === 'style-led' }" @click="applyPreset('style-led')"><FlaskConical :size="15" /><strong>文风优先</strong><span>给挂载文风留余地</span></button>
      </div>
      <div class="quality-instrument-sliders">
        <label><span><strong>破折号</strong><small>每 100 个叙事单元</small></span><input v-model.number="profile.thresholds.dash_per_100_units" type="range" min="0" max="8" step=".5" @input="runPreview" /><output>{{ profile.thresholds.dash_per_100_units }}</output></label>
        <label><span><strong>套话</strong><small>器官反应与万能占位</small></span><input v-model.number="profile.thresholds.soft_density_per_100_units" type="range" min="0" max="8" step=".5" @input="runPreview" /><output>{{ profile.thresholds.soft_density_per_100_units }}</output></label>
        <label><span><strong>显性转折</strong><small>但是、然而、于是、突然</small></span><input v-model.number="profile.thresholds.transition_per_100_units" type="range" min="0" max="12" step="1" @input="runPreview" /><output>{{ profile.thresholds.transition_per_100_units }}</output></label>
        <label><span><strong>比喻依赖</strong><small>好像、仿佛、像……一样</small></span><input v-model.number="profile.thresholds.simile_per_100_units" type="range" min="0" max="10" step=".5" @input="runPreview" /><output>{{ profile.thresholds.simile_per_100_units }}</output></label>
        <label><span><strong>单句逗号</strong><small>超过后建议重组句法</small></span><input v-model.number="profile.thresholds.commas_per_sentence" type="number" min="1" max="10" @input="runPreview" /><output>{{ profile.thresholds.commas_per_sentence }}</output></label>
      </div>
    </section>

    <section v-else-if="instrumentTab === 'preview'" class="quality-instrument-preview">
      <header><div><span class="eyebrow">即时样文检查</span><h3>先看规则会怎样判断</h3></div><button class="orrery-icon" title="重新检查" @click="runPreview"><RefreshCw :size="15" /></button></header>
      <textarea v-model="previewText" rows="7" aria-label="样文" @input="runPreview"></textarea>
      <label>按场景例外预览<input v-model.trim="previewScope" placeholder="留空表示项目通用规则" @input="runPreview" /></label>
      <div class="quality-instrument-verdict" :data-status="preview?.status || 'pass'"><CircleAlert v-if="preview?.status === 'blocking'" :size="16" /><CircleCheck v-else :size="16" /><strong>{{ statusLabel }}</strong><span>{{ findings.length }} 项</span></div>
      <div class="quality-instrument-findings"><article v-for="item in findings.slice(0, 6)" :key="`${item.rule}-${item.sample}`"><strong>{{ item.severity === 'low' ? '提醒' : '需修改' }}</strong><p>{{ item.message }}</p><small v-if="item.sample">{{ item.sample }}</small></article><p v-if="!findings.length">没有触发确定性规则，语义与人物仍会进入正式审查。</p></div>
    </section>

    <section v-else class="quality-instrument-rules">
      <article v-for="rule in rules" :key="rule[0]">
        <div><strong>{{ rule[1] }}</strong><p>{{ rule[2] }}</p></div>
        <div class="rule-modes" role="group" :aria-label="`${rule[1]}强度`"><button :class="{ active: profile.rule_modes[rule[0]] === 'off' }" @click="profile.rule_modes[rule[0]] = 'off'; runPreview()">关闭</button><button :class="{ active: profile.rule_modes[rule[0]] === 'note' }" @click="profile.rule_modes[rule[0]] = 'note'; runPreview()">提醒</button><button :class="{ active: profile.rule_modes[rule[0]] === 'blocking' }" @click="profile.rule_modes[rule[0]] = 'blocking'; runPreview()">阻断</button></div>
      </article>
      <label class="field"><span>项目自定义禁用表达（每行一条）</span><textarea :value="profile.custom_banned_phrases.join('\n')" rows="4" @input="profile.custom_banned_phrases = ($event.target as HTMLTextAreaElement).value.split('\n').map(v => v.trim()).filter(Boolean); runPreview()"></textarea></label>
      <section class="quality-instrument-exceptions">
        <header><div><strong>场景范围例外</strong><p>例外必须有范围与理由。</p></div><button class="secondary-button" @click="addException"><Plus :size="14" />新增</button></header>
        <article v-for="(item, index) in profile.exceptions" :key="index"><input v-model.trim="item.scope" placeholder="scene_0001" /><select v-model="item.rule"><option v-for="rule in rules" :key="rule[0]" :value="rule[0]">{{ rule[1] }}</option></select><select v-model="item.mode"><option value="off">关闭</option><option value="note">提醒</option><option value="blocking">阻断</option></select><input v-model.trim="item.reason" placeholder="说明理由" /><button class="icon-button" title="删除例外" @click="removeException(index)"><Trash2 :size="14" /></button></article>
      </section>
    </section>

    <footer class="quality-instrument-save"><p>{{ message || "保存后从下一份候选正文开始生效。" }}</p><button class="primary-button" :disabled="saving" @click="save"><Save :size="15" />{{ saving ? "正在保存" : "保存规则" }}</button></footer>
  </div>

  <div class="view quality-view" v-else-if="profile">
    <header class="quality-heading">
      <div><span class="eyebrow">创作规则</span><h1>让语言保持你要的质地</h1><p>这里调节文学表达，不会关闭审查、晋升、设定写回或正式导出。</p></div>
      <div class="profile-stamp"><ShieldCheck :size="18" /><span>第 {{ profile.revision }} 版</span><small>{{ profile.digest.slice(0, 10) }}</small></div>
    </header>

    <section class="quality-presets">
      <button :class="{ active: profile.preset === 'balanced' }" @click="applyPreset('balanced')"><Sparkles :size="17" /><strong>均衡叙事</strong><span>保留表达空间，同时拦住明显套话。</span></button>
      <button :class="{ active: profile.preset === 'plainspoken' }" @click="applyPreset('plainspoken')"><CircleCheck :size="17" /><strong>朴素克制</strong><span>更少比喻、破折号和显式转折。</span></button>
      <button :class="{ active: profile.preset === 'style-led' }" @click="applyPreset('style-led')"><FlaskConical :size="17" /><strong>文风优先</strong><span>为鲜明句法与节奏保留更大余地。</span></button>
    </section>

    <RhythmCurveEditor />

    <div class="quality-workbench">
      <section class="quality-controls">
        <header><div><span class="eyebrow">基础控制</span><h2>用文学语言调整阈值</h2></div><button class="text-button" @click="advanced = !advanced">{{ advanced ? "收起逐条规则" : "打开逐条规则" }}</button></header>
        <label class="quality-slider"><span><strong>破折号容忍度</strong><small>每 100 个叙事单元</small></span><input v-model.number="profile.thresholds.dash_per_100_units" type="range" min="0" max="8" step=".5" @input="runPreview" /><output>{{ profile.thresholds.dash_per_100_units }}</output></label>
        <label class="quality-slider"><span><strong>套话容忍度</strong><small>器官反应、万能占位等</small></span><input v-model.number="profile.thresholds.soft_density_per_100_units" type="range" min="0" max="8" step=".5" @input="runPreview" /><output>{{ profile.thresholds.soft_density_per_100_units }}</output></label>
        <label class="quality-slider"><span><strong>显性转折密度</strong><small>但是、然而、于是、突然</small></span><input v-model.number="profile.thresholds.transition_per_100_units" type="range" min="0" max="12" step="1" @input="runPreview" /><output>{{ profile.thresholds.transition_per_100_units }}</output></label>
        <label class="quality-slider"><span><strong>比喻密度</strong><small>好像、仿佛、像……一样</small></span><input v-model.number="profile.thresholds.simile_per_100_units" type="range" min="0" max="10" step=".5" @input="runPreview" /><output>{{ profile.thresholds.simile_per_100_units }}</output></label>
        <label class="quality-number"><span><strong>一句最多几个逗号</strong><small>超过后建议重组句法</small></span><input v-model.number="profile.thresholds.commas_per_sentence" type="number" min="1" max="10" @input="runPreview" /></label>

        <div v-if="advanced" class="quality-rules">
          <article v-for="rule in rules" :key="rule[0]">
            <div><strong>{{ rule[1] }}</strong><p>{{ rule[2] }}</p></div>
            <div class="rule-modes" role="group" :aria-label="`${rule[1]}强度`">
              <button :class="{ active: profile.rule_modes[rule[0]] === 'off' }" @click="profile.rule_modes[rule[0]] = 'off'; runPreview()">关闭</button>
              <button :class="{ active: profile.rule_modes[rule[0]] === 'note' }" @click="profile.rule_modes[rule[0]] = 'note'; runPreview()">提醒</button>
              <button :class="{ active: profile.rule_modes[rule[0]] === 'blocking' }" @click="profile.rule_modes[rule[0]] = 'blocking'; runPreview()">阻断</button>
            </div>
          </article>
          <label class="field"><span>项目自定义禁用表达（每行一条）</span><textarea :value="profile.custom_banned_phrases.join('\n')" rows="4" @input="profile.custom_banned_phrases = ($event.target as HTMLTextAreaElement).value.split('\n').map(v => v.trim()).filter(Boolean); runPreview()"></textarea></label>
          <section class="quality-exceptions">
            <header><div><strong>场景范围例外</strong><p>例外必须写明场景、规则和理由，只在指定场景生效。</p></div><button class="secondary-button" @click="addException"><Plus :size="14" />新增例外</button></header>
            <article v-for="(item, index) in profile.exceptions" :key="index">
              <label><span>场景</span><input v-model.trim="item.scope" placeholder="scene_0001" /></label>
              <label><span>规则</span><select v-model="item.rule"><option v-for="rule in rules" :key="rule[0]" :value="rule[0]">{{ rule[1] }}</option></select></label>
              <label><span>在此场景</span><select v-model="item.mode"><option value="off">关闭</option><option value="note">仅提醒</option><option value="blocking">仍阻断</option></select></label>
              <label class="exception-reason"><span>理由</span><input v-model.trim="item.reason" placeholder="说明为何需要这项范围例外" /></label>
              <button class="icon-button" title="删除例外" @click="removeException(index)"><Trash2 :size="15" /></button>
            </article>
          </section>
        </div>
      </section>

      <aside class="quality-preview">
        <header><div><span class="eyebrow">即时样文检查</span><h2>这段文字会怎样被判断</h2></div><button class="icon-button" title="重新检查" @click="runPreview"><RefreshCw :size="16" /></button></header>
        <textarea v-model="previewText" rows="9" @input="runPreview" aria-label="样文"></textarea>
        <label class="preview-scope"><span>按场景例外预览</span><input v-model.trim="previewScope" placeholder="留空表示项目通用规则" @input="runPreview" /></label>
        <div class="preview-verdict" :data-status="preview?.status || 'pass'"><CircleAlert v-if="preview?.status === 'blocking'" :size="18" /><CircleCheck v-else :size="18" /><strong>{{ statusLabel }}</strong><span>{{ findings.length }} 项</span></div>
        <div class="preview-findings">
          <article v-for="item in findings.slice(0, 6)" :key="`${item.rule}-${item.sample}`" :data-severity="item.severity">
            <strong>{{ item.severity === 'low' ? '表达提醒' : '需要修改' }}</strong><p>{{ item.message }}</p><small v-if="item.sample">{{ item.sample }}</small>
          </article>
          <p v-if="!findings.length" class="preview-clean">没有触发确定性规则。语义、人物与文风仍会进入正式 AgentReview。</p>
        </div>
      </aside>
    </div>

    <footer class="quality-savebar"><p>{{ message || "修改只影响未来候选稿；已经审查的文字不会被悄悄改判。" }}</p><button class="primary-button" :disabled="saving" @click="save"><Save :size="16" />{{ saving ? "正在保存" : "保存创作规则" }}</button></footer>
  </div>
</template>
