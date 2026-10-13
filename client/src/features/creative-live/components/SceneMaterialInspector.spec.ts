import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import SceneMaterialInspector from "./SceneMaterialInspector.vue";

const mocks = vi.hoisted(() => ({ materials: vi.fn() }));
vi.mock("../services/creativeLiveClient", () => ({ creativeLiveClient: mocks }));

describe("complete material inspection", () => {
  it('shows local processing and technical calls separately',async()=>{
    mocks.materials.mockResolvedValue({inspection:{transaction_id:'tx',calls:[],materials:[],warnings:[],candidate_count:0,
      transport:{model_calls:1,reuse_count:2,local_records:3,records:[{record_id:'r',operation:'creator',mode:'reused',
        model_calls:1,reuse_count:2,requested_thinking:'off'}]}}});
    const wrapper=mount(SceneMaterialInspector,{props:{projectRoot:'work',transactionId:'tx'}});
    await flushPromises();
    expect(wrapper.get('.material-transport').text()).toContain('3 份本地解析');
    expect(wrapper.get('.material-transport').text()).toContain('1 次整理调用');
    expect(wrapper.get('.material-transport').text()).toContain('请求非思考');
    wrapper.unmount();
  });
  it("shows discarded long prose, requests, source status and private character fiction", async () => {
    const text = "森林的历法。\n".repeat(500);
    const base = { call_id: "call", target: "森林", purpose: "介绍季节", scene_moment: "整个夏季", text,
      spoken: "", first_person_action: "", private_impulse: "", focus: "", basis: "confirmed",
      source_note: "世界档案", decision: "discard", decision_reason: "选了另一种叙述声音", complete: true, attachments: [] };
    mocks.materials.mockResolvedValue({ inspection: {
      transaction_id: "tx", scene_id: "scene_0001", calls: [{ call_id: "call", sequence: 1,
        request: { kind: "event-narration", target: "森林", purpose: "介绍季节" }, attachments: [], raw_response: text }],
      candidate_count: 2, warnings: [], materials: [{ ...base, candidate_id: "event:1", kind: "event-narration" },
        { ...base, candidate_id: "actor:1", kind: "actor", private_impulse: "我在期待节日。" }],
    } });
    const wrapper = mount(SceneMaterialInspector, { props: { projectRoot: "work", transactionId: "tx" } });
    await flushPromises();
    expect(wrapper.find(".material-original").text()).toBe(text.trim());
    expect(wrapper.text()).toContain("舍下");
    expect(wrapper.text()).toContain("已确认资料");
    expect(wrapper.text()).toContain("我在期待节日。");
    await wrapper.find('select').setValue("event-narration");
    expect(wrapper.findAll(".material-candidate")).toHaveLength(1);
    await wrapper.find('input').setValue("不存在的词");
    expect(wrapper.text()).toContain("没有符合筛选条件");
  });

  it("shows a retryable read failure", async () => {
    mocks.materials.mockRejectedValue(new Error("素材记录无法读取"));
    const wrapper = mount(SceneMaterialInspector, { props: { projectRoot: "work", transactionId: "bad" } });
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("素材记录无法读取");
    expect(wrapper.get('[role="alert"] button').text()).toBe("重试");
  });
});
