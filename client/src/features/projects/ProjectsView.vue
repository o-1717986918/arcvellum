<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ArrowRight, BookOpenText, BookPlus, Check, Copy, FolderOpen, LocateFixed, ShieldCheck, Sparkles } from "lucide-vue-next";
import { projectsClient } from "@/features/projects/services/projectsClient";
import { DesktopBridge } from "@/services/desktopBridge";
import { friendlyError, useAppStore } from "@/stores/app";
import type { DemoBundleSummary } from "@/types/api";

const store = useAppStore();
const router = useRouter();
const busy = ref(false);
const directoryBusy = ref<"create" | "open" | "">("");
const feedback = ref("");
const demos = ref<DemoBundleSummary[]>([]);
const advancedPaths = ref(!DesktopBridge.isDesktop);
const manualOpenPath = ref(!DesktopBridge.isDesktop);
const createForm = reactive({
  title: "",
  parent_directory: localStorage.getItem("arcvellum.createDirectory") || "",
  folder_name: "",
  work_type: "novel",
  target_length: 300000,
  target_chapters: 0,
  target_scenes: 0,
  premise: "",
  genre: "",
});
const openPath = ref(localStorage.getItem("arcvellum.openDirectory") || "");

onMounted(async () => {
  try {
    const [catalog, location] = await Promise.all([
      projectsClient.demos(),
      projectsClient.defaultLocation(),
    ]);
    demos.value = catalog.items || [];
    if (!createForm.parent_directory) createForm.parent_directory = location.projects_root || "";
  } catch {
    advancedPaths.value = true;
  }
});

const primaryDemo = computed(() => demos.value.find((item) => item.available) || null);
const installedDemo = computed(() =>
  primaryDemo.value
    ? store.projects.find((item) => item.is_demo && item.demo_work_id === primaryDemo.value?.work_id) || null
    : null,
);

const targetLabel = computed(() =>
  createForm.target_length >= 10000 ? `${Math.round(createForm.target_length / 10000)} 万字` : `${createForm.target_length} 字`,
);

async function chooseCreateDirectory(): Promise<void> {
  feedback.value = "";
  directoryBusy.value = "create";
  try {
    const result = await DesktopBridge.selectDirectory(createForm.parent_directory);
    if (!result.supported) advancedPaths.value = true;
    if (result.path) {
      createForm.parent_directory = result.path;
      localStorage.setItem("arcvellum.createDirectory", result.path);
    }
  } catch (cause) {
    advancedPaths.value = true;
    feedback.value = friendlyError(cause, "目录选择器没有成功打开，请手动填写保存位置。 ");
  } finally {
    directoryBusy.value = "";
  }
}

async function chooseOpenDirectory(): Promise<void> {
  feedback.value = "";
  directoryBusy.value = "open";
  try {
    const result = await DesktopBridge.selectDirectory(openPath.value);
    if (!result.supported) manualOpenPath.value = true;
    if (result.path) openPath.value = result.path;
  } catch (cause) {
    manualOpenPath.value = true;
    feedback.value = friendlyError(cause, "目录选择器没有成功打开，请手动填写作品位置。 ");
  } finally {
    directoryBusy.value = "";
  }
}

async function createProject(): Promise<void> {
  feedback.value = "";
  busy.value = true;
  try {
    const check = await projectsClient.validateLocation({
      mode: "create",
      parent_directory: createForm.parent_directory,
      folder_name: createForm.folder_name || createForm.title,
    });
    if (!check.valid) throw new Error(check.conflicts.join(" "));
    await store.createProject({ ...createForm });
    localStorage.setItem("arcvellum.createDirectory", createForm.parent_directory);
    await router.push("/overview");
  } catch (cause) {
    feedback.value = friendlyError(cause, "作品暂时没有建立，请检查保存位置。 ");
  } finally {
    busy.value = false;
  }
}

async function openProject(): Promise<void> {
  feedback.value = "";
  busy.value = true;
  try {
    const check = await projectsClient.validateLocation({ mode: "open", project_root: openPath.value });
    if (!check.valid) throw new Error(check.conflicts.join(" "));
    await store.openProject(openPath.value);
    localStorage.setItem("arcvellum.openDirectory", openPath.value);
    await router.push("/overview");
  } catch (cause) {
    feedback.value = friendlyError(cause, "这里没有找到可以打开的 ArcVellum 作品。 ");
  } finally {
    busy.value = false;
  }
}

