import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AgentThreadRail from "./AgentThreadRail.vue";

describe("AgentThreadRail", () => {
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
    expect(projectButtons).toHaveLength(9);
    expect(appButtons).toHaveLength(5);

    await projectButtons[0].trigger("click");
    expect(wrapper.emitted("workspace")?.[0]).toEqual(["reader"]);

    await appButtons[1].trigger("click");
    expect(wrapper.emitted("workspace")?.[1]).toEqual(["settings"]);
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
