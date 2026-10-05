import { mount, flushPromises } from "@vue/test-utils";
import { computed, defineComponent, ref } from "vue";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { useStylometryTuning } from "./useStylometryTuning";
import type { FragmentRequest, StyloCompiled } from "../stylometryTypes";
const mocks = vi.hoisted(() => ({ compile: vi.fn() }));
vi.mock("../services/stylometryClient", () => ({ stylometryClient: mocks }));
const base: FragmentRequest = { project_root: "work", profile_id: "p", controls_json: "10", dependency_json: "", title: "河", intent: "" };
function harness() {
  const input = ref({ ...base }), fragment = ref(""), compiled = ref<StyloCompiled | null>(null), publish = vi.fn().mockResolvedValue(true);
  let desk!: ReturnType<typeof useStylometryTuning>;
  const wrapper = mount(defineComponent({ setup() { desk = useStylometryTuning(computed(() => input.value), fragment, compiled, publish); return () => null; } }));
  return { desk, input, fragment, compiled, publish, wrapper };
}
beforeEach(() => { vi.useFakeTimers(); mocks.compile.mockReset(); mocks.compile.mockImplementation(async input => ({ fragment_text: `目标 ${input.controls_json}` })); });
afterEach(() => { vi.useRealTimers(); });
describe("live parameter preview and mount", () => {
  it("coalesces rapid drags and publishes the exact latest requirement", async () => {
    const { desk, input, fragment, publish, wrapper } = harness();
    desk.autoMount.value = true;
    input.value = { ...base, controls_json: "11" }; await flushPromises();
    input.value = { ...base, controls_json: "12" }; await flushPromises();
    await vi.advanceTimersByTimeAsync(351);
    expect(mocks.compile).toHaveBeenCalledTimes(1);
    expect(publish).toHaveBeenCalledTimes(1);
    expect(publish.mock.calls[0][0].controls_json).toBe("12");
    expect(publish.mock.calls[0][1]).toBe("目标 12"); expect(fragment.value).toBe("目标 12");
    wrapper.unmount();
  });
  it("discards an older compile response after another drag", async () => {
    const { desk, input, fragment, wrapper } = harness();
    let resolve!: (result: unknown) => void;
    mocks.compile.mockReturnValueOnce(new Promise(done => { resolve = done; }));
    const old = desk.refresh(); input.value = { ...base, controls_json: "20" };
    await desk.refresh(); resolve({ fragment_text: "过时目标 10" }); await old;
    expect(fragment.value).toBe("目标 20"); wrapper.unmount();
  });
  it("preserves handwritten prose and offers the new generated requirement for adoption", async () => {
    const { desk, input, fragment, compiled, wrapper } = harness();
    await desk.refresh(); fragment.value = "将风声写成迟疑的回应。";
    input.value = { ...base, controls_json: "30" }; await desk.refresh();
    expect(fragment.value).toBe("将风声写成迟疑的回应。"); expect(compiled.value?.fragment_text).toBe("目标 30");
    expect(desk.manualFragment.value).toBe(true); expect(desk.autoMount.value).toBe(false);
    desk.takePreview(); expect(fragment.value).toBe("目标 30"); expect(desk.manualFragment.value).toBe(false);
    wrapper.unmount();
  });
  it("allows stopping automatic mounting while a publication is pending", async () => {
    const { desk, publish, wrapper } = harness();
    let finish!: () => void, current!: () => boolean;
    publish.mockImplementation((_input, _body, guard) => { current = guard; return new Promise<boolean>(done => { finish = () => done(guard()); }); });
    desk.autoMount.value = true; const pending = desk.applyAndMount(); await flushPromises();
    expect(current()).toBe(true); desk.autoMount.value = false; expect(current()).toBe(false);
    finish(); await pending; expect(desk.publishing.value).toBe(false); wrapper.unmount();
  });
  it("keeps the current mount when compilation fails and stops automatic publishing", async () => {
    const { desk, publish, wrapper } = harness();
    mocks.compile.mockRejectedValue(new Error("短句与长句目标需要调整"));
    desk.autoMount.value = true; await desk.refresh();
    expect(publish).not.toHaveBeenCalled(); expect(desk.previewError.value).toContain("需要调整");
    expect(desk.autoMount.value).toBe(false); wrapper.unmount();
  });
});
