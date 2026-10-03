import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CharacterChatPanel from "./CharacterChatPanel.vue";
const mocks = vi.hoisted(() => ({ setup: vi.fn(), archive: vi.fn(), create: vi.fn(), ask: vi.fn(), session: vi.fn(), draftCard: vi.fn() }));
vi.mock("./services/characterChatClient", () => ({ characterChatClient: mocks }));
describe("character dialogue panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.setup.mockResolvedValue({ sections: ["PERSONA_LOAD"], cards: [{
      digest: "card-1", scene_id: "s1", card: { target: "阿青", sections: { PERSONA_LOAD: "独特声线" }, source_refs: ["known.md"] },
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
});

