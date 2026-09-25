import type { CreativeActivity, CreativeSession } from "./types";

const ROUTE_LABELS: Record<string, string> = {
  "scene-development": "正文主创",
  "character-world-assets": "人物与世界设定",
  "longform-planning": "长篇规划",
  "source-ingest": "资料整理",
  "style-development": "文风设计",
};

const EVENT_TITLES: Record<string, string> = {
  "task.opened": "创作任务已领取",
  "task.started": "创作任务已开始",
  "task.failed": "创作任务未完成",
  "task.transport_interrupted": "创作连接暂时中断",
  "task.transport_retry_scheduled": "正在恢复创作连接",
  "task.recovery_started": "正在尝试恢复任务",
  "task.recovery_succeeded": "创作任务已经恢复",
  "task.recovery_rejected": "当前任务需要重新开始",
  "runner.session.started": "主创会话已开始",
  "runner.session.finished": "主创会话已结束",
  "runner.warning": "创作执行需要留意",
  "writeback.approved": "候选内容已通过写入检查",
  "mutation.receipt": "正式作品已经更新",
  "validation.failed": "候选内容等待修订",
  "planning.validation_failed": "规划结构正在返修",
  "human.required": "需要你的选择",
  "worker.human.required": "需要你的选择",
};

const TECHNICAL_ERROR = /(?:traceback|stack trace|exit code|enoent|spawn\s|stderr|command failed|subprocess|\bat .+\.(?:py|ts|js):\d+)/i;

export function sessionDisplayName(session?: CreativeSession | null, index = 0): string {
  if (!session) return "等待主创 Agent";
  const role = String(session.role || "").trim();
  if (role && !["worker", "agent", "assistant"].includes(role.toLowerCase())) return role;
  const value = parseJsonObjects(String(session.transcript || "")).at(-1);
  if (value) {
    if (value.speaker && Array.isArray(value.entries)) return `角色演出 · ${value.speaker}`;
    if (Array.isArray(value.passages)) return "环境描写";
    if (value.next_speaker || value.scene_change) return "导演调度";
    if (Array.isArray(value.beats)) return "场景推演设计";
    if (typeof value.prose === "string") return value.decision_summary ? "主创修订" : "主创成稿";
    if (value.decision && value.summary) return "独立审读";
    if (value.premise || value.central_question) return "全书规划";
  }
  const route = ROUTE_LABELS[session.route] || "创作 Agent";
  return index > 0 ? `${route} ${index + 1}` : route;
}

export function activityTitle(item: CreativeActivity): string {
  const title = String(item.title || "").trim();
  if (title && !["创作现场更新", "创作状态更新"].includes(title)) return title;
  return EVENT_TITLES[item.event] || routeProgressTitle(item.route);
}

export function activityMessage(item: CreativeActivity): string {
  const message = String(item.message || "").trim();
  if (message && !TECHNICAL_ERROR.test(message)) return message;
  if (item.event.includes("failed") || item.event.includes("rejected")) {
    return "本步没有完成。技术详情已保留，可返回项目 Agent 调整或重试。";
  }
  if (item.event.includes("interrupted") || item.event.includes("retry")) {
    return "连接短暂中断，系统正在按项目规则恢复。";
  }
  return "项目已推进到下一步。";
}

export function hasTechnicalDetail(item: CreativeActivity): boolean {
  const message = String(item.message || "").trim();
  return Boolean(message && TECHNICAL_ERROR.test(message));
}

export interface TranscriptPresentation {
  source: string;
  raw: string;
  structured: boolean;
}

