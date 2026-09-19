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

  it("returns the old observatory route to the conversation with its right rail", async () => {
    await router.push("/observatory");
    expect(router.currentRoute.value.name).toBe("project-agent");
    expect(router.currentRoute.value.query.workspace).toBeUndefined();
  });

  it("keeps the narrative orrery as a first-class mode", async () => {
    await router.push("/overview");
    expect(router.currentRoute.value.name).toBe("overview");
    expect(router.currentRoute.value.redirectedFrom).toBeUndefined();
  });
});
