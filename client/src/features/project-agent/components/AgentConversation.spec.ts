import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AgentConversation from "./AgentConversation.vue";

describe("AgentConversation creative activity", () => {
  it("keeps the live entry visible while work runs or needs attention", async () => {
    const wrapper = mount(AgentConversation, {
      props: {
        messages: [],
        activity: null,
        loading: false,
        omittedCount: 0,
        hasSession: true,
        creativePhase: "active",
        creativeStatus: "正在形成正文",
        creativeTask: "第三章",
      },
    });

    const card = wrapper.find(".pa-creative-live-card");
    expect(card.text()).toContain("创作正在进行");
    await card.trigger("click");
    expect(wrapper.emitted("openLive")).toHaveLength(1);

    await wrapper.setProps({ creativePhase: "waiting", creativeStatus: "创作已暂停，等待继续" });
    expect(wrapper.find(".pa-creative-live-card").text()).toContain("创作等待继续");

    await wrapper.setProps({ creativePhase: "attention", creativeStatus: "创作遇到问题，需要处理" });
    expect(wrapper.find(".pa-creative-live-card").text()).toContain("创作需要处理");

    await wrapper.setProps({ creativePhase: null });
    expect(wrapper.find(".pa-creative-live-card").exists()).toBe(false);
  });
});
