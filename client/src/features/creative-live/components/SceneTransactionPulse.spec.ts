import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SceneTransactionPulse from "./SceneTransactionPulse.vue";

describe("SceneTransactionPulse", () => {
  it("renders literary progress without protocol internals", () => {
    const wrapper = mount(SceneTransactionPulse, {
      props: {
        transaction: {
          transaction_id: "scene-tx-secret",
          scene_id: "scene_0007",
          status: "reviewing",
          mode: "standard",
          risk: "standard",
          objective: "让迟到的回信改变两人的关系",
          scene_function: "relationship-turn",
          body_hanzi: 1832,
          warning_count: 1,
          hard_issue_count: 0,
          review_decision: "",
          review_summary: "",
          revision_attempts: 0,
          requires_input: false,
          message: "",
          version: 4,
        },
      },
    });

    expect(wrapper.text()).toContain("让迟到的回信改变两人的关系");
    expect(wrapper.text()).toContain("审读");
    expect(wrapper.text()).toContain("1 条提示");
    expect(wrapper.text()).not.toContain("scene-tx-secret");
  });
});
