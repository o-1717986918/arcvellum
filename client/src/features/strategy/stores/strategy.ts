import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import type { EventStreamConnection } from "@/services/api";
import { friendlyError, useAppStore } from "@/stores/app";
import {
  fetchStrategy,
  observeStrategyEvents,
} from "../services/strategyClient";
import type { StrategyProjection, TypedPlanEvent } from "../types";

export const useStrategyStore = defineStore("strategy", () => {
  const app = useAppStore();
  const projection = shallowRef<StrategyProjection | null>(null);
  const events = ref<TypedPlanEvent[]>([]);
  const busy = ref(false);
  const error = ref("");
  let stream: EventStreamConnection | null = null;

  const projectRoot = computed(() => app.currentProjectPath);
  const settings = computed(() => projection.value?.settings ?? null);
  const activePlan = computed(() => projection.value?.active_plan ?? null);
  const connected = computed(() => stream !== null);

  async function load(): Promise<void> {
    stopStream();
    if (!projectRoot.value) {
      reset();
      return;
    }
    busy.value = true;
    error.value = "";
    try {
      projection.value = await fetchStrategy(projectRoot.value);
      startStream();
    } catch (cause) {
      error.value = friendlyError(cause, "创作策略暂时没有读取成功。");
    } finally {
      busy.value = false;
    }
  }

  function startStream(): void {
    if (!projectRoot.value || stream) return;
    stream = observeStrategyEvents(projectRoot.value, (event) => {
      events.value = [...events.value.slice(-99), event];
    });
  }

  function stopStream(): void {
    stream?.close();
    stream = null;
  }

  function reset(): void {
    projection.value = null;
    events.value = [];
    error.value = "";
  }

  return {
    projection,
    events,
    busy,
    error,
    settings,
    activePlan,
    connected,
    load,
    startStream,
    stopStream,
    reset,
  };
});
