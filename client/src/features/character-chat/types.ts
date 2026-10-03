export interface CharacterCard {
  schema: "arcvellum/actor-character-card/v1";
  target: string;
  sections: Record<string, string>;
  source_refs: string[];
  notes: string;
}
export interface KnownAttachment {
  path: string; start_line: number | null; end_line: number | null; knowledge: "known";
}
export interface CharacterChatSession {
  session_id: string; target: string; context: string; card: CharacterCard;
  system_prompt: string; system_sha256: string; updated_at: string;
  known_archive: Array<{ path: string; line_range: number[]; content: string; file_sha256: string }>;
  turns: Array<{ message: string; answer: string; at: string }>;
}
export interface CharacterChatSetup {
  sections: string[]; system_template: string;
  cards: Array<{ card: CharacterCard; scene_id: string; digest: string }>;
  sessions: Array<{ session_id: string; target: string; updated_at: string }>;
}

