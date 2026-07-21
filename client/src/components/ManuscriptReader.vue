<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  Bookmark,
  BookmarkCheck,
  BookOpenText,
  ChevronLeft,
  ChevronRight,
  ListTree,
  Maximize2,
  Minimize2,
  Minus,
  Moon,
  Plus,
  Search,
  Sun,
  X,
} from "lucide-vue-next";
import { api, query } from "@/services/api";
import { displayValue } from "@/services/presentation";
import { useAppStore } from "@/stores/app";

const props = withDefaults(
  defineProps<{ items?: Record<string, unknown>[]; compact?: boolean; immersive?: boolean }>(),
  { items: () => [], compact: false, immersive: false },
);
const store = useAppStore();
const index = ref(0);
const expanded = ref(false);
const tocOpen = ref(props.immersive);
const searchOpen = ref(false);
const searchText = ref("");
const searchResults = ref<Record<string, unknown>[]>([]);
const searching = ref(false);
const loading = ref(false);
const body = ref("");
const readingMode = ref<"section" | "continuous">((localStorage.getItem("arcvellum.reader.mode") as "section" | "continuous") || "section");
const continuousStart = ref(0);
const continuousCount = ref(4);
const continuousBodies = ref<Record<string, string>>({});
const readerScroll = ref<HTMLElement | null>(null);
const fontSize = ref(Number(localStorage.getItem("arcvellum.reader.fontSize") || 18));
const lineHeight = ref(Number(localStorage.getItem("arcvellum.reader.lineHeight") || 2));
const theme = ref(localStorage.getItem("arcvellum.reader.theme") || "mineral");
const followProgress = ref(localStorage.getItem("arcvellum.reader.follow") === "true");
const bookmarks = ref<string[]>(JSON.parse(localStorage.getItem("arcvellum.reader.bookmarks") || "[]"));
const newUnitCount = ref(0);
const savedPosition = ref({ unit_id: "", scroll_ratio: 0 });
let positionTimer: number | null = null;

const manifestUnits = computed(() => (store.readerManifest?.units || []) as unknown as Record<string, unknown>[]);
const units = computed(() => (manifestUnits.value.length ? manifestUnits.value : props.items));
const current = computed(() => units.value[index.value] || null);
const currentId = computed(() => String(current.value?.unit_id || current.value?.id || ""));
const paragraphs = computed(() => body.value.split(/\n+/).map((item) => item.trim()).filter(Boolean));
const isBookmarked = computed(() => bookmarks.value.includes(currentId.value));
const continuousUnits = computed(() => units.value.slice(continuousStart.value, continuousStart.value + continuousCount.value));

watch(
  () => units.value.length,
  (length, previous = 0) => {
    if (index.value >= length) index.value = Math.max(0, length - 1);
    if (previous && length > previous) {
      if (followProgress.value) index.value = length - 1;
      else newUnitCount.value += length - previous;
    }
  },
);

watch(currentId, () => void loadCurrent(), { immediate: true });
watch(fontSize, (value) => {
  fontSize.value = Math.min(24, Math.max(15, value));
  localStorage.setItem("arcvellum.reader.fontSize", String(fontSize.value));
});
watch(lineHeight, (value) => localStorage.setItem("arcvellum.reader.lineHeight", String(value)));
watch(theme, (value) => localStorage.setItem("arcvellum.reader.theme", value));
watch(followProgress, (value) => localStorage.setItem("arcvellum.reader.follow", String(value)));
watch(readingMode, (value) => {
  localStorage.setItem("arcvellum.reader.mode", value);
  if (value === "continuous") {
    continuousStart.value = Math.max(0, index.value - 1);
    continuousCount.value = 4;
    void loadContinuous();
  }
});
watch(continuousUnits, () => void loadContinuous());

