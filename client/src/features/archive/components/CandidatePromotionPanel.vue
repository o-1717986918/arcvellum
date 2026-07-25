<script setup lang="ts">
import { Check, CircleAlert, RefreshCw, Rocket, ShieldCheck, Sparkles } from "lucide-vue-next";
import SafeMarkdown from "@/components/SafeMarkdown.vue";
import type { ArchiveCandidate } from "../types";

const props = defineProps<{
  candidate: ArchiveCandidate;
  choice?: Record<string, unknown> | null;
  decisionError?: string;
  busy?: boolean;
  job?: Record<string, unknown> | null;
}>();
const emit = defineEmits<{
  decide: [option: Record<string, unknown>];
  promote: [];
  refresh: [];
}>();

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];
}

function options(): Array<Record<string, unknown>> {
  return rows(props.choice?.options);
}

function outputRows(): Array<Record<string, unknown>> {
  const impact = props.candidate.impact;
  return rows(impact?.formal_outputs);
}
</script>

<template>
  <section class="candidate-workbench">
    <header>
      <div><span>候选资产</span><h2>{{ candidate.title || candidate.candidate_id }}</h2><p>{{ candidate.asset_type }} · {{ candidate.current_step }}</p></div>
      <button class="archive-icon-button" title="重新读取候选状态" @click="emit('refresh')"><RefreshCw :size="15" /></button>
    </header>

    <div class="candidate-columns">
      <div class="candidate-document">
        <SafeMarkdown v-if="candidate.report" :source="candidate.report" variant="document" />
        <pre v-else>{{ candidate.content }}</pre>
      </div>
      <aside>
        <section class="candidate-gates">
          <h3><ShieldCheck :size="14" />正式流程</h3>
          <ol>
            <li v-for="step in rows(candidate.steps)" :key="String(step.key)" :class="String(step.status)">
              <i><Check v-if="step.status === 'pass'" :size="11" /><CircleAlert v-else :size="11" /></i>
              <span><strong>{{ step.key }}</strong><small>{{ step.message || step.status }}</small></span>
            </li>
          </ol>
        </section>
        <section class="candidate-impact-list">
          <h3>晋升将写入</h3>
          <div v-for="output in outputRows()" :key="String(output.path)">
            <span>{{ output.effect === "replace" ? "覆盖正式版本" : "建立正式资产" }}</span>
            <strong>{{ output.path }}</strong>
          </div>
        </section>
        <section v-if="choice" class="candidate-decision">
          <h3>需要作者决定</h3>
          <p>{{ choice.summary }}</p>
          <button v-for="option in options()" :key="String(option.id)" @click="emit('decide', option)">
            {{ option.label || option.id }}
          </button>
        </section>
        <p v-else-if="decisionError" class="candidate-decision-error">{{ decisionError }}</p>
        <ul v-if="candidate.promotion_blockers?.length" class="candidate-blockers">
          <li v-for="blocker in candidate.promotion_blockers" :key="blocker">{{ blocker }}</li>
        </ul>
        <button class="candidate-promote" :disabled="!candidate.can_promote || busy" @click="emit('promote')">
          <Rocket :size="16" />{{ candidate.promoted ? "已经晋升" : candidate.can_promote ? "确认影响并正式晋升" : "尚未具备晋升条件" }}
        </button>
        <div v-if="job" class="candidate-job"><Sparkles :size="14" /><span>晋升任务 {{ job.status || "queued" }}<small>{{ job.job_id }}</small></span></div>
      </aside>
    </div>
  </section>
</template>
