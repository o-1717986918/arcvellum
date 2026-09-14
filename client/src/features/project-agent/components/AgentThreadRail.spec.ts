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
      },
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });

    const buttons = wrapper.findAll(".pa-workspace-links button");
    expect(buttons).toHaveLength(9);
    expect(wrapper.findAll(".pa-workspace-links a")).toHaveLength(0);

    await buttons[0].trigger("click");
    expect(wrapper.emitted("workspace")?.[0]).toEqual(["reader"]);
  });
});