onMounted(async () => {
  let remembered = localStorage.getItem(`arcvellum.reader.unit.${store.currentProjectPath}`) || "";
  if (store.currentProjectPath) {
    try {
      const state = await api<{ position: { unit_id: string; scroll_ratio: number }; bookmarks: Array<{ unit_id: string }> }>(
        `/reader/state?${query({ project_root: store.currentProjectPath })}`,
      );
      savedPosition.value = state.position || savedPosition.value;
      remembered = state.position?.unit_id || remembered;
      bookmarks.value = (state.bookmarks || []).map((item) => item.unit_id);
    } catch {
      // Local preferences remain a recovery fallback when the sidecar is unavailable.
    }
  }
  const restored = units.value.findIndex((unit) => String(unit.unit_id || unit.id || "") === remembered);
  if (restored >= 0) index.value = restored;
  if (readingMode.value === "continuous") {
    continuousStart.value = Math.max(0, index.value - 1);
    await loadContinuous();
  }
});

onBeforeUnmount(() => {
  if (positionTimer !== null) window.clearTimeout(positionTimer);
});

async function loadCurrent(): Promise<void> {
  const item = current.value;
  if (!item) {
    body.value = "";
    return;
  }
  loading.value = true;
  try {
    body.value = item.unit_id ? await store.loadReaderUnit(String(item.unit_id)) : String(item.body || item.excerpt || "");
    localStorage.setItem(`arcvellum.reader.unit.${store.currentProjectPath}`, currentId.value);
    await nextTick();
    const localProgress = Number(localStorage.getItem(`arcvellum.reader.scroll.${store.currentProjectPath}.${currentId.value}`) || 0);
    const progress = savedPosition.value.unit_id === currentId.value ? savedPosition.value.scroll_ratio : localProgress;
    if (readerScroll.value) readerScroll.value.scrollTop = progress * Math.max(0, readerScroll.value.scrollHeight - readerScroll.value.clientHeight);
  } finally {
    loading.value = false;
  }
}

function goTo(target: number): void {
  index.value = Math.max(0, Math.min(units.value.length - 1, target));
  newUnitCount.value = 0;
  if (readingMode.value === "continuous") {
    if (index.value < continuousStart.value || index.value >= continuousStart.value + continuousCount.value) {
      continuousStart.value = Math.max(0, index.value - 1);
      continuousCount.value = 4;
    }
    void loadContinuous().then(() => nextTick()).then(() => {
      document.getElementById(`reader-unit-${currentId.value}`)?.scrollIntoView({ block: "start", behavior: "smooth" });
    });
  }
}

function rememberScroll(): void {
  const element = readerScroll.value;
  if (!element || !currentId.value) return;
  const total = Math.max(1, element.scrollHeight - element.clientHeight);
  const ratio = element.scrollTop / total;
  localStorage.setItem(`arcvellum.reader.scroll.${store.currentProjectPath}.${currentId.value}`, String(ratio));
  if (readingMode.value === "continuous" && element.scrollHeight - element.scrollTop - element.clientHeight < 360) void expandContinuous();
  if (positionTimer !== null) window.clearTimeout(positionTimer);
  positionTimer = window.setTimeout(() => {
    if (!store.currentProjectPath) return;
    void api("/reader/position", {
      method: "PUT",
      body: JSON.stringify({ project_root: store.currentProjectPath, unit_id: currentId.value, scroll_ratio: ratio }),
    });
  }, 350);
}

async function toggleBookmark(): Promise<void> {
  const id = currentId.value;
  if (!id) return;
  bookmarks.value = isBookmarked.value ? bookmarks.value.filter((item) => item !== id) : [...bookmarks.value, id];
  localStorage.setItem("arcvellum.reader.bookmarks", JSON.stringify(bookmarks.value));
  if (store.currentProjectPath) {
    await api("/reader/bookmark", {
      method: "PUT",
      body: JSON.stringify({ project_root: store.currentProjectPath, unit_id: id, enabled: bookmarks.value.includes(id) }),
    });
  }
}

async function loadContinuous(): Promise<void> {
  const missing = continuousUnits.value.filter((unit) => !continuousBodies.value[String(unit.unit_id || unit.id)]);
  if (!missing.length) return;
  const loaded = await Promise.all(
    missing.map(async (unit) => [String(unit.unit_id || unit.id), unit.unit_id ? await store.loadReaderUnit(String(unit.unit_id)) : String(unit.body || unit.excerpt || "")] as const),
  );
  continuousBodies.value = { ...continuousBodies.value, ...Object.fromEntries(loaded) };
}

