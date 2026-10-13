import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import ScenePromptInspector from "./ScenePromptInspector.vue";
const mocks = vi.hoisted(() => ({ prompts: vi.fn() }));
vi.mock("../services/creativeLiveClient", () => ({ creativeLiveClient: mocks }));
describe("actual submitted creative inputs", () => {
  it("shows the frozen bundle, separate system/task inputs, and full editing comparison", async () => {
    const original = "浮月镇的夏末。".repeat(300);
    mocks.prompts.mockResolvedValue({ transaction_id: "tx", style_bundle: { digest: "bundle", preset_revision: 3,
      selection: { preset_id: "world-narration", reason: "展开风俗与岁月" }, style: { assembled: { content: "作者文风与真实计量目标" } }, measurement: { enabled: true, usage: "guide" } },
      prompt_assembly: { response_mode: "natural-v1" }, creator_briefing: null, tone_mount: { enabled: true },
      submitted_inputs: [{ role: "worker", system_prompt: "", prompt: JSON.stringify({ system_prompt: "本次主创人格", prompt: "完整委托原文" }), history: [], digest: "input", stage: "gateway-submission" }],
      edits: [{ input_digest: "edit", phase: "create", summary: "改了一处连接", accepted: [{ before: "先", after: "随后" }], original, cleaned: original + "随后。" }], measurements: [] });
    const wrapper = mount(ScenePromptInspector, { props: { projectRoot: "work", transactionId: "tx" } });
    await flushPromises();
    expect(wrapper.text()).toContain("v2 自然创作"); expect(wrapper.text()).toContain("去 AI 味 已挂载");
    expect(wrapper.text()).toContain("本次主创人格"); expect(wrapper.text()).toContain("完整委托原文");
    expect(wrapper.find(".scene-prose-comparison").text()).toContain(original);
  });
  it("discloses unavailable historical inputs and readable errors", async () => {
    mocks.prompts.mockRejectedValue(new Error("交易不属于本作品"));
    const wrapper = mount(ScenePromptInspector, { props: { projectRoot: "work", transactionId: "foreign" } });
    await flushPromises(); expect(wrapper.get('[role="alert"]').text()).toContain("交易不属于本作品");
  });
});
