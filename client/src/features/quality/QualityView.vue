<script setup lang="ts">
import { onMounted, ref } from "vue";
import { CircleAlert, CircleCheck, FlaskConical, Plus, RefreshCw, Save, ShieldCheck, Sparkles, Trash2 } from "lucide-vue-next";
import RhythmCurveEditor from "@/components/RhythmCurveEditor.vue";
import { useQualityProfile } from "./useQualityProfile";

const advanced = ref(false);
const {
  profile, previewText, preview, previewScope, loading, saving, dirty, message, error,
  statusLabel, findings, rules, load, runPreview, schedulePreview, save, applyPreset,
  addException, removeException,
} = useQualityProfile();

onMounted(() => void load());
</script>

<template>
  <div v-if="loading" class="view quality-view"><div class="rules-page-state"><strong>正在读取创作规则</strong><p>稍候，语言与节奏设置正在与正式项目同步。</p></div></div>
  <div v-else-if="!profile" class="view quality-view"><div class="rules-page-state is-error"><CircleAlert :size="22" /><strong>创作规则暂时不可用</strong><p>{{ error || "请确认已经打开一个有效作品。" }}</p><button class="secondary-button" @click="load"><RefreshCw :size="15" />重新读取</button></div></div>
  <div class="view quality-view" v-else>
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
        <label class="quality-slider"><span><strong>破折号容忍度</strong><small>每 100 个叙事单元</small></span><input v-model.number="profile.thresholds.dash_per_100_units" type="range" min="0" max="8" step=".5" @input="schedulePreview" /><output>{{ profile.thresholds.dash_per_100_units }}</output></label>
        <label class="quality-slider"><span><strong>套话容忍度</strong><small>器官反应、万能占位等</small></span><input v-model.number="profile.thresholds.soft_density_per_100_units" type="range" min="0" max="8" step=".5" @input="schedulePreview" /><output>{{ profile.thresholds.soft_density_per_100_units }}</output></label>
        <label class="quality-slider"><span><strong>显性转折密度</strong><small>但是、然而、于是、突然</small></span><input v-model.number="profile.thresholds.transition_per_100_units" type="range" min="0" max="12" step="1" @input="schedulePreview" /><output>{{ profile.thresholds.transition_per_100_units }}</output></label>
        <label class="quality-slider"><span><strong>比喻密度</strong><small>好像、仿佛、像……一样</small></span><input v-model.number="profile.thresholds.simile_per_100_units" type="range" min="0" max="10" step=".5" @input="schedulePreview" /><output>{{ profile.thresholds.simile_per_100_units }}</output></label>
        <label class="quality-number"><span><strong>一句最多几个逗号</strong><small>超过后建议重组句法</small></span><input v-model.number="profile.thresholds.commas_per_sentence" type="number" min="1" max="10" @input="schedulePreview" /></label>

        <div v-if="advanced" class="quality-rules">
          <article v-for="rule in rules" :key="rule[0]">
            <div><strong>{{ rule[1] }}</strong><p>{{ rule[2] }}</p></div>
            <div class="rule-modes" role="group" :aria-label="`${rule[1]}强度`">
              <button :class="{ active: profile.rule_modes[rule[0]] === 'off' }" @click="profile.rule_modes[rule[0]] = 'off'; schedulePreview()">关闭</button>
              <button :class="{ active: profile.rule_modes[rule[0]] === 'note' }" @click="profile.rule_modes[rule[0]] = 'note'; schedulePreview()">提醒</button>
              <button :class="{ active: profile.rule_modes[rule[0]] === 'blocking' }" @click="profile.rule_modes[rule[0]] = 'blocking'; schedulePreview()">阻断</button>
            </div>
          </article>
          <label class="field"><span>项目自定义禁用表达（每行一条）</span><textarea :value="profile.custom_banned_phrases.join('\n')" rows="4" @input="profile.custom_banned_phrases = ($event.target as HTMLTextAreaElement).value.split('\n').map(v => v.trim()).filter(Boolean); schedulePreview()"></textarea></label>
          <section class="quality-exceptions">
            <header><div><strong>场景范围例外</strong><p>例外必须写明场景、规则和理由，只在指定场景生效。</p></div><button class="secondary-button" @click="addException"><Plus :size="14" />新增例外</button></header>
            <article v-for="(item, index) in profile.exceptions" :key="index">
              <label><span>场景</span><input v-model.trim="item.scope" placeholder="scene_0001" @input="schedulePreview" /></label>
              <label><span>规则</span><select v-model="item.rule" @change="schedulePreview"><option v-for="rule in rules" :key="rule[0]" :value="rule[0]">{{ rule[1] }}</option></select></label>
              <label><span>在此场景</span><select v-model="item.mode" @change="schedulePreview"><option value="off">关闭</option><option value="note">仅提醒</option><option value="blocking">仍阻断</option></select></label>
              <label class="exception-reason"><span>理由</span><input v-model.trim="item.reason" placeholder="说明为何需要这项范围例外" @input="schedulePreview" /></label>
              <button class="icon-button" title="删除例外" @click="removeException(index)"><Trash2 :size="15" /></button>
            </article>
          </section>
        </div>
      </section>

      <aside class="quality-preview">
        <header><div><span class="eyebrow">即时样文检查</span><h2>这段文字会怎样被判断</h2></div><button class="icon-button" title="重新检查" @click="runPreview"><RefreshCw :size="16" /></button></header>
        <textarea v-model="previewText" rows="9" @input="schedulePreview" aria-label="样文"></textarea>
        <label class="preview-scope"><span>按场景例外预览</span><input v-model.trim="previewScope" placeholder="留空表示项目通用规则" @input="schedulePreview" /></label>
        <div class="preview-verdict" :data-status="preview?.status || 'pass'"><CircleAlert v-if="preview?.status === 'blocking'" :size="18" /><CircleCheck v-else :size="18" /><strong>{{ statusLabel }}</strong><span>{{ findings.length }} 项</span></div>
        <div class="preview-findings">
          <article v-for="item in findings.slice(0, 6)" :key="`${item.rule}-${item.sample}`" :data-severity="item.severity">
            <strong>{{ item.severity === 'low' ? '表达提醒' : '需要修改' }}</strong><p>{{ item.message }}</p><small v-if="item.sample">{{ item.sample }}</small>
          </article>
          <p v-if="!findings.length" class="preview-clean">没有触发确定性规则。语义、人物与文风仍会进入正式 AgentReview。</p>
        </div>
      </aside>
    </div>

    <footer class="quality-savebar"><p :class="{ error }">{{ error || message || (dirty ? "有未保存调整；保存后才会进入正式任务包。" : "修改只影响未来候选稿；已经审查的文字不会被悄悄改判。") }}</p><button class="primary-button" :disabled="saving || !dirty" @click="save"><Save :size="16" />{{ saving ? "正在保存" : dirty ? "保存创作规则" : "已保存" }}</button></footer>
  </div>
</template>
