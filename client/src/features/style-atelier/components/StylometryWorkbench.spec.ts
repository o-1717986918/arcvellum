import { mount, flushPromises } from "@vue/test-utils";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { defineComponent, ref } from "vue";
import { useStylometry } from "../stores/useStylometry";
import StylometryWorkbench from "./StylometryWorkbench.vue";
const mocks = vi.hoisted(() => ({ workbench: vi.fn(), jobs: vi.fn(), profile: vi.fn(), parameters: vi.fn(),
  compile: vi.fn(), save: vi.fn(), mount: vi.fn(), measure: vi.fn(), version: vi.fn() }));
vi.mock("../services/stylometryClient", () => ({ stylometryClient: mocks }));
const controls = { schema: "stylometric-creator-controls/v1", profile_sha256: "hash", dependency_parse_hash: null,
  targets: [{ id: "sentence_length_han", unit: "han/sentence", min: 5, max: 20, enabled: true }] };
const workbench = { schema: "workbench", profiles: [{ profile_id: "p1", title: "河与山" }], versions: [],
  mount: { enabled: false, revision: 0, combine: "append", usage: "guide" },
  capabilities: { lab_version: "0.9.0" }, style_context: { author_directive: "作者方向", formal: "正式文风" } };
beforeEach(() => {
  Object.values(mocks).forEach(mock => mock.mockReset());
  mocks.workbench.mockResolvedValue(workbench); mocks.jobs.mockResolvedValue({ jobs: [] });
  mocks.profile.mockResolvedValue({ profile_id: "p1", title: "河与山", profile_json: "{}", controls });
  mocks.parameters.mockResolvedValue({ controls: structuredClone(controls), metrics: [{ id: "sentence_length_han", label: "句群节奏",
    unit: "han/sentence", group: "primary", observed: 12, available: true, floor: 1, ceiling: 500, suggested: { min: 5, max: 20 } }] });
});
describe("stylometry workbench", () => {
  it("clears measurements on version and body changes and discards replies for edited text", async () => {
    let desk!: ReturnType<typeof useStylometry>;
    const wrapper = mount(defineComponent({ setup() { desk = useStylometry(ref("work-one")); return () => null; } }));
    await flushPromises();
    mocks.version.mockResolvedValue({ version_id: "v1", profile_id: "p1", title: "第一版", intent: "",
      fragment_text: "自由片段", controls_json: JSON.stringify(controls), dependency_json: "", compiled_json: "{}" });
    await desk.selectVersion("v1");
    desk.text.value = "旧正文";
    mocks.measure.mockResolvedValue({ measurement: { axes: {} }, targets: [] });
    await desk.measure(); expect(desk.report.value).not.toBeNull();
    await desk.selectVersion("v1"); expect(desk.report.value).toBeNull();
    await desk.measure(); desk.text.value = "新正文"; expect(desk.report.value).toBeNull();
    let resolve!: (value: unknown) => void;
    mocks.measure.mockReturnValueOnce(new Promise(done => { resolve = done; }));
    const pending = desk.measure(); desk.text.value = "又一次修改";
    resolve({ measurement: { axes: {} }, targets: [] }); await pending;
    expect(desk.report.value).toBeNull();
    await desk.measure(); expect(desk.report.value).not.toBeNull();
    await desk.selectProfile("p1"); expect(desk.report.value).toBeNull();
    wrapper.unmount();
  });
  it("observation preview retains formal style while guided replacement uses the selected fragment", async () => {
    mocks.workbench.mockResolvedValue({ ...workbench, versions: [{ version_id: "v1", title: "实验片段" }] });
    mocks.version.mockResolvedValue({ version_id: "v1", profile_id: "p1", title: "实验片段", intent: "",
      fragment_text: "自由片段", controls_json: JSON.stringify(controls), dependency_json: "", compiled_json: "{}" });
    const wrapper = mount(StylometryWorkbench, { props: { projectRoot: "work-one" } });
    await flushPromises();
    await wrapper.findAll("button").find(item => item.text().startsWith("实验片段"))!.trigger("click");
    await flushPromises();
    const options = wrapper.findAll("select");
    await options[0]!.setValue("replace"); await options[1]!.setValue("observe");
    const preview = () => wrapper.find(".stylo-content > section:last-child pre").text();
    expect(preview()).toContain("作者方向"); expect(preview()).toContain("正式文风");
    expect(preview()).not.toContain("自由片段");
    await options[1]!.setValue("guide");
    expect(preview()).toContain("作者方向"); expect(preview()).toContain("自由片段");
    expect(preview()).not.toContain("正式文风");
    wrapper.unmount();
  });
  it("matches partial version controls by metric ID and adds omitted axes explicitly", async () => {
    mocks.workbench.mockResolvedValue({ ...workbench, versions: [{ version_id: "partial", title: "部分指标" }] });
    const second = { id: "paragraph_length_han", label: "段落呼吸", unit: "han/paragraph", group: "primary",
      observed: 50, available: true, floor: 1, ceiling: 2000, suggested: { min: 20, max: 80 } };
    const first = (await mocks.parameters()).metrics[0];
    mocks.parameters.mockResolvedValue({ controls, metrics: [second, first] });
    mocks.version.mockResolvedValue({ version_id: "partial", profile_id: "p1", title: "部分指标", intent: "",
      fragment_text: "自由片段", controls_json: JSON.stringify(controls), dependency_json: "", compiled_json: "{}" });
    const wrapper = mount(StylometryWorkbench, { props: { projectRoot: "work-one" } });
    await flushPromises();
    await wrapper.findAll("button").find(item => item.text().startsWith("部分指标"))!.trigger("click");
    await flushPromises();
    await wrapper.findAll("button").find(item => item.text() === "参数与提示词")!.trigger("click");
    expect(wrapper.find('input[aria-label="句群节奏目标下界"]').element).toHaveProperty("value", "5");
    expect(wrapper.text()).toContain("未纳入此版本");
    expect(wrapper.text()).not.toContain("当前修改尚未保存");
    await wrapper.findAll("button").find(item => item.text() === "加入此指标")!.trigger("click");
    expect(wrapper.find('input[aria-label="段落呼吸目标下界"]').element).toHaveProperty("value", "20");
    expect(wrapper.text()).toContain("当前修改尚未保存");
    wrapper.unmount();
  });
  it("edits creator fragment, saves a version, and mounts the saved exact text", async () => {
    const wrapper = mount(StylometryWorkbench, { props: { projectRoot: "work-one" } });
    await flushPromises();
    await wrapper.findAll("button").find(item => item.text() === "河与山")!.trigger("click"); await flushPromises();
    mocks.compile.mockResolvedValue({ fragment_text: "编译片段", artifact_sha256: "compiled" });
    await wrapper.findAll("button").find(item => item.text() === "编译文风片段")!.trigger("click"); await flushPromises();
    await wrapper.find(".stylo-fragment").setValue("我手写的文学化片段。");
    const version = { version_id: "v1", profile_id: "p1", title: "河与山", fragment_text: "我手写的文学化片段。",
      controls_json: JSON.stringify(controls), compiled_json: '{"fragment_text":"编译片段"}', dependency_json: "", intent: "", user_edited: true };
    mocks.save.mockResolvedValue(version);
    await wrapper.findAll("button").find(item => item.text() === "保存新版本")!.trigger("click"); await flushPromises();
    expect(mocks.save.mock.calls[0][0].fragment_override).toBe(version.fragment_text);
    await wrapper.findAll("button").find(item => item.text() === "主创挂载与测量")!.trigger("click");
    await wrapper.findAll("button").find(item => item.text() === "挂载所选版本")!.trigger("click"); await flushPromises();
    expect(mocks.mount).toHaveBeenCalledWith("work-one", "v1", true, 0, "append", "guide");
    wrapper.unmount();
  });
  it("discards an old project's delayed reply after switching projects", async () => {
    let resolve!: (value: unknown) => void;
    mocks.workbench.mockReturnValueOnce(new Promise(done => { resolve = done; }));
    const wrapper = mount(StylometryWorkbench, { props: { projectRoot: "old" } });
    await wrapper.setProps({ projectRoot: "new" }); await flushPromises();
    resolve({ ...workbench, profiles: [{ profile_id: "old-profile", title: "旧作品专属画像" }] }); await flushPromises();
    expect(wrapper.text()).not.toContain("旧作品专属画像");
    expect(wrapper.text()).toContain("河与山");
    wrapper.unmount();
  });
});
