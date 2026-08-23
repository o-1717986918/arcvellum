import type { SpatialNarrativeNode, SpatialNarrativeProjection } from "@/types/spatial";

export type CreativeProgressionState = "complete" | "active" | "available" | "blocked" | "latent";

export interface CreativeProgressionStage {
  id: string;
  kicker: string;
  title: string;
  description: string;
  nodeIds: string[];
  anchorNodeId: string;
  state: CreativeProgressionState;
  completion: number;
  activeNodeIds: string[];
  availableActions: number;
}

export interface CreativeProgressionLink {
  source: string;
  target: string;
  state: CreativeProgressionState;
}

export interface CreativeProgressionModel {
  stages: CreativeProgressionStage[];
  links: CreativeProgressionLink[];
}

interface StageDefinition {
  id: string;
  kicker: string;
  title: string;
  description: string;
  kinds: string[];
}

const STAGE_DEFINITIONS: StageDefinition[] = [
  {
    id: "architecture",
    kicker: "01 / ORIGIN",
    title: "架构",
    description: "让作品先拥有方向、篇幅与文风的骨架。",
    kinds: ["project", "story-architecture", "word-budget", "style"],
  },
  {
    id: "foundation",
    kicker: "02 / FOUNDATION",
    title: "资产",
    description: "人物、世界、地点与关系成为可调用的创作材料。",
    kinds: ["world", "location", "organization", "character", "relationship"],
  },
  {
    id: "dramaturgy",
    kicker: "03 / DRAMATURGY",
    title: "推演",
    description: "场景、分支、承诺与读者问题开始互相牵引。",
    kinds: ["volume", "chapter", "scene", "event", "branch", "reader-question", "promise", "payoff"],
  },
  {
    id: "manuscript",
    kicker: "04 / MANUSCRIPT",
    title: "正文",
    description: "候选文本经过文风、连续性与语义审查，逐步沉淀。",
    kinds: ["draft", "formal-prose", "review", "revision", "canon"],
  },
  {
    id: "release",
    kicker: "05 / RELEASE",
    title: "交付",
    description: "创作决定与正式作品汇合，形成可阅读、可导出的成果。",
    kinds: ["human-decision", "delivery"],
  },
];

function nodeKind(node: SpatialNarrativeNode): string {
  return String(node.creative_kind || node.type || "");
}

function nodeState(node: SpatialNarrativeNode): CreativeProgressionState {
  const lifecycle = String(node.lifecycle || "");
  const completion = String(node.completion_state || "");
  const status = String(node.status || "");
  if (["blocked", "failed"].includes(lifecycle) || ["blocked", "failed"].includes(status) || completion === "blocked") return "blocked";
  if (["active", "awaiting", "reviewing", "revision"].includes(lifecycle) || ["current", "queued", "running", "waiting"].includes(status) || completion === "active") return "active";
  if (["formal", "delivered"].includes(lifecycle) || ["formal", "delivered"].includes(status) || completion === "completed") return "complete";
  if (["available", "planned"].includes(lifecycle) || ["available", "planned"].includes(status) || completion === "planned") return "available";
  return "latent";
}

function stageState(nodes: SpatialNarrativeNode[]): CreativeProgressionState {
  const states = nodes.map(nodeState);
  if (states.includes("blocked")) return "blocked";
  if (states.includes("active")) return "active";
  if (states.length && states.every((state) => state === "complete")) return "complete";
  if (states.includes("available") || states.includes("complete")) return "available";
  return "latent";
}

function anchorFor(nodes: SpatialNarrativeNode[]): SpatialNarrativeNode | undefined {
  return nodes.find((node) => nodeState(node) === "active")
    || nodes.find((node) => nodeState(node) === "available")
    || nodes.find((node) => nodeState(node) === "complete")
    || nodes[0];
}

/**
 * Build a presentation-only creative progression. It deliberately never
 * invents hard prerequisites: the CLI/state machine remains the authority.
 */
export function buildCreativeProgression(projection: SpatialNarrativeProjection): CreativeProgressionModel {
  const stages = STAGE_DEFINITIONS
    .map((definition) => {
      const nodes = projection.nodes
        .filter((node) => definition.kinds.includes(nodeKind(node)))
        .sort((left, right) => left.order - right.order || left.node_id.localeCompare(right.node_id));
      const activeNodeIds = nodes.filter((node) => nodeState(node) === "active").map((node) => node.node_id);
      const completeCount = nodes.filter((node) => nodeState(node) === "complete").length;
      const anchor = anchorFor(nodes);
      return {
        id: definition.id,
        kicker: definition.kicker,
        title: definition.title,
        description: definition.description,
        nodeIds: nodes.map((node) => node.node_id),
        anchorNodeId: anchor?.node_id || "",
        state: nodes.length ? stageState(nodes) : "latent",
        completion: nodes.length ? Math.round((completeCount / nodes.length) * 100) : 0,
        activeNodeIds,
        availableActions: nodes.reduce((total, node) => total + (node.available_actions?.filter((action) => action.enabled).length || 0), 0),
      } satisfies CreativeProgressionStage;
    })
    .filter((stage): stage is CreativeProgressionStage => Boolean(stage));

  return {
    stages,
    links: stages.slice(1).map((stage, index) => ({
      source: stages[index].id,
      target: stage.id,
      state: stage.state,
    })),
  };
}

export function nodeProgressionState(node: SpatialNarrativeNode): CreativeProgressionState {
  return nodeState(node);
}
