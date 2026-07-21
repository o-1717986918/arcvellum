<script setup lang="ts">
import { markRaw } from "vue";
import {
  BookOpenText,
  CircleHelp,
  FolderKanban,
  Gauge,
  GitBranch,
  Info,
  LibraryBig,
  PackageCheck,
  Scale,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-vue-next";
import AutopilotPanel from "@/components/AutopilotPanel.vue";
import ImmersiveInstrumentWindow from "@/components/ImmersiveInstrumentWindow.vue";
import DeliveryView from "@/features/delivery/DeliveryView.vue";
import DetailsView from "@/features/details/DetailsView.vue";
import HelpView from "@/features/help/HelpView.vue";
import LegalView from "@/features/details/LegalView.vue";
import LibraryView from "@/features/library/LibraryView.vue";
import ProjectsView from "@/features/projects/ProjectsView.vue";
import QualityView from "@/features/quality/QualityView.vue";
import ReaderView from "@/features/reader/ReaderView.vue";
import SettingsView from "@/features/settings/SettingsView.vue";
import { asList, asRecord, describeGate, labelFor } from "@/services/presentation";
import { panelEdge, type ImmersiveEdge, type ImmersivePanel } from "@/types/immersive";

const props = defineProps<{
  open: ImmersivePanel[];
  choices: Record<string, unknown>[];
  prose: Record<string, unknown>[];
  routeAudits: Record<string, unknown>[];
}>();
const emit = defineEmits<{
  "update:open": [value: ImmersivePanel[]];
  choose: [choice: Record<string, unknown>];
}>();

const featureComponents = {
  projects: markRaw(ProjectsView),
  library: markRaw(LibraryView),
  delivery: markRaw(DeliveryView),
  settings: markRaw(SettingsView),
  help: markRaw(HelpView),
  legal: markRaw(LegalView),
} as const;
const edges: ImmersiveEdge[] = ["left", "right", "top", "bottom"];
const titles: Record<ImmersivePanel, string> = {
  progress: "连续创作",
  decisions: "等待判断",
  reader: "正式正文",
  health: "作品健康度",
  projects: "作品管理",
  library: "作品档案",
  quality: "规则与叙事节奏",
  delivery: "作品交付",
  settings: "连接与设置",
  help: "使用帮助",
  details: "应用详情",
  legal: "协议与隐私",
};

function isOpen(panel: ImmersivePanel): boolean {
  return props.open.includes(panel);
}

async function toggle(panel: ImmersivePanel): Promise<void> {
  const opening = !isOpen(panel);
  emit("update:open", opening ? [panel, ...props.open] : props.open.filter((item) => item !== panel));
}

function close(panel: ImmersivePanel): void {
  emit("update:open", props.open.filter((item) => item !== panel));
}

function openFor(edge: ImmersiveEdge): ImmersivePanel[] {
  return props.open.filter((panel) => panelEdge(panel) === edge);
}

function openFromDetails(panel: ImmersivePanel): void {
  if (!isOpen(panel)) emit("update:open", [...props.open, panel]);
}

function featureFor(panel: ImmersivePanel) {
  return panel in featureComponents ? featureComponents[panel as keyof typeof featureComponents] : null;
}
</script>

<template>
  <nav class="immersive-edge-dock" data-edge="left" aria-label="作品与档案仪表">
    <button :class="{ active: isOpen('projects') }" title="作品管理" @click="toggle('projects')"><FolderKanban :size="17" /><span>作品</span></button>
    <button :class="{ active: isOpen('library') }" title="作品档案" @click="toggle('library')"><LibraryBig :size="17" /><span>档案</span></button>
  </nav>

  <nav class="immersive-edge-dock" data-edge="right" aria-label="创作控制仪表">
    <button :class="{ active: isOpen('progress') }" title="连续创作" @click="toggle('progress')"><Gauge :size="17" /><span>推进</span></button>
    <button :class="{ active: isOpen('decisions') }" title="等待判断" @click="toggle('decisions')"><GitBranch :size="17" /><span>决策</span><i v-if="choices.length">{{ choices.length }}</i></button>
    <button :class="{ active: isOpen('quality') }" title="创作规则与叙事节奏" @click="toggle('quality')"><SlidersHorizontal :size="17" /><span>规则</span></button>
    <button :class="{ active: isOpen('health') }" title="作品健康度" @click="toggle('health')"><ShieldCheck :size="17" /><span>健康</span></button>
    <button :class="{ active: isOpen('delivery') }" title="作品交付" @click="toggle('delivery')"><PackageCheck :size="17" /><span>交付</span></button>
  </nav>

  <nav class="immersive-edge-dock" data-edge="bottom" aria-label="正文阅读仪表">
    <button :class="{ active: isOpen('reader') }" title="阅读正式正文" @click="toggle('reader')"><BookOpenText :size="17" /><span>正文长卷</span><i v-if="prose.length">{{ prose.length }}</i></button>
  </nav>

  <nav class="immersive-edge-dock" data-edge="top" aria-label="应用与帮助仪表">
    <button :class="{ active: isOpen('settings') }" title="连接与设置" @click="toggle('settings')"><Settings2 :size="17" /><span>设置</span></button>
    <button :class="{ active: isOpen('help') }" title="使用帮助" @click="toggle('help')"><CircleHelp :size="17" /><span>帮助</span></button>
    <button :class="{ active: isOpen('details') }" title="应用详情" @click="toggle('details')"><Info :size="17" /><span>详情</span></button>
    <button :class="{ active: isOpen('legal') }" title="协议与隐私" @click="toggle('legal')"><Scale :size="17" /><span>协议</span></button>
  </nav>

  <div class="immersive-instrument-layout" aria-label="已打开的星仪窗口">
    <section v-for="edge in edges" :key="edge" class="immersive-instrument-zone" :data-edge="edge" :aria-label="`${edge}侧已打开仪表`">
      <ImmersiveInstrumentWindow
        v-for="panel in openFor(edge)"
        :key="panel"
        :panel="panel"
        :edge="edge"
        :title="titles[panel]"
        @close="close(panel)"
      >
        <AutopilotPanel v-if="panel === 'progress'" />

        <section v-else-if="panel === 'decisions'" class="immersive-decisions">
          <template v-if="choices.length">
            <article v-for="choice in choices" :key="String(choice.choice_id || choice.id)">
              <span>{{ labelFor(choice.kind || choice.decision_type) }}</span>
              <h3>{{ choice.title || choice.prompt || "创作方向选择" }}</h3>
              <p>{{ choice.summary || choice.description || "查看候选方向和它对后续创作的影响。" }}</p>
              <button class="secondary-button" @click="emit('choose', choice)">打开选择</button>
            </article>
          </template>
          <div v-else class="immersive-empty"><GitBranch :size="24" /><strong>当前没有等待判断的方向</strong><p>需要你决定的分支、设定或修订方向会出现在这里。</p></div>
        </section>

        <QualityView v-else-if="panel === 'quality'" instrument />
        <ReaderView v-else-if="panel === 'reader'" />

        <section v-else-if="panel === 'health'" class="immersive-route-ledger">
          <article v-for="audit in routeAudits" :key="String(audit.route)">
            <i :class="Number(audit.blocking_count || 0) ? 'blocked' : 'ready'"></i>
            <div><strong>{{ labelFor(audit.route) }}</strong><p v-if="Number(audit.blocking_count || 0)">{{ describeGate(asRecord(asList(audit.top_blocking_gates)[0]).message) }}</p><p v-else>已经具备继续推进的条件。</p></div>
            <span>{{ audit.gate_count || 0 }} 项</span>
          </article>
        </section>

        <DetailsView v-else-if="panel === 'details'" embedded @navigate="openFromDetails($event as ImmersivePanel)" />
        <component :is="featureFor(panel)" v-else-if="featureFor(panel)" instrument />
      </ImmersiveInstrumentWindow>
    </section>
  </div>
</template>
