<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { CheckCircle2, Download, FileText, PackageOpen, RefreshCw, ShieldCheck } from "lucide-vue-next";
import { api, query } from "@/services/api";
import { asList, displayValue } from "@/services/presentation";
import { useAppStore } from "@/stores/app";

const store = useAppStore();
const preparing = ref(false);
const message = ref("");
const ready = computed(() => store.delivery?.status === "ready");
const blockers = computed(() => asList<Record<string, unknown>>(store.delivery?.blockers));

onMounted(() => store.loadDelivery());

function downloadUrl(path: string): string {
  return `/project/delivery/download?${query({ project_root: store.currentProjectPath, path })}`;
}

function fileSize(size?: number): string {
  if (!size) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

async function prepareDelivery(): Promise<void> {
  preparing.value = true;
  message.value = "";
  try {
    const result = await api<Record<string, unknown>>("/worker/run", {
      method: "POST",
      body: JSON.stringify({ project_root: store.currentProjectPath, route: "export-and-release", runtime: "opencode" }),
    });
    message.value = String(result.message || "交付任务已经启动；完成后正式文件会出现在下方。");
    await Promise.allSettled([store.loadDelivery(), store.loadDashboard(), store.loadAgentObservability(), store.loadAutopilotStatus()]);
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : "暂时无法准备交付。";
  } finally {
    preparing.value = false;
  }
}
</script>

<template>
  <div class="view delivery-view">
    <section class="delivery-hero">
      <div>
        <span class="eyebrow">正式交付</span>
        <h1>把作品交成可以阅读、保存和发布的文件。</h1>
        <p>只有通过门禁的正式正文会进入交付包。审查记录、设定变更和工作流程会被留在项目中。</p>
        <div class="delivery-actions">
          <button class="primary-button" :disabled="preparing" @click="prepareDelivery"><PackageOpen :size="17" />{{ preparing ? "正在准备……" : "准备正式交付" }}</button>
          <button class="secondary-button" @click="store.loadDelivery"><RefreshCw :size="17" />刷新</button>
        </div>
        <small v-if="message">{{ message }}</small>
      </div>
      <div class="delivery-seal" :class="{ ready }">
        <ShieldCheck :size="32" />
        <strong>{{ ready ? "可交付" : "准备中" }}</strong>
        <span>{{ store.delivery?.files?.length || 0 }} 个正式文件</span>
      </div>
    </section>

    <section class="delivery-ledger">
      <header><div><span class="eyebrow">交付文件</span><h2>已经形成的正式版本</h2></div><span>{{ store.delivery?.files?.length || 0 }} 项</span></header>
      <div v-if="store.delivery?.files?.length" class="delivery-files">
        <article v-for="file in store.delivery.files" :key="file.path">
          <span class="file-icon"><FileText :size="22" /></span>
          <div><strong>{{ file.name || file.path.split('/').at(-1) }}</strong><p>{{ (file.format || file.path.split('.').at(-1) || '文件').toUpperCase() }} {{ fileSize(file.size) }}</p></div>
          <a class="icon-button download-button" :href="downloadUrl(file.path)" title="下载"><Download :size="18" /></a>
        </article>
      </div>
      <div v-else class="delivery-empty"><PackageOpen :size="30" /><strong>还没有正式交付文件</strong><p>完成正文审查和导出路线后，文件会出现在这里。</p></div>
    </section>

    <section class="delivery-checks">
      <div class="check-intro"><span class="eyebrow">交付前检查</span><h2>作品会经过哪些确认</h2></div>
      <div class="check-list">
        <div><CheckCircle2 :size="18" /><span><strong>只收录正式正文</strong><small>候选稿和工程标记不会混入。</small></span></div>
        <div><CheckCircle2 :size="18" /><span><strong>审查证据完整</strong><small>未通过门禁的场景无法晋升。</small></span></div>
        <div><CheckCircle2 :size="18" /><span><strong>版式与目录可读</strong><small>DOCX 与 Markdown 按作品结构组织。</small></span></div>
      </div>
      <div v-if="blockers.length" class="blocker-list">
        <strong>仍需处理</strong>
        <p v-for="(blocker, index) in blockers" :key="index">{{ displayValue(blocker.message || blocker) }}</p>
      </div>
    </section>
  </div>
</template>
