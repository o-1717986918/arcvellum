<script setup lang="ts">
import { onMounted, ref } from "vue";
import { CircleAlert, CircleCheck, FlaskConical, Plus, RefreshCw, Save, ShieldCheck, Sparkles, Trash2 } from "lucide-vue-next";
import RhythmCurveEditor from "@/components/RhythmCurveEditor.vue";
import { useQualityProfile } from "./useQualityProfile";

const tab = ref<"rhythm" | "language" | "preview" | "rules">("rhythm");
const {
  profile, previewText, preview, previewScope, loading, saving, dirty, message, error,
  statusLabel, findings, rules, load, runPreview, schedulePreview, save, applyPreset,
  addException, removeException,
} = useQualityProfile();

onMounted(() => void load());
</script>

<template>
  <div class="rules-instrument-shell">
    <div v-if="loading" class="rules-instrument-state"><i></i><strong>正在校准创作规则</strong><p>读取语言阈值、文风例外与叙事节奏合同。</p></div>
    <div v-else-if="!profile" class="rules-instrument-state is-error"><CircleAlert :size="20" /><strong>规则暂时没有就绪</strong><p>{{ error || "请确认已经打开一个有效作品。" }}</p><button class="secondary-button" @click="load"><RefreshCw :size="14" />重新读取</button></div>
    <template v-else>
      <header class="rules-instrument-heading">
        <div><span class="eyebrow">创作控制</span><h2>规则与叙事节奏</h2></div>
        <div class="quality-instrument-revision"><ShieldCheck :size="15" /><span>第 {{ profile.revision }} 版</span><small :class="{ dirty }">{{ dirty ? "有未保存调整" : profile.digest.slice(0, 8) }}</small></div>
      </header>
      <nav class="quality-instrument-tabs" aria-label="规则仪表工作面">
        <button :class="{ active: tab === 'rhythm' }" @click="tab = 'rhythm'">节奏</button>
        <button :class="{ active: tab === 'language' }" @click="tab = 'language'">语言</button>
        <button :class="{ active: tab === 'preview' }" @click="tab = 'preview'">样文</button>
        <button :class="{ active: tab === 'rules' }" @click="tab = 'rules'">规则</button>
      </nav>
      <main class="rules-instrument-scroll">
        <RhythmCurveEditor v-if="tab === 'rhythm'" compact />
        <section v-else-if="tab === 'language'" class="quality-instrument-language">
          <div class="quality-instrument-presets">
            <button :class="{ active: profile.preset === 'balanced' }" @click="applyPreset('balanced')"><Sparkles :size="15" /><strong>均衡</strong><span>保留表达空间</span></button>
            <button :class="{ active: profile.preset === 'plainspoken' }" @click="applyPreset('plainspoken')"><CircleCheck :size="15" /><strong>克制</strong><span>减少套话修饰</span></button>
            <button :class="{ active: profile.preset === 'style-led' }" @click="applyPreset('style-led')"><FlaskConical :size="15" /><strong>文风优先</strong><span>允许鲜明句法</span></button>
          </div>
          <div class="quality-instrument-sliders">
            <label><span><strong>破折号</strong><small>每 100 个叙事单元</small></span><input v-model.number="profile.thresholds.dash_per_100_units" type="range" min="0" max="8" step=".5" @input="schedulePreview" /><output>{{ profile.thresholds.dash_per_100_units }}</output></label>
            <label><span><strong>套话</strong><small>器官反应与万能占位</small></span><input v-model.number="profile.thresholds.soft_density_per_100_units" type="range" min="0" max="8" step=".5" @input="schedulePreview" /><output>{{ profile.thresholds.soft_density_per_100_units }}</output></label>
            <label><span><strong>显性转折</strong><small>但是、然而、于是、突然</small></span><input v-model.number="profile.thresholds.transition_per_100_units" type="range" min="0" max="12" step="1" @input="schedulePreview" /><output>{{ profile.thresholds.transition_per_100_units }}</output></label>
            <label><span><strong>比喻依赖</strong><small>好像、仿佛、像……一样</small></span><input v-model.number="profile.thresholds.simile_per_100_units" type="range" min="0" max="10" step=".5" @input="schedulePreview" /><output>{{ profile.thresholds.simile_per_100_units }}</output></label>
            <label><span><strong>单句逗号</strong><small>超过后建议重组句法</small></span><input v-model.number="profile.thresholds.commas_per_sentence" type="number" min="1" max="10" @input="schedulePreview" /><output>{{ profile.thresholds.commas_per_sentence }}</output></label>
          </div>
        </section>
        <section v-else-if="tab === 'preview'" class="quality-instrument-preview">
          <header><div><span class="eyebrow">即时样文检查</span><h3>先看规则会怎样判断</h3></div><button class="orrery-icon" title="重新检查" @click="runPreview"><RefreshCw :size="15" /></button></header>
          <textarea v-model="previewText" rows="7" aria-label="样文" @input="schedulePreview"></textarea>
          <label>按场景例外预览<input v-model.trim="previewScope" placeholder="留空表示项目通用规则" @input="schedulePreview" /></label>
          <div class="quality-instrument-verdict" :data-status="preview?.status || 'pass'"><CircleAlert v-if="preview?.status === 'blocking'" :size="16" /><CircleCheck v-else :size="16" /><strong>{{ statusLabel }}</strong><span>{{ findings.length }} 项</span></div>
          <div class="quality-instrument-findings"><article v-for="item in findings.slice(0, 6)" :key="`${item.rule}-${item.sample}`"><strong>{{ item.severity === 'low' ? '提醒' : '需修改' }}</strong><p>{{ item.message }}</p><small v-if="item.sample">{{ item.sample }}</small></article><p v-if="!findings.length">没有触发确定性规则，语义与人物仍会进入正式审查。</p></div>
        </section>
        <section v-else class="quality-instrument-rules">
          <article v-for="rule in rules" :key="rule[0]">
            <div><strong>{{ rule[1] }}</strong><p>{{ rule[2] }}</p></div>
            <div class="rule-modes" role="group" :aria-label="`${rule[1]}强度`"><button :class="{ active: profile.rule_modes[rule[0]] === 'off' }" @click="profile.rule_modes[rule[0]] = 'off'; schedulePreview()">关闭</button><button :class="{ active: profile.rule_modes[rule[0]] === 'note' }" @click="profile.rule_modes[rule[0]] = 'note'; schedulePreview()">提醒</button><button :class="{ active: profile.rule_modes[rule[0]] === 'blocking' }" @click="profile.rule_modes[rule[0]] = 'blocking'; schedulePreview()">阻断</button></div>
          </article>
          <label class="field"><span>项目自定义禁用表达（每行一条）</span><textarea :value="profile.custom_banned_phrases.join('\n')" rows="4" @input="profile.custom_banned_phrases = ($event.target as HTMLTextAreaElement).value.split('\n').map(v => v.trim()).filter(Boolean); schedulePreview()"></textarea></label>
          <section class="quality-instrument-exceptions">
            <header><div><strong>场景范围例外</strong><p>例外必须有范围与理由。</p></div><button class="secondary-button" @click="addException"><Plus :size="14" />新增</button></header>
            <article v-for="(item, index) in profile.exceptions" :key="index"><input v-model.trim="item.scope" placeholder="scene_0001" @input="schedulePreview" /><select v-model="item.rule" @change="schedulePreview"><option v-for="rule in rules" :key="rule[0]" :value="rule[0]">{{ rule[1] }}</option></select><select v-model="item.mode" @change="schedulePreview"><option value="off">关闭</option><option value="note">提醒</option><option value="blocking">阻断</option></select><input v-model.trim="item.reason" placeholder="说明理由" @input="schedulePreview" /><button class="icon-button" title="删除例外" @click="removeException(index)"><Trash2 :size="14" /></button></article>
          </section>
        </section>
      </main>
      <footer class="quality-instrument-save" :data-dirty="dirty">
        <p :class="{ error }">{{ error || message || (dirty ? "规则有调整，保存后才会进入正式任务包。" : "规则已与正式项目同步。") }}</p>
        <button class="primary-button" :disabled="saving || !dirty" @click="save"><Save :size="15" />{{ saving ? "正在保存" : dirty ? "保存规则" : "已保存" }}</button>
      </footer>
    </template>
  </div>
</template>
