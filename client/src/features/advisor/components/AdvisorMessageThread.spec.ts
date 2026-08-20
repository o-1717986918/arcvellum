import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import AdvisorMessageThread from "./AdvisorMessageThread.vue";

describe("AdvisorMessageThread", () => {
  it("safely renders Markdown and delegates notices and workspace actions", async () => {
    const action = { type: "open_view" as const, label: "打开正文", target: "reader" as const };
    const notice = { item_id: "notice-1", unread: true, title: "需要决定", message: "请选择分支。", action };
    const wrapper = mount(AdvisorMessageThread, {
      props: {
        messages: [{
          role: "advisor",
          payload: {
            message: "**先看正文**<script>alert(1)</script>",
            evidence: [{ statement: "第二场已晋升", citation: "scene_0002" }],
            uncertainties: ["下一场视角未定"],
            suggested_actions: [action],
          },
        }],
        inbox: [notice],
        loadingSession: false,
        actionBusy: "",
      },
    });

    expect(wrapper.get(".advisor-markdown strong").text()).toBe("先看正文");
    expect(wrapper.html()).not.toContain("<script>");
    expect(wrapper.text()).toContain("第二场已晋升");
    await wrapper.get(".advisor-actions button").trigger("click");
    expect(wrapper.emitted("action")?.[0]).toEqual([action]);
    await wrapper.findAll(".advisor-inbox button").at(-1)!.trigger("click");
    expect(wrapper.emitted("notice")?.at(-1)).toEqual([notice, false]);
  });
});
