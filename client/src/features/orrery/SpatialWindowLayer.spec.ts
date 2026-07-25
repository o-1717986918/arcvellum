import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import SpatialWindowLayer from "./SpatialWindowLayer.vue";
import { useAppStore } from "@/stores/app";
import { useSpatialWindowsStore } from "@/stores/spatialWindows";

describe("SpatialWindowLayer", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: () => ({
        matches: false,
        media: "",
        onchange: null,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      }),
    });
  });

  it("keeps an open reader mounted while live observability facts update", async () => {
    const app = useAppStore();
    const windows = useSpatialWindowsStore();
    windows.setScope("C:\\ArcVellum\\潮汐之后::spine", []);
    windows.openInstrument("reader");
    const wrapper = mount(SpatialWindowLayer, {
      props: {
        projection: null,
        dashboard: { route_audits: [] },
        choices: [],
        delivery: null,
        progress: null,
        prose: [],
      },
      global: {
        stubs: {
          AutopilotPanel: true,
          RulesInstrument: true,
          SafeMarkdown: true,
          ManuscriptReader: {
            props: ["mode"],
            template: '<div class="reader-stub">{{ mode }}</div>',
          },
        },
      },
    });
    const reader = wrapper.find('[data-spatial-window-id="instrument:reader"]');
    const element = reader.element;

    app.$patch({
      agentObservability: {
        ok: true,
        schema: "arcvellum/agent-observability/v2",
        project_root: "C:\\ArcVellum\\潮汐之后",
        status: "active",
        active_task: null,
        controller: null,
        services: [],
        sessions: [],
        recent_events: [],
        throughput: {
          schema: "arcvellum/throughput-projection/v1",
          mode: "measure-only",
          event_count: 0,
          task_count: 0,
          bundle_count: 0,
          model_turns: 0,
          repairs: 0,
          retries: 0,
          first_validation: {
            evaluated_tasks: 0,
            passed_first_attempt: 0,
            failed_first_attempt: 0,
            pass_rate: null,
          },
          usage: {
            input_tokens: 0,
            output_tokens: 0,
            reasoning_tokens: 0,
            cache_read_tokens: 0,
            cache_write_tokens: 0,
            total_tokens: 0,
            cost_usd: 0,
          },
          stages: {},
          coverage: {
            event_ledger: false,
            bundle_events: false,
            cache_tokens: false,
            scene_attribution: false,
          },
          tasks: [],
          tasks_truncated: false,
          revision: "throughput-1",
        },
        revision: "agent-2",
      },
    });
    await wrapper.setProps({ dashboard: { route_audits: [], current_task: { title: "更新后的任务" } } });

    expect(wrapper.find('[data-spatial-window-id="instrument:reader"]').element).toBe(element);
    expect(wrapper.find(".reader-stub").text()).toBe("peek");
  });
});
