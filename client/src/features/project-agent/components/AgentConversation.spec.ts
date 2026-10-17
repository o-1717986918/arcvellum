import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AgentConversation from "./AgentConversation.vue";
import type { ProjectAgentTurnActivity } from "../types";

const activity: ProjectAgentTurnActivity = {
  jobId: "job-current", turnId: "turn-current", status: "complete", statusLabel: "已完成",
  reasoning: "", inputTokens: 0, outputTokens: 0, startedAt: Date.now(),
  tools: [{ key: "read-1", name: "project_overview", label: "查看作品进度", status: "complete" }],
};

describe("AgentConversation creative activity", () => {
  it("places collapsible tools before their matching answer and preserves records after reopening", async () => {
    const wrapper = mount(AgentConversation, { props: { loading: false, omittedCount: 0, activity,
      messages: [{ role: "assistant", payload: { text: "上一轮回答", turn_id: "turn-old" } },
        { role: "user", payload: { text: "检查作品" } },
        { role: "assistant", payload: { text: "当前回答", turn_id: activity.turnId } }] } });
    const turns = wrapper.findAll(".pa-turn-agent");
    expect(turns[0].find(".pa-action-group").exists()).toBe(false);
    const panel = turns[1].find(".pa-action-group");
    const heading = panel.find("button");
    expect(heading.attributes("aria-expanded")).toBe("false");
    expect(panel.find(".pa-action-body").exists()).toBe(false);
    expect(turns[1].html().indexOf("pa-action-group")).toBeLessThan(turns[1].html().indexOf('class="safe-markdown'));
    await heading.trigger("click");
    expect(heading.attributes("aria-expanded")).toBe("true");
    expect(panel.find('[role="region"]').attributes("tabindex")).toBe("0");
    expect(panel.find(".pa-tool-row").text()).toContain("查看作品进度");
    await heading.trigger("click");
    await heading.trigger("click");
    expect(panel.findAll(".pa-tool-row")).toHaveLength(1);
  });

  it("keeps streaming tool activity above the pending body without attaching it to an old answer", () => {
    const wrapper = mount(AgentConversation, { props: { loading: false, omittedCount: 0,
      activity: { ...activity, status: "running" }, messages: [
        { role: "assistant", payload: { text: "旧回答", job_id: "job-old" } },
        { role: "user", payload: { text: "继续" } },
        { role: "assistant", payload: { text: "" } }] } });
    const turns = wrapper.findAll(".pa-turn-agent");
    expect(turns[0].find(".pa-action-group").exists()).toBe(false);
    expect(turns[1].find(".pa-action-group").exists()).toBe(true);
    expect(turns[1].html().indexOf("pa-action-group")).toBeLessThan(turns[1].html().indexOf("pa-thinking"));
  });

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
