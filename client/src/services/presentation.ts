const LABELS: Record<string, string> = {
  drafts: "正文",
  characters: "人物",
  world: "世界观",
  scenes: "场景",
  branches: "推演分支",
  style: "文风",
  reviews: "审查",
  word_budget: "字数规划",
  rhythm: "叙事节奏",
  canon_patches: "设定更新",
  "scene-development": "场景创作",
  "longform-planning": "长篇规划",
  "style-engineering": "文风学习",
  "character-and-world-assets": "人物与世界",
  "review-and-audit": "质量审查",
  "export-and-release": "交付出版",
  "source-ingest": "作品导入",
};

export function labelFor(value: unknown): string {
  const key = String(value || "");
  return LABELS[key] || humanize(key);
}

export function humanize(value: string): string {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

export function asList<T = Record<string, unknown>>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "尚未填写";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.map(displayValue).filter(Boolean).join("、");
  if (typeof value === "object") {
    const record = asRecord(value);
    return String(record.title || record.label || record.name || record.content || record.message || "已记录");
  }
  return String(value);
}

export function formatCount(value: unknown): string {
  const number = Number(value || 0);
  return Number.isFinite(number) ? new Intl.NumberFormat("zh-CN").format(number) : "0";
}

export function targetLabel(value: unknown): string {
  const text = String(value || "");
  const scene = text.match(/^scene[_-]?(\d+)$/i);
  if (scene) return `场景 ${scene[1]}`;
  const chapter = text.match(/^chapter[_-]?(\d+)$/i);
  if (chapter) return `第 ${Number(chapter[1])} 章`;
  if (text === "project-review") return "整部作品";
  if (text === "longform") return "全书规模";
  return text || "当前作品";
}

export function workflowStepLabel(value: unknown): string {
  const text = String(value || "").toLowerCase();
  const mapping: Array<[string, string]> = [
    ["context", "整理场景资料"],
    ["roleplay", "人物处境推演"],
    ["branch", "剧情分支比较"],
    ["composition", "场景编排"],
    ["generation", "正文创作"],
    ["agent-review", "语义审查"],
    ["review", "质量审查"],
    ["promotion", "确认正式正文"],
    ["state", "更新人物状态"],
    ["canon", "核对世界设定"],
    ["word-budget", "字数与场景规划"],
    ["longform", "长篇结构规划"],
    ["chapter", "章节汇整"],
    ["export", "正式交付"],
  ];
  return mapping.find(([needle]) => text.includes(needle))?.[1] || labelFor(text);
}

export function describeWorkflowAction(value: unknown): string {
  const text = String(value || "").toLowerCase();
  const mapping: Array<[string[], string]> = [
    [["context"], "整理这一场需要的人物、设定和前情。"],
    [["simulate-scene", "roleplay"], "让人物按各自处境推演下一步选择。"],
    [["branch-simulate", "branch"], "比较可行的剧情分支及其长期代价。"],
    [["compose-scene", "composition"], "把本场目标、节奏和衔接整理成写作方案。"],
    [["generate-scene", "generation"], "按照既定文风和约束创作本场正文。"],
    [["agent-review", "review"], "审查正文是否符合人物、文风、设定和字数目标。"],
    [["promote"], "将通过审查的版本确认为正式正文。"],
    [["state-evolve", "state"], "记录人物关系、认知和状态的变化。"],
    [["canon-lint", "canon-review"], "确认本次变化没有破坏世界设定。"],
    [["chapter-workspace", "chapter"], "把已完成场景汇整成连贯章节。"],
    [["word-budget", "longform-budget"], "核对目标篇幅、剧情库存和各场字数。"],
    [["export", "release"], "整理通过门禁的正文并生成交付文件。"],
  ];
  const match = mapping.find(([needles]) => needles.some((needle) => text.includes(needle)));
  if (match) return match[1];
  return text ? "按照作品当前状态继续下一项正式工作。" : "等待下一项创作任务。";
}

export function describeGate(value: unknown): string {
  const text = String(value || "");
  if (!text) return "仍有步骤需要完成。";
  if (/review/i.test(text)) return "这一部分还缺少完整的质量审查。";
  if (/style/i.test(text)) return "文风要求尚未完整进入本次创作。";
  if (/budget|word.count/i.test(text)) return "字数目标和实际正文仍需对齐。";
  if (/canon/i.test(text)) return "世界设定变化仍需确认。";
  if (/task|sidecar/i.test(text)) return "有一项创作任务尚未完成。";
  if (/promot/i.test(text)) return "正文还没有通过晋升确认。";
  return "这条路线仍有必要步骤需要完成。";
}

export function sectionEntries(sections: unknown): Array<[string, Record<string, unknown>[]]> {
  if (Array.isArray(sections)) {
    return sections.map((section, index) => {
      const record = asRecord(section);
      return [String(record.id || record.key || index), asList(record.items)];
    });
  }
  return Object.entries(asRecord(sections)).map(([key, value]) => [key, asList(value)]);
}

export function manuscriptItems(library: Record<string, unknown> | null): Record<string, unknown>[] {
  if (!library) return [];
  const completed = asRecord(library.completed_prose);
  const completedItems = asList<Record<string, unknown>>(completed.items);
  if (completedItems.length) return completedItems;
  const sections = asRecord(library.sections);
  return asList<Record<string, unknown>>(sections.drafts).filter((item) =>
    ["promoted", "chapter", "exported", "published"].includes(String(item.status || "")),
  );
}
