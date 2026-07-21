<script setup lang="ts">
import { computed } from "vue";
import { BookOpenText, Bot, CircleHelp, Compass, FileDown, Gauge, RotateCw, ShieldCheck, Sparkles } from "lucide-vue-next";
import { useAppStore } from "@/stores/app";
import { api } from "@/services/api";

const store = useAppStore();
const phase = computed(() => store.bootstrap?.phase === "blocked" ? "有一项启动条件需要处理" : store.bootstrap?.phase === "degraded" ? "工作台可用，部分创作连接尚未就绪" : "工作台运行正常");

async function exportDiagnostics(): Promise<void> {
  await api("/application/diagnostics/export", { method: "POST" });
  store.notice = "诊断报告已生成。";
}

function replayTour(): void {
  window.dispatchEvent(new CustomEvent("arcvellum:onboarding"));
}
</script>

<template>
  <div class="view help-view">
    <header class="help-hero"><CircleHelp :size="30" /><div><span class="eyebrow">使用帮助</span><h1>现在不必先学会整个系统</h1><p>ArcVellum 会把下一步准备成明确任务。你负责作品方向，状态机会守住资料、审查和交付。</p></div></header>
    <section class="help-current"><span></span><div><strong>{{ phase }}</strong><p>{{ store.currentProject ? `当前作品：${store.currentProject.title}` : "先建立或打开一部作品。" }}</p></div><div class="help-current-actions"><button class="secondary-button" @click="replayTour"><Compass :size="15" />观看界面引导</button><button class="secondary-button" @click="store.initialize"><RotateCw :size="15" />重新检查</button></div></section>
    <div class="help-grid">
      <article><Sparkles :size="20" /><h2>第一次使用</h2><p>建立作品，写下创作方向，连接一个 Agent 与模型，然后在创作总控准备下一项任务。无需手工管理项目文件。</p></article>
      <article><Gauge :size="20" /><h2>为什么会停住</h2><p>分支选择、设定写回、修订方向和最终交付会等待明确决定。阻塞不是故障，而是作品完整性正在被保护。</p></article>
      <article><Bot :size="20" /><h2>Agent 与模型</h2><p>Agent 执行受控任务，模型提供创作判断。它们只能读取任务包允许的资料，正式产物仍要经过验收与晋升。</p></article>
      <article><BookOpenText :size="20" /><h2>边写边读</h2><p>进入“阅读”即可按卷章连续阅读已经晋升的正文。候选稿、审查备注和项目标记不会混入阅读内容。</p></article>
      <article><ShieldCheck :size="20" /><h2>你的数据在哪里</h2><p>作品默认保存在本机作品库。连接第三方模型时，当前任务所需材料会交给对应提供商，具体政策由提供商决定。</p></article>
      <article><FileDown :size="20" /><h2>交付与备份</h2><p>只有通过正式门禁的正文会进入交付。更新应用不会删除作品；卸载前仍建议备份作品库。</p></article>
    </div>
    <section class="help-troubleshooting"><div><span class="eyebrow">连接或启动异常</span><h2>页面没有进入工作台时</h2><ol><li>先点“重新检查”，让本地服务重新建立会话。</li><li>确认安全软件没有阻止 ArcVellum 本地服务。</li><li>导出诊断报告，再附到问题反馈中。</li></ol></div><button class="secondary-button" @click="exportDiagnostics"><FileDown :size="16" />生成诊断报告</button></section>
  </div>
</template>
