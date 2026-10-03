import type { ApiTransport } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type { CharacterCard, CharacterChatSession, CharacterChatSetup, KnownAttachment } from "../types";

export function createCharacterChatClient(transport: ApiTransport = featureTransport) {
  const q = transport.query;
  return {
    setup: (projectRoot: string) => transport.request<CharacterChatSetup>(
      `/character-chat/setup?${q({ project_root: projectRoot })}`),
    archive: (projectRoot: string, cursor = 0) => transport.request<{
      entries: Array<{ path: string; status: string }>; next_cursor: number | null;
    }>(`/character-chat/archive?${q({ project_root: projectRoot, cursor })}`),
    readArchive: (projectRoot: string, path: string, offset = 0) => transport.request<{
      content: string; next_offset: number | null; total_lines: number;
    }>(`/character-chat/archive/read?${q({ project_root: projectRoot, path, offset })}`),
    create: (projectRoot: string, card: CharacterCard, attachments: KnownAttachment[], context: string) =>
      transport.request<{ session: CharacterChatSession }>("/character-chat/sessions", {
        method: "POST", body: JSON.stringify({ project_root: projectRoot, target: card.target, card, attachments, context }),
      }),
    draftCard: (projectRoot: string, target: string, attachments: KnownAttachment[], context: string) =>
      transport.request<{ card: CharacterCard; draft_text: string }>("/character-chat/cards/draft", {
        method: "POST", body: JSON.stringify({ project_root: projectRoot, target, attachments, context }),
      }),
    session: (projectRoot: string, sessionId: string) => transport.request<{ session: CharacterChatSession }>(
      `/character-chat/sessions/${encodeURIComponent(sessionId)}?${q({ project_root: projectRoot })}`),
    ask: (projectRoot: string, sessionId: string, message: string) =>
      transport.request<{ session: CharacterChatSession }>(
        `/character-chat/sessions/${encodeURIComponent(sessionId)}/ask`, {
          method: "POST", body: JSON.stringify({ project_root: projectRoot, message }),
        }),
  };
}
export const characterChatClient = createCharacterChatClient();

