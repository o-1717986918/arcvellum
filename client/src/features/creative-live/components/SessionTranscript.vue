<script setup lang="ts">
import { Bot, Braces, TerminalSquare } from "lucide-vue-next";
import SafeMarkdown from "@/components/SafeMarkdown.vue";
import type { CreativeSession } from "../types";

defineProps<{ session?: CreativeSession | null }>();

function toolLabel(value?: string): string {
  return ({
    read_authorized_source: "读取授权资料",
    write_expected_output: "写入候选产物",
    validate_output: "验证候选产物",
    complete_task: "提交正式预检",
    report_blocker: "报告推进阻塞",
  } as Record<string, string>)[value || ""] || "项目工具";
}
</script>

<template>
  <section class="creative-session-panel">
    <header>
      <div><span>Agent 会话</span><strong>{{ session?.role || '等待主创 Agent' }}</strong></div>
      <i :class="{ live: session?.status === 'running' }">{{ session?.status === 'running' ? 'LIVE' : session?.status || 'IDLE' }}</i>
    </header>
    <dl v-if="session" class="creative-session-facts">
      <div><dt>执行器</dt><dd>{{ session.runtime || 'Pi Worker' }}</dd></div>
      <div><dt>模型</dt><dd>{{ session.model || '由执行器管理' }}</dd></div>
      <div><dt>路线</dt><dd>{{ session.route || '等待路线' }}</dd></div>
    </dl>
    <div v-if="session?.transcript" class="creative-transcript"><SafeMarkdown :source="session.transcript" variant="chat" /></div>
    <div v-else class="creative-live-empty compact"><Bot :size="21" /><p>Agent 的可见说明会在这里流式出现。</p></div>
    <section v-if="session?.tools?.length" class="creative-tool-list">
      <header><TerminalSquare :size="13" /><strong>最近工具活动</strong></header>
      <ol>
        <li v-for="(tool, index) in session.tools.slice(-8).reverse()" :key="`${tool.at}-${index}`">
          <Braces :size="12" /><span>{{ toolLabel(tool.tool) }}</span><small>{{ tool.event.replace('tool.', '') }}</small>
        </li>
      </ol>
    </section>
    <details v-if="session?.context" class="creative-context-summary">
      <summary>本轮使用的创作资料 <span>{{ session.context.entry_count }} 项</span></summary>
      <div v-if="session.context.available" class="creative-context-facts">
        <p>{{ Number(session.context.character_count || 0).toLocaleString('zh-CN') }} 字符已纳入本轮资料合同</p>
        <ol><li v-for="(entry, index) in session.context.entries.slice(0, 12)" :key="`${entry.title}-${index}`"><strong>{{ entry.title }}</strong><small>{{ entry.purpose || entry.partition || '支撑当前创作任务' }}</small><span>{{ entry.character_count.toLocaleString('zh-CN') }}</span></li></ol>
      </div>
      <p v-else>本轮资料指纹已经记录，详细分类尚未进入可读投影。</p>
    </details>
    <details v-if="session?.task_id" class="creative-technical-identity"><summary>技术身份</summary><code>{{ session.task_id }}</code></details>
  </section>
</template>
