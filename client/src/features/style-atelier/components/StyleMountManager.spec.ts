import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import StyleMountManager from "./StyleMountManager.vue";
import type { StyleMountPreview, StyleVersion } from "../types";

describe("StyleMountManager", () => {
  it("keeps the exact-version impact visible before confirmation", async () => {
    const wrapper = mount(StyleMountManager, {
      props: {
        version: versionFixture(),
        activeMount: {
          style_id: "classic-style",
          version_id: "v1-stable",
          content_hash: "sha256:style-v1",
        },
        preview: previewFixture(),
        busy: false,
      },
      global: { stubs: { Teleport: true } },
    });

    expect(wrapper.text()).toContain("已晋升正文保留原有版本证据");
    expect(wrapper.text()).toContain("1 个未晋升场景需要刷新");
    expect(wrapper.text()).toContain("scene_0002");
    expect(wrapper.text()).toContain("上下文");
    expect(wrapper.text()).toContain("场景编排");

    await wrapper.get(".style-confirm-mount").trigger("click");
    await wrapper.get(".style-icon-button").trigger("click");

    expect(wrapper.emitted("confirm")).toHaveLength(1);
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("does not offer mounting before the immutable version is built", () => {
    const wrapper = mount(StyleMountManager, {
      props: {
        version: {
          ...versionFixture(),
          state: "prompt-candidate",
          built: false,
        },
        activeMount: {},
        preview: null,
        busy: false,
      },
    });

    expect(wrapper.get(".style-mount-preview-button").attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("等待构建与审查");
  });
});

function versionFixture(): StyleVersion {
  return {
    style_id: "classic-style",
    version_id: "v2-reviewed",
    author_id: "classic-author",
    profile_id: "restrained",
    display_name: "克制叙事（二版）",
    state: "built",
    source_count: 3,
    accepted_evaluation_count: 1,
    review_status: "pass",
    content_hash: "sha256:style-v2",
    built: true,
    mounted: false,
  };
}

function previewFixture(): StyleMountPreview {
  return {
    schema: "arcvellum/style-mount-preview/v1",
    status: "confirmation-required",
    revision: "sha256:mount-preview-v2",
    current: {
      style_id: "classic-style",
      version_id: "v1-stable",
      content_hash: "sha256:style-v1",
    },
    target: {
      style_id: "classic-style",
      version_id: "v2-reviewed",
      content_hash: "sha256:style-v2",
    },
    comparison: {
      status: "changed",
      changes: [{
        field: "content_hash",
        label: "版本证据",
        before: "sha256:style-v1",
        after: "sha256:style-v2",
        changed: true,
      }],
      evidence: [{
        field: "prompt_chars",
        label: "提示词细节",
        before: 980,
        after: 1240,
        changed: true,
      }],
    },
    impact: {
      status: "would-propagate",
      mount_changes: true,
      affected_scene_count: 1,
      affected_artifact_count: 2,
      historical_artifact_count: 1,
      inspected_artifact_count: 3,
      entries: [{
        scene_id: "scene_0002",
        stages: ["context", "composition"],
        artifact_count: 2,
        recorded_versions: ["v1-stable"],
        reason: "unpromoted scene evidence uses the previous mounted style",
      }],
      invalidated_stages: ["context", "composition"],
      historical_prose: "preserved",
      revision: "sha256:mount-impact-v2",
    },
    requires_confirmation: true,
  };
}
