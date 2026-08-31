import type { SpatialGrammar } from "@/types/spatial";

const GRAMMAR_LABELS: Record<SpatialGrammar, string> = {
  spine: "脊柱",
  braid: "编织",
  strata: "层室",
  constellation: "星簇",
  loop: "回环",
  stage: "舞台",
};

export function grammarLabel(grammar: SpatialGrammar): string {
  return GRAMMAR_LABELS[grammar];
}