async function expandContinuous(): Promise<void> {
  if (continuousStart.value + continuousCount.value >= units.value.length) return;
  continuousCount.value = Math.min(units.value.length - continuousStart.value, continuousCount.value + 3);
  await loadContinuous();
}

function bodyParagraphs(unit: Record<string, unknown>): string[] {
  return String(continuousBodies.value[String(unit.unit_id || unit.id)] || "").split(/\n+/).map((item) => item.trim()).filter(Boolean);
}

async function searchProse(): Promise<void> {
  if (!searchText.value.trim() || !store.currentProjectPath) return;
  searching.value = true;
  try {
    const result = await api<{ items: Record<string, unknown>[] }>(
      `/reader/search?${query({ project_root: store.currentProjectPath, q: searchText.value.trim() })}`,
    );
    searchResults.value = result.items || [];
  } finally {
    searching.value = false;
  }
}

function openSearchResult(result: Record<string, unknown>): void {
  const target = units.value.findIndex((unit) => String(unit.unit_id || unit.id) === String(result.unit_id));
  if (target >= 0) goTo(target);
  searchOpen.value = false;
}

function chapterLabel(value: unknown): string {
  const text = String(value || "");
  const match = text.match(/chapter[_-]?(\d+)/i);
  if (match) return `第 ${Number(match[1])} 章`;
  const labels: Record<string, string> = { promoted: "已晋升正文", chapter: "章节正文", exported: "已导出", published: "已发布" };
  return labels[text] || text || "正式正文";
}
</script>

