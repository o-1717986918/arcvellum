export interface ScenePromptInspection {
  transaction_id: string;
  style_bundle: null | { digest: string; preset_revision: number; selection: { preset_id: string; reason: string };
    style: { assembled: { content: string } }; measurement: { enabled: boolean; usage: string } };
  prompt_assembly: null | { response_mode?: string; [key: string]: unknown };
  creator_briefing: unknown; tone_mount: null | { enabled: boolean };
  submitted_inputs: { role: string; prompt: string; system_prompt: string; history: unknown[]; digest: string; stage: string }[];
  edits: { input_digest: string; phase: string; summary: string; accepted: unknown[]; original: string; cleaned: string }[];
  measurements: { text_sha256: string; error?: string; stages?: string[];
    result?: { targets?: { id: string; label: string; unit: string; min: number; max: number; observed: number | null; distance: number | null }[] };
    [key: string]: unknown }[];
}
