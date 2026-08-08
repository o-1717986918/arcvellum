<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import { CircleAlert, Radio, RefreshCw, Unplug } from "lucide-vue-next";
import { computed } from "vue";
import { projectPlanOverlay } from "./orreryPlanProjection";
import { useStrategyStore } from "./stores/strategy";

const store = useStrategyStore();
const overlay = computed(() =>
  projectPlanOverlay(store.projection, store.events),
);
const visibleCapabilities = computed(() =>
  (store.projection?.capabilities || []).filter((item) => item.user_visible),
);

const modeLabels: Record<string, string> = {
  fixed: "固定正式路线",
  shadow: "影子评估",
  assisted: "辅助编排",
  supervised_adaptive: "监督式自适应",
  full_adaptive: "全自适应",
};
const presetLabels: Record<string, string> = {
  conservative: "审慎",
  balanced: "均衡",
  exploratory: "探索",
};

function maturityLabel(value: string): string {
  return { production: "正式能力", preview: "预览能力", contract: "合同阶段" }[value] || value;
}

function stateLabel(value: string): string {
  return { active: "正式运行", available: "可用，尚未启用", disabled: "当前关闭", unavailable: "暂未开放" }[value] || value;
}

function eventLabel(value: string): string {
  return {
    "plan.candidate.started": "开始形成计划候选",
    "plan.candidate.completed": "计划候选已完成",
    "plan.review.completed": "计划审查已完成",
    "plan.activated": "计划已正式激活",
  }[value] || value;
}

onMounted(() => void store.load());
onUnmounted(() => store.stopStream());
</script>

<template>
  <div v-if="store.busy && !store.projection" class="view strategy-view">
    <div class="rules-page-state">
      <strong>正在读取创作策略</strong>
      <p>编排设置与激活计划正在与正式项目同步。</p>
    </div>
  </div>
  <div v-else-if="!store.projection" class="view strategy-view">
    <div class="rules-page-state is-error">
      <CircleAlert :size="22" />
      <strong>创作策略暂时不可用</strong>
      <p>{{ store.error || "请确认已经打开一个有效作品。" }}</p>
      <button class="secondary-button" @click="store.load">
        <RefreshCw :size="15" />重新读取
      </button>
    </div>
  </div>
  <div v-else class="view strategy-view">
    <header class="quality-heading">
      <div>
        <span class="eyebrow">创作策略</span>
        <h1>计划如何推进</h1>
        <p>这里只展示正式项目中的策略状态；计划激活与写回仍由 CLI 门禁完成。</p>
      </div>
      <button class="secondary-button" @click="store.load">
        <RefreshCw :size="15" />重新读取
      </button>
    </header>

    <section class="strategy-grid">
      <article class="strategy-card">
        <header>
          <span class="eyebrow">编排设置</span>
          <h2>当前模式</h2>
        </header>
        <dl>
          <div><dt>模式</dt><dd>{{ modeLabels[store.settings?.mode || ""] || store.settings?.mode }}</dd></div>
          <div><dt>内部标识</dt><dd><code>{{ store.settings?.mode }}</code></dd></div>
          <div><dt>策略倾向</dt><dd>{{ presetLabels[store.settings?.preset || ""] || store.settings?.preset }} <small>({{ store.settings?.preset }})</small></dd></div>
          <div><dt>开关</dt><dd>{{ store.settings?.enabled ? "开启" : "关闭" }}</dd></div>
        </dl>
      </article>

      <article class="strategy-card">
        <header>
          <span class="eyebrow">激活计划</span>
          <h2>当前绑定</h2>
        </header>
        <dl v-if="store.activePlan">
          <div><dt>计划</dt><dd>{{ store.activePlan.plan_id }}</dd></div>
          <div><dt>版本</dt><dd>{{ store.activePlan.revision }}</dd></div>
          <div><dt>状态</dt><dd>{{ store.activePlan.status }}</dd></div>
          <div><dt>范围</dt><dd>{{ store.activePlan.scope_kind }} · {{ store.activePlan.scope_key }}</dd></div>
        </dl>
        <p v-else class="strategy-empty">还没有激活的创作计划。计划经独立审查与授权后才会出现在这里。</p>
      </article>
    </section>

    <section class="strategy-capabilities" aria-label="创作能力成熟度">
      <header>
        <span class="eyebrow">能力实况</span>
        <h2>哪些能力现在真的生效</h2>
        <p>“正式能力”说明生产链已经使用；“预览能力”仍需明确开启。支持程度与当前开关分别显示。</p>
      </header>
      <div class="strategy-capability-grid">
        <article v-for="capability in visibleCapabilities" :key="capability.id" :data-state="capability.state" :data-maturity="capability.maturity">
          <div class="capability-signal" aria-hidden="true"><i></i><i></i><i></i></div>
          <div>
            <span>{{ maturityLabel(capability.maturity) }}</span>
            <h3>{{ capability.label }}</h3>
            <p>{{ capability.detail }}</p>
          </div>
          <strong>{{ stateLabel(capability.state) }}</strong>
        </article>
      </div>
    </section>

    <section class="strategy-card strategy-overlay">
      <header>
        <span class="eyebrow">计划投影</span>
        <h2>星仪轻量视图</h2>
      </header>
      <div class="plan-overlay-strip">
        <span
          v-for="node in overlay.nodes"
          :key="node.id"
          class="plan-overlay-node"
          :data-kind="node.kind"
          :title="node.detail || node.label"
        >
          <small>{{ node.slot }}</small>
          {{ node.label }}
        </span>
      </div>
      <p class="strategy-empty">
        {{
          overlay.plan_id
            ? `${overlay.plan_id} · ${overlay.event_count} 个事件`
            : "还没有可投影的激活计划。"
        }}
      </p>
    </section>

    <section class="strategy-events">
      <header>
        <div>
          <span class="eyebrow">计划事件流</span>
          <h2>实时 typed 事件</h2>
        </div>
        <template v-if="store.connected">
          <button class="text-button" @click="store.stopStream()">
            <Unplug :size="14" />断开事件流
          </button>
        </template>
        <template v-else>
          <button class="text-button" @click="store.startStream()">
            <Radio :size="14" />连接事件流
          </button>
        </template>
      </header>
      <div class="strategy-event-log">
        <article v-for="event in store.events" :key="`${event.event_id}-${event.created_at}`">
          <span class="event-dot" aria-hidden="true"></span>
          <strong>{{ eventLabel(event.event_type) }}</strong>
          <code>{{ event.plan_id }}</code>
          <small>{{ event.event_type }}</small>
          <small v-if="event.revision !== undefined">r{{ event.revision }}</small>
          <time>{{ event.created_at || "—" }}</time>
        </article>
        <p v-if="!store.events.length" class="strategy-empty">
          还没有收到计划事件。事件在计划候选、Lint、编译、模拟或激活通过正式审计后产生。
        </p>
      </div>
    </section>

    <footer class="strategy-boundary">
      本页只读。计划 diff、模拟结果与审批状态来自正式审计证据；审批与写回不能从这里发起。
    </footer>
  </div>
</template>
