<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import { CircleAlert, Radio, RefreshCw, Unplug } from "lucide-vue-next";
import { useStrategyStore } from "./stores/strategy";

const store = useStrategyStore();

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
          <div><dt>模式</dt><dd>{{ store.settings?.mode }}</dd></div>
          <div><dt>预设</dt><dd>{{ store.settings?.preset }}</dd></div>
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
          <strong>{{ event.event_type }}</strong>
          <code>{{ event.plan_id }}</code>
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
