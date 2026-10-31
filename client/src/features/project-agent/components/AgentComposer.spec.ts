import { beforeEach, describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import AgentComposer from "./AgentComposer.vue";

beforeEach(() => localStorage.clear());
describe("conversation drafts", () => {
  it("keeps a draft until the durable request is acknowledged", async () => {
    const wrapper = mount(AgentComposer, { props: { sessionId: "a" } });
    await wrapper.get("textarea").setValue("写下一章");
    await wrapper.get("form").trigger("submit");
    expect(wrapper.get("textarea").element.value).toBe("写下一章");
    expect(localStorage.getItem("arcvellum.draft.a")).toBe("写下一章");
    const [message, accept] = wrapper.emitted("send")![0] as [string, () => void];
    expect(message).toBe("写下一章");
    accept();
    expect(localStorage.getItem("arcvellum.draft.a")).toBeNull();
    wrapper.unmount();
  });
  it("preserves newer typing when a previous send is acknowledged", async () => {
    const wrapper = mount(AgentComposer, { props: { sessionId: "a" } });
    await wrapper.get("textarea").setValue("原消息");
    await wrapper.get("form").trigger("submit");
    await wrapper.get("textarea").setValue("还有一个想法");
    (wrapper.emitted("send")![0][1] as () => void)();
    expect(wrapper.get("textarea").element.value).toBe("还有一个想法");
    wrapper.unmount();
  });
  it("keeps independent drafts across sessions and reloads", async () => {
    const wrapper = mount(AgentComposer, { props: { sessionId: "a" } });
    await wrapper.get("textarea").setValue("作品甲");
    await wrapper.setProps({ sessionId: "b" });
    expect(wrapper.get("textarea").element.value).toBe("");
    await wrapper.get("textarea").setValue("作品乙");
    await wrapper.setProps({ sessionId: "a" });
    expect(wrapper.get("textarea").element.value).toBe("作品甲");
    wrapper.unmount();
    const restored = mount(AgentComposer, { props: { sessionId: "b" } });
    expect(restored.get("textarea").element.value).toBe("作品乙");
    restored.unmount();
  });
  it("does not submit an IME confirmation, Shift Enter or a busy draft", async () => {
    const wrapper = mount(AgentComposer, { props: { sessionId: "a" } });
    const input = wrapper.get("textarea");
    await input.setValue("中文创作");
    await input.trigger("compositionstart");
    await input.trigger("keydown", { key: "Enter" });
    await input.trigger("compositionend");
    await input.trigger("keydown", { key: "Enter", isComposing: true });
    await input.trigger("keydown", { key: "Enter", shiftKey: true });
    await wrapper.setProps({ busy: true });
    await input.trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("send")).toBeUndefined();
    expect(input.element.value).toBe("中文创作");
    wrapper.unmount();
  });
});
