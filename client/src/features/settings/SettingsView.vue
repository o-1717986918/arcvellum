<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Bot, Check, CloudCog, Download, FileJson, FolderCog, Info, KeyRound, RefreshCw, RotateCcw, Settings, Unplug, WandSparkles } from "lucide-vue-next";
import { api, authorizedFetch } from "@/services/api";
import { DesktopBridge } from "@/services/desktopBridge";
import { formatCount } from "@/services/presentation";
import { checkForUpdate, installUpdate, restartApplication, type UpdateCheckResult } from "@/services/updater";
import { useAppStore } from "@/stores/app";

const store = useAppStore();
const credential = reactive({ provider_id: "deepseek", credential: "" });
const selectedModels = reactive({ worker: "", advisor: "", steward: "" });
const busy = ref(false);
const feedback = ref("");
const section = ref<"connections" | "about">("connections");
const appInfo = ref<Record<string, any> | null>(null);
const updateResult = ref<UpdateCheckResult | null>(null);
const updateProgress = ref({ downloaded: 0, total: 0 });
const projectsRoot = ref("");

const providers = computed(() => store.modelCatalog?.providers || []);
const connectedProviders = computed(() => providers.value.filter((provider) => provider.connected));
const models = computed(() => connectedProviders.value.flatMap((provider) => provider.models || []));

onMounted(async () => {
  try {
    await store.loadModelCatalog();
    syncSelectedModels();
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "模型目录暂时不可用。";
  }
  appInfo.value = await api<Record<string, any>>("/application/info").catch(() => null);
  projectsRoot.value = String(appInfo.value?.paths?.projects_root || "");
});

async function refresh(): Promise<void> {
  busy.value = true;
  feedback.value = "";
  try {
    await store.loadModelCatalog(true);
    syncSelectedModels();
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "刷新失败。";
  } finally {
    busy.value = false;
  }
}

async function connectProvider(): Promise<void> {
  busy.value = true;
  feedback.value = "";
  try {
    await api("/model-connections/opencode/credential", {
      method: "PUT",
      body: JSON.stringify(credential),
    });
    credential.credential = "";
    await store.loadModelCatalog();
    feedback.value = "模型服务已经连接。";
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "连接失败。";
  } finally {
    busy.value = false;
  }
}

async function saveModel(role: "worker" | "advisor" | "steward"): Promise<void> {
  if (!selectedModels[role]) return;
  await api("/model-connections/opencode/model", {
    method: "PUT",
    body: JSON.stringify({ model: selectedModels[role], role }),
  });
  const labels = { worker: "正文与审查", advisor: "创作顾问", steward: "自动审批" };
  feedback.value = `${labels[role]}模型已经更新。`;
  await store.loadModelCatalog();
  syncSelectedModels();
}

function syncSelectedModels(): void {
  const fallback = store.modelCatalog?.selected_model || "";
  const values: Partial<Record<"worker" | "advisor" | "steward", string>> = store.modelCatalog?.selected_models || {};
  selectedModels.worker = values.worker || fallback;
  selectedModels.advisor = values.advisor || fallback;
  selectedModels.steward = values.steward || fallback;
}

async function disconnect(providerId: string): Promise<void> {
  busy.value = true;
  try {
    await api(`/model-connections/opencode/credential/${encodeURIComponent(providerId)}`, { method: "DELETE" });
    await store.loadModelCatalog();
  } finally {
    busy.value = false;
  }
}

async function checkUpdate(): Promise<void> {
  busy.value = true;
  feedback.value = "";
  try {
    updateResult.value = await checkForUpdate();
    feedback.value = !updateResult.value.supported
      ? "更新检查只在 ArcVellum 桌面客户端中可用。"
      : updateResult.value.available
        ? `发现 ArcVellum ${updateResult.value.version}。`
        : "当前已经是最新版本。";
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "暂时无法检查更新。";
  } finally {
    busy.value = false;
  }
}

async function applyUpdate(): Promise<void> {
  if (!updateResult.value) return;
  busy.value = true;
  try {
    await installUpdate(updateResult.value, (downloaded, total) => (updateProgress.value = { downloaded, total }));
    await restartApplication();
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "更新没有完成，当前版本仍可继续使用。";
    busy.value = false;
  }
}

async function exportDiagnostics(): Promise<void> {
  busy.value = true;
  try {
    const response = await authorizedFetch("/application/diagnostics/export", { method: "POST" });
    if (!response.ok) throw new Error("诊断报告没有生成。 ");
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const name = disposition.match(/filename="?([^";]+)"?/)?.[1] || "arcvellum-diagnostic.json";
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    URL.revokeObjectURL(url);
    feedback.value = "脱敏诊断报告已经导出。";
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "诊断报告没有生成。";
  } finally {
    busy.value = false;
  }
}

