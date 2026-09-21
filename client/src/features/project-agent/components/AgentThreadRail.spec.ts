import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AgentThreadRail from "./AgentThreadRail.vue";

describe("AgentThreadRail", () => {
  it("keeps a long history bounded until the user expands it", async () => {
    const sessions = Array.from({ length: 12 }, (_, index) => ({
      session_id: `session-${index}`,
      project_root: "C:/works/tide",
      title: `对话 ${index + 1}`,
      session_kind: "project-agent" as const,
      updated_at: new Date(2026, 8, 21 - index).toISOString(),
      created_at: new Date(2026, 8, 21 - index).toISOString(),
    }));
    const wrapper = mount(AgentThreadRail, {
      props: { sessions, activeSessionId: "session-11", projectTitle: "潮线", hasProject: true },
    });

    expect(wrapper.findAll(".pa-thread-list > button:not(.pa-thread-more)")).toHaveLength(9);
    expect(wrapper.text()).toContain("显示其余 3 个对话");

    await wrapper.get(".pa-thread-more").trigger("click");
    expect(wrapper.findAll(".pa-thread-list > button:not(.pa-thread-more)")).toHaveLength(12);
    expect(wrapper.text()).toContain("收起历史对话");
  });

  it("opens viewing workspaces without navigating away from the Agent desktop", async () => {
    const wrapper = mount(AgentThreadRail, {
      props: {
        sessions: [],
        projectTitle: "潮线",
        projectProgress: 24,
        hasProject: true,
      },
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });

    const projectButtons = wrapper.findAll(".pa-workspace-links:not(.pa-application-links) button");
    const appButtons = wrapper.findAll(".pa-application-links button");
    expect(projectButtons).toHaveLength(7);
    expect(appButtons).toHaveLength(4);

    await projectButtons[0].trigger("click");
    expect(wrapper.emitted("workspace")?.[0]).toEqual(["reader"]);

    await projectButtons[1].trigger("click");
    expect(wrapper.emitted("workspace")?.[1]).toEqual(["live"]);

    await appButtons[0].trigger("click");
    expect(wrapper.emitted("workspace")?.[2]).toEqual(["settings"]);
  });

  it("keeps application settings available before a project is selected", () => {
    const wrapper = mount(AgentThreadRail, {
      props: { sessions: [], projectTitle: "尚未选择作品", projectProgress: 0, hasProject: false },
      global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
    });

    expect(wrapper.findAll(".pa-workspace-links:not(.pa-application-links) button").every((button) => button.attributes("disabled") !== undefined)).toBe(true);
    expect(wrapper.findAll(".pa-application-links button").every((button) => button.attributes("disabled") === undefined)).toBe(true);
  });
});