async function continueProject(path: string): Promise<void> {
  store.setCurrentProject(path);
  const project = store.projects.find((item) => item.path === path);
  await router.push(project?.is_demo ? "/reader" : "/overview");
}

async function openOrInstallDemo(): Promise<void> {
  if (!primaryDemo.value || busy.value) return;
  feedback.value = "";
  busy.value = true;
  try {
    const project = installedDemo.value || (await projectsClient.installDemo(primaryDemo.value.bundle_id)).project;
    await store.loadProjects();
    store.setCurrentProject(project.path);
    await router.push("/reader");
  } catch (cause) {
    feedback.value = friendlyError(cause, "演示作品没有成功安装，请检查安装资源是否完整。 ");
  } finally {
    busy.value = false;
  }
}

async function copyDemoForWriting(): Promise<void> {
  if (!primaryDemo.value || busy.value) return;
  feedback.value = "";
  busy.value = true;
  try {
    const demo = installedDemo.value || (await projectsClient.installDemo(primaryDemo.value.bundle_id)).project;
    const stamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 12);
    const response = await projectsClient.cloneDemo({
      project_root: demo.path,
      title: `${primaryDemo.value.title} - 创作副本`,
      folder_name: `${primaryDemo.value.work_id}-editable-${stamp}`,
    });
    await store.loadProjects();
    store.setCurrentProject(response.project.path);
    await router.push("/overview");
  } catch (cause) {
    feedback.value = friendlyError(cause, "演示作品没有成功复制，请换一个保存位置后重试。 ");
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="view projects-view">
    <section class="view-intro project-intro">
      <div>
        <span class="eyebrow">作品起点</span>
        <h1>从一个念头，建立一部能持续生长的长篇。</h1>
        <p>人物、世界、剧情、文风和正文会被放进同一个作品里。你只需要先说清想写什么。</p>
      </div>
      <div class="intro-emblem" aria-hidden="true"><Sparkles :size="24" /><span>ARC</span><i></i><span>VELLUM</span></div>
    </section>

    <p v-if="feedback" class="inline-feedback danger" role="alert">{{ feedback }}</p>

    <section v-if="primaryDemo" class="authorized-demo-band">
      <div class="demo-seal" aria-hidden="true"><BookOpenText :size="26" /><span>授权原作</span></div>
      <div class="demo-copy">
        <span class="eyebrow">随安装版提供的文学工程示范</span>
        <h2>先走进《{{ primaryDemo.title }}》，再决定怎样开始自己的作品。</h2>
        <p>{{ primaryDemo.author }} · {{ primaryDemo.version }}。原文、人物、世界、情节与文风资料在同一工程中呈现；演示母本只读，不会被创作流程改写。</p>
        <div class="demo-trust"><ShieldCheck :size="15" /><span>授权来源可追溯</span><i></i><span>原文未伪装为 AI 生成稿</span><i></i><span>复制后才进入创作模式</span></div>
      </div>
      <div class="demo-actions">
        <button class="primary-button" :disabled="busy" @click="openOrInstallDemo"><BookOpenText :size="17" />{{ installedDemo ? "继续阅读" : "打开演示作品" }}</button>
        <button class="secondary-button" :disabled="busy" @click="copyDemoForWriting"><Copy :size="16" />复制为可编辑作品</button>
      </div>
    </section>

    <section class="project-maker">
      <form class="creation-form" @submit.prevent="createProject">
        <div class="section-heading">
          <span class="section-icon"><BookPlus :size="19" /></span>
          <div><h2>建立新作品</h2><p>先给作品一个方向，细节可以在创作中继续决定。</p></div>
        </div>

        <label class="field field-prominent">
          <span>作品名称</span>
          <input v-model.trim="createForm.title" required placeholder="例如：潮汐档案" autocomplete="off" />
        </label>
        <label class="field">
          <span>最初创作方向</span>
          <textarea v-model.trim="createForm.premise" rows="5" placeholder="这是一部关于什么的作品？你希望读者记住什么？"></textarea>
        </label>
        <div class="field-row three">
          <label class="field"><span>类型</span><input v-model.trim="createForm.genre" placeholder="历史、悬疑、科幻……" /></label>
          <label class="field">
            <span>载体</span>
            <select v-model="createForm.work_type">
              <option value="novel">长篇小说</option><option value="script">剧本</option><option value="pseudo-record">伪记录</option>
            </select>
          </label>
          <label class="field"><span>目标规模 · {{ targetLabel }}</span><input v-model.number="createForm.target_length" type="number" min="1000" step="10000" /></label>
        </div>
        <div class="field-row">
          <label class="field"><span>目标章数（可选）</span><input v-model.number="createForm.target_chapters" type="number" min="0" step="1" placeholder="自动规划" /></label>
          <label class="field"><span>目标场景数（可选）</span><input v-model.number="createForm.target_scenes" type="number" min="0" step="1" placeholder="自动规划" /></label>
        </div>

        <div class="directory-picker">
          <div><span>保存位置</span><strong>{{ createForm.parent_directory || "选择一个常用文件夹" }}</strong></div>
          <button v-if="DesktopBridge.isDesktop" type="button" class="secondary-button" :disabled="Boolean(directoryBusy)" @click="chooseCreateDirectory">
            <LocateFixed :size="17" />{{ directoryBusy === "create" ? "正在打开……" : "选择位置" }}
          </button>
          <button v-else type="button" class="text-button" @click="advancedPaths = !advancedPaths">手动填写</button>
        </div>
        <button v-if="DesktopBridge.isDesktop" type="button" class="text-button path-fallback" @click="advancedPaths = !advancedPaths">
          {{ advancedPaths ? "收起手动路径" : "手动填写路径" }}
        </button>
        <div v-if="advancedPaths" class="field-row">
          <label class="field"><span>保存位置</span><input v-model.trim="createForm.parent_directory" required placeholder="作品的上一级文件夹" /></label>
          <label class="field"><span>目录名（可选）</span><input v-model.trim="createForm.folder_name" placeholder="留空时自动生成" /></label>
        </div>

        <button class="primary-button create-submit" :disabled="busy || !createForm.parent_directory">
          <Sparkles :size="17" />{{ busy ? "正在建立……" : "建立作品" }}<ArrowRight :size="17" />
        </button>
      </form>

      <aside class="open-project-panel">
        <div class="section-heading compact">
          <span class="section-icon"><FolderOpen :size="19" /></span>
          <div><h2>打开已有作品</h2><p>作品留在原来的位置。</p></div>
        </div>
        <button v-if="DesktopBridge.isDesktop" class="folder-drop" type="button" :disabled="Boolean(directoryBusy)" @click="chooseOpenDirectory">
          <FolderOpen :size="28" /><strong>{{ directoryBusy === "open" ? "正在打开……" : "选择作品文件夹" }}</strong><span>{{ openPath || "从电脑中选择" }}</span>
        </button>
        <button v-if="DesktopBridge.isDesktop" type="button" class="text-button path-fallback" @click="manualOpenPath = !manualOpenPath">
          {{ manualOpenPath ? "收起手动路径" : "手动填写路径" }}
        </button>
        <label v-if="manualOpenPath" class="field"><span>作品文件夹</span><input v-model.trim="openPath" placeholder="输入已有作品目录" /></label>
        <button class="secondary-button wide" :disabled="busy || !openPath" @click="openProject">打开作品<ArrowRight :size="16" /></button>
        <div class="trust-note"><Check :size="15" /><span>不会移动、复制或改名你的作品文件夹。</span></div>
      </aside>
    </section>

    <section class="recent-works">
      <header><div><span class="eyebrow">最近作品</span><h2>继续上次停下的地方</h2></div><span>{{ store.projects.length }} 部作品</span></header>
      <div v-if="store.projects.length" class="work-shelf">
        <button v-for="project in store.projects" :key="project.path" class="work-spine" @click="continueProject(project.path)">
          <span class="spine-status">{{ project.is_demo ? "授权演示 · 只读" : (project.status || "创作中") }}</span>
          <strong>{{ project.title }}</strong>
          <p>{{ project.premise || "尚未填写作品简介" }}</p>
          <div><span>{{ project.demo_author || project.genre || project.work_type }}</span><span>{{ project.is_demo ? "按原作实际篇幅" : `${Math.round((project.target_length || 0) / 10000)} 万字目标` }}</span></div>
        </button>
      </div>
      <div v-else class="empty-shelf">第一部作品建立后，会固定在这里。</div>
    </section>
  </div>
</template>