<template>
  <section
    class="manuscript-reader"
    :class="[{ expanded, compact, immersive }, `reader-theme-${theme}`]"
    @keydown.left="goTo(index - 1)"
    @keydown.right="goTo(index + 1)"
  >
    <header class="reader-header">
      <div class="reader-title-block">
        <span class="eyebrow">正式正文</span>
        <h2>{{ current?.title || "尚未形成正式正文" }}</h2>
        <p v-if="current">
          {{ chapterLabel(current.chapter_id || current.subtitle || current.status) }} ·
          {{ Number(current.chinese_content_chars || 0).toLocaleString('zh-CN') || displayValue(current.badges) }} 字
        </p>
      </div>
      <div class="reader-actions" v-if="current">
        <button class="icon-button" title="目录" @click="tocOpen = !tocOpen"><ListTree :size="18" /></button>
        <button class="icon-button" title="搜索正文" @click="searchOpen = !searchOpen"><Search :size="17" /></button>
        <button class="icon-button" :title="isBookmarked ? '取消书签' : '添加书签'" @click="toggleBookmark">
          <BookmarkCheck v-if="isBookmarked" :size="17" /><Bookmark v-else :size="17" />
        </button>
        <span class="reader-position">{{ index + 1 }} / {{ units.length }}</span>
        <button class="icon-button" title="上一节" :disabled="index === 0" @click="goTo(index - 1)"><ChevronLeft :size="18" /></button>
        <button class="icon-button" title="下一节" :disabled="index >= units.length - 1" @click="goTo(index + 1)"><ChevronRight :size="18" /></button>
        <button class="icon-button" :title="expanded ? '收回阅读器' : '全屏阅读'" @click="expanded = !expanded">
          <Minimize2 v-if="expanded" :size="18" /><Maximize2 v-else :size="18" />
        </button>
      </div>
    </header>

    <div v-if="current" class="reader-toolbelt">
      <div class="reader-typography">
        <button class="icon-button" title="减小字号" @click="fontSize--"><Minus :size="15" /></button>
        <span>{{ fontSize }} px</span>
        <button class="icon-button" title="增大字号" @click="fontSize++"><Plus :size="15" /></button>
        <select v-model.number="lineHeight" title="行距">
          <option :value="1.75">紧凑行距</option><option :value="2">舒适行距</option><option :value="2.2">宽松行距</option>
        </select>
      </div>
      <div class="reader-theme-switch" aria-label="阅读主题">
        <button :class="{ active: theme === 'mineral' }" title="明亮纸张" @click="theme = 'mineral'"><Sun :size="15" /></button>
        <button :class="{ active: theme === 'night' }" title="夜间阅读" @click="theme = 'night'"><Moon :size="15" /></button>
      </div>
      <select v-if="immersive" v-model="readingMode" class="reader-mode-select" title="阅读方式">
        <option value="section">分节阅读</option><option value="continuous">连续阅读</option>
      </select>
      <label class="follow-toggle"><input v-model="followProgress" type="checkbox" />跟随最新正文</label>
      <button v-if="newUnitCount" class="reader-new-units" @click="goTo(units.length - 1)">{{ newUnitCount }} 节新正文</button>
    </div>

    <div class="reader-layout" :class="{ 'toc-open': tocOpen && current }">
      <aside v-if="tocOpen && current" class="reader-toc">
        <header><strong>阅读目录</strong><button class="icon-button" title="关闭目录" @click="tocOpen = false"><X :size="15" /></button></header>
        <nav>
          <button
            v-for="(unit, unitIndex) in units"
            :key="String(unit.unit_id || unit.id)"
            :class="{ active: unitIndex === index }"
            @click="goTo(unitIndex)"
          >
            <span>{{ String(unit.order || unitIndex + 1).padStart(2, '0') }}</span>
            <span><strong>{{ unit.title || `第 ${unitIndex + 1} 节` }}</strong><small>{{ chapterLabel(unit.chapter_id || unit.subtitle || unit.status) }}</small></span>
            <BookmarkCheck v-if="bookmarks.includes(String(unit.unit_id || unit.id))" :size="13" />
          </button>
        </nav>
      </aside>

      <main ref="readerScroll" class="reader-scroll" tabindex="0" @scroll.passive="rememberScroll">
        <div v-if="loading && readingMode === 'section'" class="reader-loading"><BookOpenText :size="24" /><span>正在展开这一节……</span></div>
        <div v-else-if="current && readingMode === 'continuous'" class="continuous-manuscript">
          <article
            v-for="unit in continuousUnits"
            :id="`reader-unit-${unit.unit_id || unit.id}`"
            :key="String(unit.unit_id || unit.id)"
            :style="{ fontSize: `${fontSize}px`, lineHeight }"
          >
            <h1>{{ unit.title }}</h1>
            <p v-for="(paragraph, paragraphIndex) in bodyParagraphs(unit)" :key="paragraphIndex" :class="{ 'first-paragraph': paragraphIndex === 0 }">{{ paragraph.replace(/^#+\s*/, '') }}</p>
          </article>
          <button v-if="continuousStart + continuousCount < units.length" class="continuous-more" @click="expandContinuous">继续展开后文</button>
        </div>
        <article v-else-if="current" :style="{ fontSize: `${fontSize}px`, lineHeight }">
          <h1>{{ current.title }}</h1>
          <p v-for="(paragraph, paragraphIndex) in paragraphs" :key="paragraphIndex" :class="{ 'first-paragraph': paragraphIndex === 0 }">
            {{ paragraph.replace(/^#+\s*/, "") }}
          </p>
        </article>
        <div v-else class="empty-manuscript">
          <span>稿</span>
          <strong>正文会在通过审查后出现在这里</strong>
          <p>候选稿、流程记录和设定更新不会混入阅读区域。</p>
        </div>
      </main>
    </div>

    <div v-if="searchOpen" class="reader-search-panel">
      <header><strong>在正式正文中搜索</strong><button class="icon-button" @click="searchOpen = false"><X :size="16" /></button></header>
      <form @submit.prevent="searchProse"><Search :size="17" /><input v-model="searchText" autofocus placeholder="输入人物、地点或一句话" /><button class="primary-button">{{ searching ? '搜索中' : '搜索' }}</button></form>
      <button v-for="result in searchResults" :key="String(result.unit_id)" class="reader-search-result" @click="openSearchResult(result)">
        <strong>{{ result.title }}</strong><p>{{ result.excerpt }}</p>
      </button>
      <p v-if="searchText && !searching && !searchResults.length" class="reader-no-result">还没有找到匹配正文。</p>
    </div>
  </section>
</template>