async function chooseProjectsRoot(): Promise<void> {
  const result = await DesktopBridge.selectDirectory(projectsRoot.value);
  if (result.path) projectsRoot.value = result.path;
}

async function saveProjectsRoot(): Promise<void> {
  if (!projectsRoot.value.trim()) return;
  busy.value = true;
  try {
    const result = await api<{ projects_root: string }>("/projects/default-location", {
      method: "PUT",
      body: JSON.stringify({ projects_root: projectsRoot.value }),
    });
    projectsRoot.value = result.projects_root;
    feedback.value = "默认作品库已更新，只影响以后新建的作品。";
    appInfo.value = await api<Record<string, any>>("/application/info");
  } finally {
    busy.value = false;
  }
}

function resetInterface(): void {
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith("arcvellum.") && key !== "arcvellum.currentProject") localStorage.removeItem(key);
  }
  feedback.value = "界面偏好已经恢复默认。";
}

function pathValue(key: string): string {
  return String(appInfo.value?.paths?.[key] || "尚未确定");
}
</script>

<template>
  <div class="view settings-view">
    <section class="overview-header settings-header">
      <div><span class="eyebrow">设置</span><h1>让创作能力保持清楚、可控。</h1><p>模型负责思考与写作，ArcVellum 负责项目、门禁和交付。密钥不会写入作品。</p></div>
      <button class="secondary-button" :disabled="busy" @click="refresh"><RefreshCw :size="17" />刷新连接</button>
    </section>

    <p v-if="feedback" class="inline-feedback">{{ feedback }}</p>

    <div class="settings-tabs" role="tablist">
      <button :class="{ active: section === 'connections' }" @click="section = 'connections'"><CloudCog :size="16" />连接与模型</button>
      <button :class="{ active: section === 'about' }" @click="section = 'about'"><Info :size="16" />关于 ArcVellum</button>
    </div>

    <template v-if="section === 'connections'">
    <section class="connection-summary">
      <div><span class="summary-symbol"><Bot :size="21" /></span><p>可用模型<strong>{{ formatCount(store.modelCatalog?.available_model_count) }}</strong></p></div>
      <div><span class="summary-symbol"><CloudCog :size="21" /></span><p>已连接服务<strong>{{ connectedProviders.length }}</strong></p></div>
      <div><span class="summary-symbol"><WandSparkles :size="21" /></span><p>正文模型<strong>{{ store.modelCatalog?.selected_models?.worker || store.modelCatalog?.selected_model || "尚未选择" }}</strong></p></div>
    </section>

    <div class="settings-grid">
      <section class="settings-section">
        <header><span class="section-icon"><WandSparkles :size="18" /></span><div><h2>按工作选择模型</h2><p>高质量正文、快速对话和日常审批可以各用合适的模型。</p></div></header>
        <div class="role-model-list">
          <article v-for="role in ([
            { id: 'worker', title: '正文与审查', text: '负责写作、推演、修订和正式审查。' },
            { id: 'advisor', title: '创作顾问', text: '优先选择响应快、对话自然的模型。' },
            { id: 'steward', title: '自动审批', text: '在授权范围内比较候选方向。' },
          ] as const)" :key="role.id">
            <div><strong>{{ role.title }}</strong><p>{{ role.text }}</p></div>
            <select v-model="selectedModels[role.id]"><option value="">先连接一个模型服务</option><option v-for="model in models" :key="model.qualified_id" :value="model.qualified_id">{{ model.name }} · {{ model.qualified_id }}</option></select>
            <button class="icon-button" :disabled="!selectedModels[role.id]" title="保存这个角色的模型" @click="saveModel(role.id)"><Check :size="15" /></button>
          </article>
        </div>

        <div class="provider-list">
          <article v-for="provider in providers" :key="provider.id" :class="{ connected: provider.connected }">
            <span class="provider-state"><Check v-if="provider.connected" :size="14" /><span v-else></span></span>
            <div><strong>{{ provider.name }}</strong><p>{{ provider.connected ? `${provider.model_count} 个模型可用` : "尚未连接" }}</p></div>
            <button v-if="provider.connected && provider.id !== 'opencode'" class="icon-button" title="断开连接" @click="disconnect(provider.id)"><Unplug :size="16" /></button>
          </article>
        </div>
      </section>

      <section class="settings-section connection-form-section">
        <header><span class="section-icon iris"><KeyRound :size="18" /></span><div><h2>连接模型服务</h2><p>密钥只交给本机 OpenCode 凭证存储。</p></div></header>
        <form @submit.prevent="connectProvider">
          <label class="field"><span>服务</span><select v-model="credential.provider_id"><option value="deepseek">DeepSeek</option><option value="anthropic">Anthropic</option><option value="openai">OpenAI compatible</option><option value="google">Google</option></select></label>
          <label class="field"><span>API 密钥</span><input v-model="credential.credential" required type="password" autocomplete="new-password" placeholder="输入后不会再次显示" /></label>
          <button class="primary-button wide" :disabled="busy || !credential.credential"><KeyRound :size="16" />建立连接</button>
        </form>
        <p class="privacy-note"><Settings :size="15" />界面、普通日志和作品文件都不会回显密钥原文。</p>
      </section>
    </div>

    <section class="bootstrap-status-panel">
      <header><div><span class="eyebrow">启动与恢复</span><h2>这次启动发生了什么</h2></div><span>{{ store.bootstrap?.phase === 'ready' ? '全部就绪' : '可降级运行' }}</span></header>
      <div class="bootstrap-status-list">
        <div v-for="step in store.bootstrap?.steps" :key="step.id" :data-state="step.status">
          <span class="status-mark"><Check v-if="step.status === 'ready'" :size="13" /></span>
          <p><strong>{{ step.label }}</strong><small>{{ step.detail }}</small></p>
        </div>
      </div>
    </section>
    </template>

    <template v-else>
      <section class="about-hero">
        <div class="about-mark"><span></span><span></span><span></span></div>
        <div><span class="eyebrow">长篇文学创作观测台</span><h2>ArcVellum</h2><p>{{ appInfo?.privacy }}</p></div>
        <div class="version-stamp"><span>版本</span><strong>{{ appInfo?.version || '读取中' }}</strong><small>{{ appInfo?.build_number }}</small></div>
      </section>

      <div class="about-grid">
        <section class="settings-section update-section">
          <header><span class="section-icon"><RefreshCw :size="18" /></span><div><h2>应用更新</h2><p>{{ appInfo?.release_channel === 'preview' ? '预览通道' : '稳定通道' }} · 更新包经过签名验证</p></div></header>
          <div v-if="updateResult?.available" class="available-update"><strong>ArcVellum {{ updateResult.version }}</strong><p>{{ updateResult.body || '新版本已经准备好。' }}</p></div>
          <div v-if="updateProgress.total" class="update-progress"><span :style="{ width: `${Math.min(100, updateProgress.downloaded / updateProgress.total * 100)}%` }"></span></div>
          <div class="button-row">
            <button class="secondary-button" :disabled="busy" @click="checkUpdate"><RefreshCw :size="16" />检查更新</button>
            <button v-if="updateResult?.available" class="primary-button" :disabled="busy" @click="applyUpdate"><Download :size="16" />下载并安装</button>
          </div>
          <small v-if="!DesktopBridge.isDesktop">浏览器开发模式不会安装桌面更新。</small>
        </section>

        <section class="settings-section runtime-section">
          <header><span class="section-icon iris"><Info :size="18" /></span><div><h2>运行信息</h2><p>用于确认当前客户端与创作能力。</p></div></header>
          <dl>
            <div><dt>文学工程内核</dt><dd>{{ appInfo?.engine?.protocol_version || '未知' }}</dd></div>
            <div><dt>OpenCode</dt><dd>{{ appInfo?.opencode?.version || (appInfo?.opencode?.installed ? '已安装' : '未安装') }}</dd></div>
            <div><dt>默认模型</dt><dd>{{ appInfo?.current_model || '尚未选择' }}</dd></div>
            <div><dt>许可证</dt><dd>{{ appInfo?.license || 'MIT' }}</dd></div>
          </dl>
        </section>
      </div>

      <section class="data-locations">
        <header><div><span class="eyebrow">本地数据</span><h2>ArcVellum 把内容放在哪里</h2></div></header>
        <dl>
          <div><dt>默认作品库</dt><dd>{{ pathValue('projects_root') }}</dd></div>
          <div><dt>应用数据</dt><dd>{{ pathValue('application_data') }}</dd></div>
          <div><dt>日志</dt><dd>{{ pathValue('logs') }}</dd></div>
          <div><dt>配置</dt><dd>{{ pathValue('configuration') }}</dd></div>
        </dl>
        <div class="projects-root-editor">
          <label class="field"><span>以后新建作品的保存位置</span><input v-model.trim="projectsRoot" /></label>
          <button v-if="DesktopBridge.isDesktop" class="secondary-button" @click="chooseProjectsRoot"><FolderCog :size="16" />选择文件夹</button>
          <button class="primary-button" :disabled="busy || !projectsRoot" @click="saveProjectsRoot"><Check :size="16" />设为默认</button>
        </div>
        <p class="location-note">更改默认位置不会移动现有作品，也不会改变它们在最近作品中的登记。</p>
      </section>

      <section class="maintenance-actions">
        <button class="secondary-button" :disabled="busy" @click="exportDiagnostics"><FileJson :size="16" />导出脱敏诊断报告</button>
        <button class="secondary-button" @click="resetInterface"><RotateCcw :size="16" />恢复界面默认设置</button>
        <button class="secondary-button" @click="restartApplication"><RefreshCw :size="16" />重新启动应用</button>
      </section>
    </template>
  </div>
</template>
