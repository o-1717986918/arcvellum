import { describe, expect, it } from "vitest";
import { activityMessage, activityTitle, hasTechnicalDetail, sessionDisplayName, transcriptPresentation } from "./creativePresentation";
import type { CreativeActivity, CreativeSession } from "./types";

const session: CreativeSession = {
  session_id: "session-1",
  role: "worker",
  runtime: "pi-worker",
  status: "running",
  route: "scene-development",
  task_id: "scene-1",
  transcript: "",
  tools: [],
};

const activity: CreativeActivity = {
  event_id: "event-1",
  event: "task.failed",
  channel: "activity",
  at: "2026-09-21T08:00:00Z",
  task_id: "scene-1",
  route: "scene-development",
  title: "创作现场更新",
  message: "Command failed with exit code 1: python worker.py",
};

describe("Creative Live presentation", () => {
  it("names a worker session by its creative responsibility", () => {
    expect(sessionDisplayName(session)).toBe("正文主创");
    expect(sessionDisplayName({ ...session, role: "独立审读" })).toBe("独立审读");
  });

  it("uses the typed event for a specific title and summarizes raw command errors", () => {
    expect(activityTitle(activity)).toBe("创作任务未完成");
    expect(activityMessage(activity)).toContain("技术详情已保留");
    expect(activityMessage(activity)).not.toContain("python worker.py");
    expect(hasTechnicalDetail(activity)).toBe(true);
  });

  it("summarizes planning JSON and keeps the exact machine payload behind details", () => {
    const raw = JSON.stringify({
      premise: "雾港中的旧记录重新出现。",
      central_question: "谁改写了潮位？",
      chapters: [{ title: "回声", dramatic_turn: "记录指向父亲" }],
      first_window: [{ name: "检修浮标", function: "发现异常" }],
      characters: [{ name: "林雾", role: "浮标工程师" }],
    });

    const result = transcriptPresentation(raw);

    expect(result.structured).toBe(true);
    expect(result.source).toContain("章节骨架（1）");
    expect(result.source).toContain("林雾 — 浮标工程师");
    expect(result.source).not.toContain("first_window");
    expect(result.raw).toBe(raw);
  });

  it("uses the latest complete object when streamed planning answers are concatenated", () => {
    const first = JSON.stringify({ premise: "旧前提", chapters: [{ title: "旧章", dramatic_turn: "旧转向" }] });
    const latest = JSON.stringify({ premise: "修正前提", chapters: [{ title: "新章", dramatic_turn: "新转向" }] });

    const result = transcriptPresentation(`${first}${latest}{"premise":"未完成`);

    expect(result.structured).toBe(true);
    expect(result.source).toContain("修正前提");
    expect(result.source).toContain("新章 — 新转向");
    expect(result.source).not.toContain("旧前提");
  });
});
