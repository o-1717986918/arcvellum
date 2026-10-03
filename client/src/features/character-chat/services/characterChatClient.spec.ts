import { describe, expect, it } from "vitest";
import { MockFeatureTransport } from "@/testing/mockFeatureTransport";
import { createCharacterChatClient } from "./characterChatClient";
import type { CharacterCard } from "../types";

describe("isolated character dialogue client", () => {
  it("keeps the chosen work, facts and independent context on each request", async () => {
    const transport = new MockFeatureTransport();
    const client = createCharacterChatClient(transport);
    transport.respond("POST", "/character-chat/sessions", { session: { session_id: "separate-1" } });
    const card: CharacterCard = { schema: "arcvellum/actor-character-card/v1", target: "阿青",
      sections: { PERSONA_LOAD: "尖锐的语感" }, source_refs: ["characters/qing.yaml"], notes: "" };
    const mounts = [{ path: "known.md", start_line: 1, end_line: 2, knowledge: "known" as const }];
    await client.create("C:/works/rain", card, mounts, "独立的雨后场景");
    expect(transport.lastCall("request")?.body).toEqual({
      project_root: "C:/works/rain", target: "阿青", card, attachments: mounts, context: "独立的雨后场景",
    });
    transport.respond("POST", "/character-chat/sessions/separate-1/ask", { session: { turns: [] } });
    await client.ask("C:/works/rain", "separate-1", "你看见信了吗？");
    expect(transport.lastCall("request")?.body).toEqual({ project_root: "C:/works/rain", message: "你看见信了吗？" });
    expect(transport.lastCall("request")?.path).not.toContain("scene-transactions");
  });
});

