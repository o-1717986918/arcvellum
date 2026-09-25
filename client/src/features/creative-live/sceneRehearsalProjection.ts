import type { CreativeLiveEvent, SceneRehearsalDetail, SceneRehearsalTurn } from "./types";

export function rehearsalTurnFromEvent(event: CreativeLiveEvent): SceneRehearsalTurn | null {
  if (event.event !== "scene.performance.interaction.turn") return null;
  const data = event.data;
  const turn = Number(data.turn);
  const speaker = typeof data.speaker === "string" ? data.speaker : "";
  if (!Number.isInteger(turn) || turn < 1 || !speaker) return null;
  const raw = Array.isArray(data.turn_entries) ? data.turn_entries : [];
  return {
    turn, speaker, beat_id: String(data.beat_id || ""), source: String(data.source || "rehearsal"),
    entries: raw.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
      .map((item) => ({
        entry_id: String(item.entry_id || ""), spoken: String(item.spoken || ""),
        first_person_action: String(item.first_person_action || ""),
      })),
  };
}

export function applyRehearsalTurn(detail: SceneRehearsalDetail, event: CreativeLiveEvent): SceneRehearsalDetail {
  const turn = rehearsalTurnFromEvent(event);
  if (!turn || String(event.data.scene_transaction_id || "") !== detail.transaction_id) return detail;
  const turns = [...detail.turns.filter((item) => item.turn !== turn.turn), turn].sort((a, b) => a.turn - b.turn);
  return { ...detail, turns, turn_count: turns.length, updated_at: event.at || detail.updated_at };
}

export function rehearsalSpeakerSide(turns: SceneRehearsalTurn[], speaker: string): "left" | "right" {
  const names = [...new Set(turns.map((item) => item.speaker))];
  return names.indexOf(speaker) % 2 === 0 ? "right" : "left";
}
