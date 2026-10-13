import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CharacterChatPanel from "./CharacterChatPanel.vue";
const mocks = vi.hoisted(() => ({ setup: vi.fn(), archive: vi.fn(), create: vi.fn(), ask: vi.fn(), session: vi.fn(), draftCard: vi.fn() }));
vi.mock("./services/characterChatClient", () => ({ characterChatClient: mocks }));
describe("character dialogue panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.setup.mockResolvedValue({ sections: ["PERSONA_LOAD"], card_schema:'arcvellum/actor-character-card/v2', cards: [{
      digest: "card-1", scene_id: "s1", card: { schema:'arcvellum/actor-character-card/v2', target: "阿青", sections: { PERSONA_LOAD: "独特声线" }, source_refs: ["known.md"] },
    }], sessions: [] });
    mocks.archive.mockResolvedValue({ entries: [], next_cursor: null });
  });
  it("loads a card and independent context, then shows a natural answer", async () => {
    const session = { session_id: "chat-1", target: "阿青", context: "雨停后的窗边",
      known_archive: [], system_prompt: "【PERSONA_LOAD】独特声线", turns: [] };
    mocks.create.mockResolvedValue({ session });
    mocks.ask.mockResolvedValue({ session: { ...session, turns: [{ message: "信呢？", answer: "我翻过信封，手指还湿着。" }] } });
    const wrapper = mount(CharacterChatPanel, { props: { projectRoot: "C:/works/rain" }, global: { stubs: { Teleport: true } } });
    await flushPromises();
    await wrapper.findAll("select")[0].setValue("card-1");
    const context = wrapper.find('textarea[placeholder^="此刻在哪里"]');
    await context.setValue("雨停后的窗边");
    const create = wrapper.findAll("button").find((button) => button.text() === "加载并开始新对话")!;
    await create.trigger("click");
    await flushPromises();
    expect(mocks.create.mock.calls[0][3]).toBe("雨停后的窗边");
    expect(mocks.create.mock.calls[0][1].schema).toBe('arcvellum/actor-character-card/v2');
    await wrapper.find("form textarea").setValue("信呢？");
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    expect(mocks.ask).toHaveBeenCalledWith("C:/works/rain", "chat-1", "信呢？");
    expect(wrapper.text()).toContain("手指还湿着");
    wrapper.unmount();
  });
  it("shows setup failures and closes on Escape", async () => {
    mocks.setup.mockRejectedValue(new Error("请先选择作品"));
    const wrapper = mount(CharacterChatPanel, { props: { projectRoot: "" }, global: { stubs: { Teleport: true } } });
    await flushPromises();
    expect(wrapper.find('[role="alert"]').text()).toBe("请先选择作品");
    await wrapper.find(".character-chat-overlay").trigger("keydown", { key: "Escape" });
    expect(wrapper.emitted("close")).toHaveLength(1);
    wrapper.unmount();
  });

  it('keeps an explicitly selected legacy card schema and all its fields',async()=>{
    mocks.setup.mockResolvedValue({sections:['PERSONA_LOAD'],card_schema:'arcvellum/actor-character-card/v2',
      cards:[{digest:'legacy',card:{schema:'arcvellum/actor-character-card/v1',target:'阿青',
        sections:{PERSONA_LOAD:'旧人格',PERSONALITY_CORE:'旧卡附加部分'},source_refs:['known.md']}}],sessions:[]});
    mocks.create.mockResolvedValue({session:{session_id:'legacy-chat',known_archive:[],turns:[]}});
    const wrapper=mount(CharacterChatPanel,{props:{projectRoot:'C:/works/rain'},global:{stubs:{Teleport:true}}});
    await flushPromises();await wrapper.findAll('select')[0].setValue('legacy');
    await wrapper.findAll('button').find(button=>button.text()==='查看与编辑角色卡')!.trigger('click');
    expect(wrapper.text()).toContain('人格核心');
    await wrapper.findAll('button').find(button=>button.text()==='加载并开始新对话')!.trigger('click');
    await flushPromises();
    expect(mocks.create.mock.calls[0][1].schema).toBe('arcvellum/actor-character-card/v1');
    expect(mocks.create.mock.calls[0][1].sections.PERSONALITY_CORE).toBe('旧卡附加部分');
    wrapper.unmount();
  });

  it("keeps an old work's late reply out of the newly selected work", async () => {
    const session = { session_id:"old-chat", target:"阿青", context:"窗边", known_archive:[],system_prompt:"角色卡",turns:[] };
    mocks.create.mockResolvedValue({ session });
    let finish!: (value: unknown) => void;
    mocks.ask.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const wrapper = mount(CharacterChatPanel, { props:{projectRoot:"C:/works/old"},global:{stubs:{Teleport:true}} });
    await flushPromises(); await wrapper.findAll("select")[0].setValue("card-1");
    await wrapper.findAll("button").find(button => button.text()==="加载并开始新对话")!.trigger("click");
    await flushPromises(); await wrapper.find("form textarea").setValue("等我回来。");
    await wrapper.find("form").trigger("submit");
    await wrapper.setProps({projectRoot:"C:/works/new"}); await flushPromises();
    finish({session:{...session,turns:[{message:"等我回来。",answer:"来自旧作品的迟到回复"}]}});
    await flushPromises();
    expect(wrapper.text()).not.toContain("来自旧作品的迟到回复");
    expect(wrapper.find("form").exists()).toBe(false);
    expect(mocks.ask).toHaveBeenCalledWith("C:/works/old","old-chat","等我回来。");
    wrapper.unmount();
  });
});

