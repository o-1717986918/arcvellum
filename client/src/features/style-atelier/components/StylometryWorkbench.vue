<script setup lang="ts">
import { computed, toRef } from "vue";
import { useStylometry } from "../stores/useStylometry";
import StylometrySources from "./StylometrySources.vue";
import type { MetricRow } from "../stylometryTypes";
import "../stylometry.css";
const props = defineProps<{ projectRoot: string }>();
const desk = useStylometry(toRef(props, "projectRoot"));
const { workbench, profile, metrics, controls, sources, title, intent, dependency, candidateTree, fragment,
  compiled, selectedVersion, report, text, busy, error, notice, job, jobs, tab, combine, usage, running, dirty, combined } = desk;
const parameterRows = computed(() => metrics.value.map(metric => ({ metric,
  target: controls.value?.targets.find(target => target.id === metric.id) })));
const labels: Record<string, string> = { sentence_length_han: "平均句长", paragraph_length_han: "平均段长",
  dialogue_share: "对白比例代理", punctuation_per_1000_han: "每千汉字标点数" };
function addTarget(row: MetricRow) {
  if (controls.value && !controls.value.targets.some(target => target.id === row.id)) {
    controls.value.targets.push({ id: row.id, unit: row.unit, ...row.suggested, enabled: false });
  }
}
function value(number: number | null | undefined) { return number == null ? "缺测" : Number(number.toFixed(4)).toString(); }
function exportVersion() {
  const data = { schema: "arcvellum/stylometry-review-export/v1", profile: profile.value, controls: controls.value,
    compiled: compiled.value, fragment_text: fragment.value, saved_version: selectedVersion.value,
    mount: workbench.value?.mount, measurement: report.value };
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" }));
  const link = document.createElement("a"); link.href = url; link.download = "creator-stylometry-review.json";
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
}
</script>
<template>
  <section class="stylo-desk" aria-label="计量文风工作台">
    <header class="stylo-heading"><div><span class="eyebrow">Stylometric Prompt Lab · 实验</span><h2>计量文风工作台</h2><p>统计语料，调整语言目标，再把你认可的文风片段交给场景主创。</p></div>
      <div class="stylo-actions"><span class="stylo-mount-state">{{ workbench?.mount.enabled ? '已挂载 · ' + (workbench.mount.usage === 'guide' ? '参与创作' : '仅观测') : '当前未挂载' }}</span><button :disabled="busy || !projectRoot" @click="desk.load">刷新</button></div>
    </header>
    <p v-if="!projectRoot" class="stylo-hint">先选择一部作品，即可导入语料或进行单篇统计。</p>
    <p v-if="error" class="stylo-error" role="alert">{{ error }}</p><p v-if="notice" class="stylo-notice" role="status">{{ notice }}</p>
    <nav class="stylo-tabs" aria-label="计量文风步骤"><button v-for="item in [{ id: 'corpus', label: '语料与统计' }, { id: 'parameters', label: '参数与提示词' }, { id: 'mount', label: '主创挂载与测量' }]" :key="item.id" :aria-pressed="tab === item.id" @click="tab = item.id">{{ item.label }}</button></nav>
    <div class="stylo-body">
      <aside class="stylo-library">
        <h3>语料画像</h3><button v-for="row in workbench?.profiles || []" :key="row.profile_id" :disabled="busy" :aria-pressed="profile?.profile_id === row.profile_id" @click="desk.selectProfile(row.profile_id)">{{ row.title }}</button>
        <p v-if="!workbench?.profiles.length" class="stylo-hint">加入训练与留出语料，保存第一份画像。</p>
        <h3>参数版本</h3><button v-for="row in workbench?.versions || []" :key="row.version_id" :disabled="busy" :aria-pressed="selectedVersion?.version_id === row.version_id" @click="desk.selectVersion(row.version_id)">{{ row.title }}<small>{{ workbench?.mount.version_id === row.version_id ? '当前挂载' : row.user_edited ? '手动修改片段' : '编译片段' }}</small></button>
        <p class="stylo-hint">Lab {{ workbench?.capabilities.lab_version || '加载中' }}<br />依存：可导入已保存原树<br />LTP 标注 / R：当前未配置</p>
      </aside>
      <main class="stylo-content">
        <section v-show="tab === 'corpus'">
          <label>语料名称<input v-model="title" maxlength="80" /></label>
          <StylometrySources :project-root="projectRoot" v-model:sources="sources" :busy="busy || running" />
          <div class="stylo-actions"><button class="stylo-primary" :disabled="busy || running || !sources.length || !projectRoot" @click="desk.launch">{{ sources.length === 1 ? '统计单篇' : '建立语料画像' }}</button><span class="stylo-hint">{{ sources.length }} 篇 · {{ sources.reduce((sum, row) => sum + row.text.length, 0).toLocaleString() }} 字符</span></div>
          <section v-if="job" class="stylo-job" aria-live="polite"><strong>{{ job.title }} · {{ job.phase }}</strong><span>第 {{ job.attempt }} 次尝试</span><button v-if="running" :disabled="busy || job.status === 'cancelling'" @click="desk.jobAction('cancel')">停止统计</button><button v-if="['failed','interrupted','cancelled'].includes(job.status)" :disabled="busy" @click="desk.jobAction('resume')">恢复统计</button><p v-if="job.error" class="stylo-error">{{ job.error }}</p></section>
          <details v-if="jobs.length"><summary>历史统计任务</summary><button v-for="row in jobs" :key="row.job_id" :disabled="busy" @click="desk.selectJob(row)">{{ row.title }} · {{ row.phase }}</button></details>
          <details v-if="profile"><summary>来源、摘要与窗口／作品分布</summary><pre>{{ JSON.stringify({ sources: profile.source_declarations, inspection: profile.inspection, distribution: JSON.parse(profile.profile_json) }, null, 2) }}</pre></details>
          <div v-if="report"><h3>文本实测</h3><dl class="stylo-observations"><div v-for="(number, key) in report.measurement.axes" :key="key"><dt>{{ labels[key] || key }}</dt><dd>{{ value(number) }}</dd></div></dl><details><summary>查看计算口径、分母与扩展统计</summary><pre>{{ JSON.stringify(report, null, 2) }}</pre></details></div>
        </section>
        <section v-show="tab === 'parameters'">
          <p v-if="!profile" class="stylo-hint">先建立或选择语料画像，再调整四主轴、九项次级目标与高频语法词。</p>
          <template v-else><div class="stylo-actions"><label>版本名称<input v-model="title" maxlength="80" /></label><button :disabled="busy" @click="desk.restore">恢复语料建议</button></div>
            <p class="stylo-hint">启用的指标写入片段。范围表示写作实验目标，实际效果由正文测量与文学审读观察。</p>
            <div class="stylo-table-wrap"><table class="stylo-targets"><thead><tr><th>启用 / 指标</th><th>语料实测</th><th>目标下界</th><th>目标上界</th><th>单位</th></tr></thead><tbody><tr v-for="{ metric: row, target } in parameterRows" :key="row.id"><td><label v-if="target"><input v-model="target.enabled" type="checkbox" :disabled="!row.available || busy" />{{ row.label }}</label><template v-else>{{ row.label }} <button :disabled="busy" @click="addTarget(row)">加入此指标</button></template></td><td>{{ value(row.observed) }}</td><td><input v-if="target" v-model.number="target.min" type="number" step="any" :disabled="busy" :min="row.floor" :max="row.ceiling" :aria-label="row.label + '目标下界'" /><span v-else>未纳入此版本</span></td><td><input v-if="target" v-model.number="target.max" type="number" step="any" :disabled="busy" :min="row.floor" :max="row.ceiling" :aria-label="row.label + '目标上界'" /></td><td>{{ row.unit }}</td></tr></tbody></table></div>
            <details><summary>导入可选的依存参考原树</summary><label>Lab 原树 JSON<textarea v-model="dependency" rows="4" placeholder="原树保留文本摘要、模型标识、标注体系与 parse_hash。" /></label><button :disabled="busy" @click="desk.loadDependency">核验参考树并加载参数</button></details>
            <label>自由文风意图<textarea v-model="intent" rows="3" maxlength="8000" placeholder="写下你希望这些语言目标怎样服务于故事。" /></label>
            <button :disabled="busy" @click="desk.compile">编译文风片段</button>
            <label>实际文风片段 · 可直接修改<textarea v-model="fragment" class="stylo-fragment" rows="12" maxlength="32000" placeholder="编译后可逐句修改；保存为独立版本。" /></label>
            <div class="stylo-actions"><button class="stylo-primary" :disabled="busy || !fragment.trim()" @click="desk.save">保存新版本</button><button :disabled="!fragment" @click="exportVersion">导出结构化文本</button><small v-if="dirty">当前修改尚未保存</small></div>
          </template>
        </section>
        <section v-show="tab === 'mount'">
          <label>组合方式<select v-model="combine"><option value="append">补充当前文风</option><option value="replace">替换当前文风内容</option></select></label><label>用途<select v-model="usage"><option value="guide">加入主创文风</option><option value="observe">仅观测与测量</option></select></label>
          <p class="stylo-hint">作者自由文风指示继续保留。挂载与卸载用于后续新场景；已开始的交易使用冻结版本。去 AI 味编辑由独立实验开关控制。</p>
          <details open><summary>待挂载的作品文风预览</summary><pre>{{ combined || '当前文风内容为空。' }}</pre></details>
          <div class="stylo-actions"><button class="stylo-primary" :disabled="busy || !selectedVersion || dirty" @click="desk.mount(true)">挂载所选版本</button><button :disabled="busy || !workbench?.mount.enabled" @click="desk.mount(false)">卸载计量文风</button><button :disabled="!fragment" @click="exportVersion">导出结构化文本</button></div>
          <details v-if="workbench?.mount.enabled"><summary>当前生效版本与内容</summary><code>{{ workbench.mount.version_id }} · {{ workbench.mount.content_sha256 }}</code><pre>{{ workbench.mount.fragment_text }}</pre></details>
          <h3>正文测量</h3><label>原稿或实验改稿<textarea v-model="text" rows="7" placeholder="粘贴需要测量的正文，选择保存的参数版本进行比较。" /></label><label>可选的正文依存原树<textarea v-model="candidateTree" rows="2" placeholder="与当前正文逐字匹配，使用同一标注器和体系。" /></label><button :disabled="busy || !text.trim()" @click="desk.measure">测量正文</button>
          <div v-if="report" class="stylo-table-wrap"><table><thead><tr><th>指标</th><th>目标</th><th>正文实测</th><th>区间距离</th></tr></thead><tbody><tr v-for="row in report.targets || []" :key="row.id"><td>{{ row.label }}{{ row.enabled ? '' : ' · 观测' }}</td><td>{{ row.min }}–{{ row.max }}<small>{{ row.unit }}</small></td><td>{{ value(row.observed) }}</td><td>{{ value(row.distance) }}</td></tr></tbody></table><details><summary>统计详情与缺测</summary><pre>{{ JSON.stringify(report, null, 2) }}</pre></details></div>
        </section>
      </main>
    </div>
  </section>
</template>
