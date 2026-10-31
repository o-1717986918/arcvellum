<script setup lang="ts">
import { computed, ref } from "vue";
import { BookOpenText, Bot, CircleHelp, Compass, FileDown, Gauge, Radio, RotateCw, ShieldCheck, Sparkles } from "lucide-vue-next";
import { settingsClient } from "@/features/settings/services/settingsClient";
import { useAppStore } from "@/stores/app";

import { saveResponseFile } from "@/services/saveResponseFile";
const store = useAppStore();
const exporting = ref(false);
const phase = computed(() => store.bootstrap?.phase === "blocked" ? "有一项启动条件需要处理" : store.bootstrap?.phase === "degraded" ? "工作台可用，部分创作连接尚未就绪" : "工作台运行正常");

async function exportDiagnostics(): Promise<void> {
  exporting.value = true;
  try {
    await saveResponseFile(await settingsClient.exportDiagnostics(), "arcvellum-diagnostic.json");
    store.notice = "诊断报告已交给下载器。";
  } catch (cause) { store.error = cause instanceof Error ? cause.message : "诊断报告暂未生成，请重试。"; }
  finally { exporting.value = false; }
}

function replayTour(): void {
  window.dispatchEvent(new CustomEvent("arcvellum:onboarding"));
}
</script>

<template>
  <div class="view help-view">
    <header class="help-hero"><CircleHelp :size="30" /><div><span class="eyebrow">使用帮助</span><h1>使用 ArcVellum</h1><p>你可以用自然语言管理项目，也可以随时打开正文、档案和创作现场核对结果。</p></div></header>
    <section class="help-current"><span></span><div><strong>{{ phase }}</strong><p>{{ store.currentProject ? `当前作品：${store.currentProject.title}` : "先建立或打开一部作品。" }}</p></div><div class="help-current-actions"><button class="secondary-button" @click="replayTour"><Compass :size="15" />观看界面引导</button><button class="secondary-button" @click="store.recheckConnection"><RotateCw :size="15" />重新检查</button></div></section>
    <section class="help-shortcuts"><strong>工作室快捷操作</strong><span><kbd>Ctrl / ⌘ K</kbd> 查找功能与会话</span><span><kbd>Enter</kbd> 发送消息</span><span><kbd>Shift Enter</kbd> 换行</span><span><kbd>Esc</kbd> 退出星仪或关闭面板</span></section>
    <div class="help-grid">
      <article><Sparkles :size="20" /><h2>第一次使用</h2><p>建立作品，写下创作方向，连接一个 Agent 与模型，然后在对话中描述接下来的创作目标。无需手工管理项目文件。</p></article>
      <article><Gauge :size="20" /><h2>为什么会停住</h2><p>缺少项目资料、模型连接失败或文学内核校验未通过时会暂停。Project Agent 会先尝试修正，再把真正的阻断原因告诉你。</p></article>
      <article><Bot :size="20" /><h2>Agent 与模型</h2><p>Agent 执行受控任务，模型提供创作判断。它们只能读取任务包允许的资料，正式产物仍要经过验收与晋升。</p></article>
      <article><BookOpenText :size="20" /><h2>边写边读</h2><p>进入“阅读”即可按卷章连续阅读已经晋升的正文。候选稿、审查备注和项目标记不会混入阅读内容。</p></article>
      <article><Radio :size="20" /><h2>创作现场</h2><p>从左栏打开“创作现场”，可以实时查看候选正文、审查轨迹、Agent 会话和修订差异。临时文字完成晋升后才会进入正式阅读器。</p></article>
      <article><ShieldCheck :size="20" /><h2>你的数据在哪里</h2><p>作品默认保存在本机作品库。未发送的消息与新建作品草稿保存在当前设备，刷新后可继续填写；清除应用或浏览器数据会移除这些草稿。连接模型时，任务所需材料会交给对应提供商。</p></article>
      <article><FileDown :size="20" /><h2>交付与备份</h2><p>只有通过正式门禁的正文会进入交付。更新应用不会删除作品；卸载前仍建议备份作品库。</p></article>
    </div>
    <section class="help-troubleshooting"><div><span class="eyebrow">连接或启动异常</span><h2>页面没有进入工作台时</h2><ol><li>先点“重新检查”，让本地服务重新建立会话。</li><li>确认安全软件没有阻止 ArcVellum 本地服务。</li><li>导出诊断报告，再附到问题反馈中。</li></ol></div><button class="secondary-button" :disabled="exporting" @click="exportDiagnostics"><FileDown :size="16" />生成诊断报告</button></section>
  </div>
</template>
