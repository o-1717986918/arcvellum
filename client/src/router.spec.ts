import { describe, expect, it } from "vitest";
import { router } from "./router";

describe("legacy project viewing routes", () => {
  it.each([
    ["/reader", "reader"],
    ["/archive", "archive"],
    ["/style", "style"],
    ["/quality", "quality"],
    ["/strategy", "quality"],
    ["/delivery", "delivery"],
    ["/settings", "settings"],
    ["/help", "help"],
    ["/details", "details"],
    ["/legal", "legal"],
  ])("redirects %s into the Agent child workspace", async (path, workspace) => {
    await router.push(path);
    expect(router.currentRoute.value.name).toBe("project-agent");
    expect(router.currentRoute.value.query.workspace).toBe(workspace);
  });

  it("opens the conversation chooser from the old projects route", async () => {
    await router.push("/projects");
    expect(router.currentRoute.value.name).toBe("project-agent");
    expect(router.currentRoute.value.query.new).toBe("1");
  });

  it("opens the creative live workspace from the old observatory route", async () => {
    await router.push("/observatory");
    expect(router.currentRoute.value.name).toBe("project-agent");
    expect(router.currentRoute.value.query.workspace).toBe("live");
  });

  it("keeps the narrative orrery as a first-class mode", async () => {
    await router.push("/overview");
    expect(router.currentRoute.value.name).toBe("overview");
    expect(router.currentRoute.value.redirectedFrom).toBeUndefined();
  });
});

describe("workspace links", () => {
  it.each([["reader", "reader"], ["library", "archive"], ["delivery", "delivery"], ["observatory", "live"], ["character-chat", "character-chat"]])(
    "keeps the originating session through /%s", async (path, workspace) => {
      await router.push(`/${path}?session=work-session&target=记录员`);
      expect(router.currentRoute.value.name).toBe("project-agent");
      expect(router.currentRoute.value.query).toMatchObject({ session: "work-session", workspace, target: "记录员" });
    },
  );
});
