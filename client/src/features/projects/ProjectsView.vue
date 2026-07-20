<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ArrowRight, BookPlus, Check, FolderOpen, LocateFixed, Sparkles } from "lucide-vue-next";
import { api } from "@/services/api";
import { DesktopBridge } from "@/services/desktopBridge";
import { friendlyError, useAppStore } from "@/stores/app";

const store = useAppStore();
const router = useRouter();
const busy = ref(false);
const feedback = ref("");
const advancedPaths = ref(!DesktopBridge.isDesktop);
const createForm = reactive({
  title: "",
  parent_directory: localStorage.getItem("arcvellum.createDirectory") || "",
  folder_name: "",
  work_type: "novel",
  target_length: 300000,
  premise: "",
  genre: "",
});
const openPath = ref(localStorage.getItem("arcvellum.openDirectory") || "");

const targetLabel = computed(() =>
  createForm.target_length >= 10000 ? `${Math.round(createForm.target_length / 10000)} 万字` : `${createForm.target_length} 字`,
);

async function chooseCreateDirectory(): Promise<void> {
  const result = await DesktopBridge.selectDirectory(createForm.parent_directory);
  if (result.path) {
    createForm.parent_directory = result.path;
    localStorage.setItem("arcvellum.createDirectory", result.path);
  }
}

async function chooseOpenDirectory(): Promise<void> {
  const result = await DesktopBridge.selectDirectory(openPath.value);
  if (result.path) openPath.value = result.path;
}

async function createProject(): Promise<void> {
  feedback.value = "";
  busy.value = true;
  try {
    const check = await api<{ valid: boolean; conflicts: string[]; warnings: string[] }>("/projects/validate-location", {
      method: "POST",
      body: JSON.stringify({
        mode: "create",
        parent_directory: createForm.parent_directory,
        folder_name: createForm.folder_name || createForm.title,
      }),
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
    const check = await api<{ valid: boolean; conflicts: string[] }>("/projects/validate-location", {
      method: "POST",
      body: JSON.stringify({ mode: "open", project_root: openPath.value }),
    });
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
  await router.push("/overview");
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

        <div class="directory-picker">
          <div><span>保存位置</span><strong>{{ createForm.parent_directory || "选择一个常用文件夹" }}</strong></div>
          <button v-if="DesktopBridge.isDesktop" type="button" class="secondary-button" @click="chooseCreateDirectory">
            <LocateFixed :size="17" />选择位置
          </button>
          <button v-else type="button" class="text-button" @click="advancedPaths = !advancedPaths">手动填写</button>
        </div>
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
        <button v-if="DesktopBridge.isDesktop" class="folder-drop" type="button" @click="chooseOpenDirectory">
          <FolderOpen :size="28" /><strong>选择作品文件夹</strong><span>{{ openPath || "从电脑中选择" }}</span>
        </button>
        <label v-else class="field"><span>作品文件夹</span><input v-model.trim="openPath" placeholder="输入已有作品目录" /></label>
        <button class="secondary-button wide" :disabled="busy || !openPath" @click="openProject">打开作品<ArrowRight :size="16" /></button>
        <div class="trust-note"><Check :size="15" /><span>不会移动、复制或改名你的作品文件夹。</span></div>
      </aside>
    </section>

    <section class="recent-works">
      <header><div><span class="eyebrow">最近作品</span><h2>继续上次停下的地方</h2></div><span>{{ store.projects.length }} 部作品</span></header>
      <div v-if="store.projects.length" class="work-shelf">
        <button v-for="project in store.projects" :key="project.path" class="work-spine" @click="continueProject(project.path)">
          <span class="spine-status">{{ project.status || "创作中" }}</span>
          <strong>{{ project.title }}</strong>
          <p>{{ project.premise || "尚未填写作品简介" }}</p>
          <div><span>{{ project.genre || project.work_type }}</span><span>{{ Math.round((project.target_length || 0) / 10000) }} 万字目标</span></div>
        </button>
      </div>
      <div v-else class="empty-shelf">第一部作品建立后，会固定在这里。</div>
    </section>
  </div>
</template>