export function transcriptPresentation(source?: string): TranscriptPresentation {
  const raw = String(source || "").trim();
  if (!raw || !raw.startsWith("{")) return { source: raw, raw: "", structured: false };
  const values = parseJsonObjects(raw);
  const value = values.at(-1);
  if (value) {
    const lines = ["**结构化创作结果**"];
    appendPerformance(lines, value);
    appendFact(lines, "场景变化", value.scene_change);
    appendFact(lines, "下一位角色", value.next_speaker);
    appendFact(lines, "导演提示", value.cue);
    appendFact(lines, "导演补充", value.director_note);
    appendFact(lines, "主创修订说明", value.decision_summary);
    appendFact(lines, "审读结论", value.decision);
    appendFact(lines, "审读意见", value.summary);
    appendRows(lines, "场景节拍", value.beats, ["beat_id", "event"]);
    appendFact(lines, "故事前提", value.premise);
    appendFact(lines, "中心问题", value.central_question);
    appendFact(lines, "终局选择", value.ending_choice);
    appendRows(lines, "章节骨架", value.chapters, ["title", "dramatic_turn"]);
    appendRows(lines, "首窗场景", value.first_window || value.scenes, ["name", "function"]);
    appendRows(lines, "主要人物", value.characters, ["name", "role"]);
    const knownContent = lines.length > 1;
    if (!knownContent) lines.push("Agent 已返回一份机器可校验的结构化结果。");
    return { source: lines.join("\n\n"), raw, structured: true };
  }
  return { source: raw, raw: "", structured: false };
}

function appendPerformance(lines: string[], value: Record<string, unknown>): void {
  const speaker = String(value.speaker || "").trim();
  if (speaker && Array.isArray(value.entries)) {
    lines.push(`**${speaker}的演出**`);
    for (const entry of value.entries.slice(0, 12)) {
      const row = entry && typeof entry === "object" ? entry as Record<string, unknown> : {};
      appendFact(lines, "发言", row.spoken);
      appendFact(lines, "动作", row.first_person_action);
    }
  }
  if (Array.isArray(value.passages)) {
    for (const passage of value.passages.slice(0, 12)) {
      const row = passage && typeof passage === "object" ? passage as Record<string, unknown> : {};
      appendFact(lines, `环境片段 ${String(row.beat_id || "").trim()}`.trim(), row.description);
    }
  }
}

function parseJsonObjects(source: string): Array<Record<string, unknown>> {
  const values: Array<Record<string, unknown>> = [];
  let start = -1;
  let depth = 0;
  let quoted = false;
  let escaped = false;
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if (quoted) {
      if (escaped) escaped = false;
      else if (character === "\\") escaped = true;
      else if (character === '"') quoted = false;
      continue;
    }
    if (character === '"') {
      quoted = true;
      continue;
    }
    if (character === "{") {
      if (depth === 0) start = index;
      depth += 1;
    } else if (character === "}" && depth > 0) {
      depth -= 1;
      if (depth === 0 && start >= 0) {
        try {
          const parsed = JSON.parse(source.slice(start, index + 1)) as unknown;
          if (parsed && !Array.isArray(parsed) && typeof parsed === "object") {
            values.push(parsed as Record<string, unknown>);
          }
        } catch {
          // Keep scanning: a later complete object may still be usable.
        }
        start = -1;
      }
    }
  }
  return values;
}

function appendFact(lines: string[], label: string, value: unknown): void {
  const text = String(value || "").trim();
  if (text) lines.push(`**${label}：** ${text}`);
}

function appendRows(
  lines: string[],
  label: string,
  value: unknown,
  fields: [string, string],
): void {
  if (!Array.isArray(value) || !value.length) return;
  const rows = value.slice(0, 12).map((item, index) => {
    const row = item && typeof item === "object" ? item as Record<string, unknown> : {};
    const first = String(row[fields[0]] || `${label}${index + 1}`).trim();
    const second = String(row[fields[1]] || "").trim();
    return `${index + 1}. ${first}${second ? ` — ${second}` : ""}`;
  });
  lines.push(`**${label}（${value.length}）：**\n${rows.join("\n")}${value.length > rows.length ? "\n…" : ""}`);
}

function routeProgressTitle(route: string): string {
  const routeLabel = ROUTE_LABELS[route];
  return routeLabel ? `${routeLabel}正在推进` : "创作任务正在推进";
}
