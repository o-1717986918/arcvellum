import type { CreativeArtifact } from "./types";

const KIND_LABELS: Record<string, string> = {
  prose: "正文",
  character: "人物设定",
  world: "世界观",
  planning: "情节规划",
  style: "文风方案",
  review: "审查意见",
  "agent-authored": "创作资料",
};

export function artifactKindLabel(artifact?: CreativeArtifact | null): string {
  return KIND_LABELS[String(artifact?.kind || "agent-authored")] || "创作资料";
}

export function artifactTitle(artifact?: CreativeArtifact | null): string {
  if (!artifact) return "等待主创落笔";
  const heading = String(artifact.content || "").match(/^\s*#{1,3}\s+(.+?)\s*$/m)?.[1]?.trim();
  if (heading) return heading.slice(0, 80);
  const stem = artifact.path.split(/[\\/]/).pop()?.replace(/\.(md|txt)$/i, "") || "创作资料";
  return friendlyStem(stem);
}

export function artifactStatusLabel(artifact?: CreativeArtifact | null): string {
  if (!artifact) return "等待内容";
  if (artifact.identity === "streaming_preview" || artifact.identity === "revision_streaming") return "正在形成";
  if (artifact.identity === "promoted" || artifact.identity === "state_and_canon_applied") return "已纳入项目";
  if (artifact.identity === "semantic_review_passed") return "审读通过";
  if (artifact.identity === "deterministic_preflight_passed") return "机器检查通过";
  if (artifact.identity === "validation_failed" || artifact.identity === "rejected") return "等待修订";
  return "候选内容";
}

function friendlyStem(stem: string): string {
  const normalized = stem.replace(/[_-]+/g, " ").trim();
  const known: Array<[RegExp, string]> = [
    [/protagonist foundation/i, "主角基础设定"],
    [/world foundation/i, "世界基础设定"],
    [/story architecture/i, "故事架构"],
    [/word budget/i, "长篇字数规划"],
    [/scene review/i, "场景审查意见"],
    [/asset review/i, "资产审查意见"],
    [/style prompt/i, "文风约束方案"],
  ];
  return known.find(([pattern]) => pattern.test(normalized))?.[1]
    || normalized.replace(/\b(scene|chapter)\s*0*(\d+)\b/gi, (_match, unit, value) => `${unit.toLowerCase() === "scene" ? "场景" : "章节"}${value}`)
    || "创作资料";
}
