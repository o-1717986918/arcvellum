<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { BookOpenText, Filter, Search, Sparkle, X } from "lucide-vue-next";
import ManuscriptReader from "@/components/ManuscriptReader.vue";
import { asList, asRecord, displayValue, labelFor, manuscriptItems, sectionEntries } from "@/services/presentation";
import { useAppStore } from "@/stores/app";

const store = useAppStore();
const queryText = ref("");
const section = ref("all");
const selected = ref<Record<string, unknown> | null>(null);

const entries = computed(() => sectionEntries(store.library?.sections));
const categories = computed(() => entries.value.map(([key, items]) => ({ key, label: labelFor(key), count: items.length })));
const items = computed(() => {
  const needle = queryText.value.trim().toLowerCase();
  return entries.value
    .filter(([key]) => section.value === "all" || section.value === key)
    .flatMap(([key, records]) =>
      records.map((record): Record<string, unknown> => ({ ...record, sectionKey: key })),
    )
    .filter((item) => {
      if (!needle) return true;
      return [item.title, item.subtitle, item.excerpt, displayValue(item.badges)].join(" ").toLowerCase().includes(needle);
    });
});
const prose = computed(() => manuscriptItems((store.library || null) as Record<string, unknown> | null));

onMounted(() => store.loadLibrary());

function keyPoints(item: Record<string, unknown>): string[] {
  const points = asList<unknown>(item.key_points).map(displayValue).filter(Boolean);
  if (points.length) return points.slice(0, 3);
  return asList<Record<string, unknown>>(item.facts)
    .filter((fact) => !["path", "路径", "机器字符"].includes(String(fact.label || "")))
    .slice(0, 3)
    .map((fact) => `${fact.label}：${displayValue(fact.value)}`);
}
</script>

<template>
  <div class="view library-view">
    <section class="overview-header archive-header">
      <div><span class="eyebrow">作品档案</span><h1>把长篇的每一层，放在手边。</h1><p>搜索人物、世界、场景、分支与审查结论。工程痕迹已经整理成可读信息。</p></div>
      <div class="archive-count"><strong>{{ items.length }}</strong><span>条作品资料</span></div>
    </section>

    <ManuscriptReader :items="prose" compact />

    <section class="archive-browser">
      <header class="archive-toolbar">
        <label class="search-field"><Search :size="17" /><input v-model="queryText" placeholder="搜索人物、场景、设定或正文" /><button v-if="queryText" @click="queryText = ''"><X :size="15" /></button></label>
        <div class="filter-label"><Filter :size="16" />按资料分类</div>
      </header>
      <div class="category-tabs" role="tablist">
        <button :class="{ active: section === 'all' }" @click="section = 'all'">全部<span>{{ entries.reduce((sum, [, records]) => sum + records.length, 0) }}</span></button>
        <button v-for="category in categories" :key="category.key" :class="{ active: section === category.key }" @click="section = category.key">
          {{ category.label }}<span>{{ category.count }}</span>
        </button>
      </div>

      <div class="archive-layout">
        <div v-if="items.length" class="archive-grid">
          <button v-for="item in items" :key="`${item.sectionKey}-${item.id}`" class="archive-card" @click="selected = item">
            <span class="archive-kind">{{ labelFor(item.sectionKey) }}</span>
            <h2>{{ item.title || "未命名资料" }}</h2>
            <p>{{ item.excerpt || "这条资料还没有摘要。" }}</p>
            <ul v-if="keyPoints(item).length">
              <li v-for="point in keyPoints(item)" :key="point"><Sparkle :size="12" />{{ point }}</li>
            </ul>
            <footer><span>{{ item.subtitle || displayValue(item.status) }}</span><BookOpenText :size="16" /></footer>
          </button>
        </div>
        <div v-else class="archive-empty"><Search :size="28" /><strong>没有找到匹配资料</strong><p>换一个关键词，或查看其他分类。</p></div>

        <aside v-if="selected" class="detail-drawer">
          <header><div><span>{{ labelFor(selected.sectionKey) }}</span><h2>{{ selected.title }}</h2></div><button class="icon-button" @click="selected = null"><X :size="18" /></button></header>
          <p class="detail-excerpt">{{ selected.excerpt }}</p>
          <div v-if="selected.body" class="detail-body">
            <p v-for="(paragraph, index) in String(selected.body).split(/\n{2,}/)" :key="index">{{ paragraph.replace(/^#+\s*/, '') }}</p>
          </div>
          <dl v-if="asList(selected.facts).length">
            <div v-for="fact in asList<Record<string, unknown>>(selected.facts)" :key="String(fact.label)"><dt>{{ fact.label }}</dt><dd>{{ displayValue(fact.value) }}</dd></div>
          </dl>
          <section v-if="keyPoints(selected).length" class="impact-box"><span>影响创作的关键点</span><ul><li v-for="point in keyPoints(selected)" :key="point">{{ point }}</li></ul></section>
        </aside>
      </div>
    </section>
  </div>
</template>
