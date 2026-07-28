import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import StyleEngineeringConsole from "./StyleEngineeringConsole.vue";

describe("StyleEngineeringConsole", () => {
  it("prepares a valid profile identity and lets the user start once sources are partitioned", async () => {
    const wrapper = mount(StyleEngineeringConsole, {
      props: {
        authors: [{
          author_id: "classic-author",
          name: "古典作者",
          rights: { status: "declared", mode: "public-domain", declaration: "公版文本" },
          work_count: 1,
          profile_count: 0,
          works: [{
            work_id: "work-one",
            title: "作品一",
            source_count: 2,
            sources: [
              { source_id: "source-one", filename: "one.txt", media_type: "text/plain", character_count: 1000, chunk_count: 2, content_sha256: "sha256:one" },
              { source_id: "source-two", filename: "two.txt", media_type: "text/plain", character_count: 900, chunk_count: 2, content_sha256: "sha256:two" },
            ],
          }],
        }],
        selectedAuthorId: "classic-author",
        selectedVersion: null,
        job: null,
        task: null,
        events: [],
        busy: false,
        streamError: "",
      },
    });

    await wrapper.find(".style-engineering-collapsed").trigger("click");
    await wrapper.find('input[placeholder="例如：克制而有余波的叙事"]').setValue("克制叙事");
    const identity = wrapper.find('input[placeholder="例如：restrained-prose"]');
    expect((identity.element as HTMLInputElement).value).toMatch(/^style-[a-z0-9]{7}$/);
    const action = wrapper.find(".style-engineering-setup button.primary");
    expect(action.attributes("disabled")).toBeUndefined();
    await action.trigger("click");

    expect(wrapper.emitted("compile")?.[0]?.[0]).toMatchObject({
      author_id: "classic-author",
      display_name: "克制叙事",
      training_sources: [{ work_id: "work-one", source_id: "source-one" }],
      holdout_sources: [{ work_id: "work-one", source_id: "source-two" }],
      runtime: "opencode",
    });
    wrapper.unmount();
  });
});
