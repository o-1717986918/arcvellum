import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LessAiToneExperiment from "./LessAiToneExperiment.vue";

const api = vi.hoisted(() => ({ toneExperimentPreferences: vi.fn(), saveToneExperimentPreferences: vi.fn() }));
vi.mock("./services/settingsClient", () => ({ settingsClient: api }));
const preferences = { enabled: true, rule_count: 11, rule_source: "lieflat-less-ai-tone",
  source_commit: "source-commit", prompt_layer_id: "experiment.less_ai_tone.editor", audit_directory: "C:/Studio/data" };

describe("automatic less AI tone experiment", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.toneExperimentPreferences.mockResolvedValue({ preferences });
  });

  it("shows the actual mount and saves a changed selection", async () => {
    const wrapper = mount(LessAiToneExperiment);
    await flushPromises();
    expect(wrapper.find("select").element.value).toBe("true");
    expect(wrapper.text()).toContain("source-commit");
    api.saveToneExperimentPreferences.mockResolvedValue({ preferences: { ...preferences, enabled: false } });
    await wrapper.find("select").setValue(false);
    await flushPromises();
    expect(api.saveToneExperimentPreferences).toHaveBeenCalledWith(false);
    expect(wrapper.text()).toContain("已保存");
  });

  it("restores confirmed settings if persistence fails", async () => {
    const wrapper = mount(LessAiToneExperiment);
    await flushPromises();
    api.saveToneExperimentPreferences.mockRejectedValue(new Error("保存失败"));
    await wrapper.find("select").setValue(false);
    await flushPromises();
    expect(wrapper.find("select").element.value).toBe("true");
    expect(wrapper.find("[role=status]").text()).toBe("保存失败");
  });

  it("keeps the switch unavailable when the server cannot load settings", async () => {
    api.toneExperimentPreferences.mockRejectedValue(new Error("服务未就绪"));
    const wrapper = mount(LessAiToneExperiment);
    await flushPromises();
    expect(wrapper.find("select").element.disabled).toBe(true);
    expect(wrapper.text()).toContain("服务未就绪");
  });
});
