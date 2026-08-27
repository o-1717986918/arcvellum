import { defineAsyncComponent, type Component } from "vue";
import type { CreativeNodeKind } from "@/types/spatial";
import type { SpatialWindowKind, SpatialWindowSize } from "@/types/spatialWindows";

export type CreativeWorkspaceKind = Extract<
  SpatialWindowKind,
  "archive" | "style" | "quality" | "strategy" | "observatory" | "archaeology"
>;

export interface WorkspaceDescriptor {
  workspaceId: CreativeWorkspaceKind;
  title: string;
  shortLabel: string;
  description: string;
  component: Component;
  defaultSize: SpatialWindowSize;
  minimumSize: SpatialWindowSize;
  allowMultiple: boolean;
  supportsFullscreen: boolean;
  supportedNodeKinds: CreativeNodeKind[];
}

const descriptors: WorkspaceDescriptor[] = [
  {
    workspaceId: "archive",
    title: "作品档案室",
    shortLabel: "档案",
    description: "维护人物、世界、地点与组织等正式作品资产。",
    component: defineAsyncComponent(() => import("@/features/archive/ArchiveView.vue")),
    defaultSize: { width: 720, height: 590 },
    minimumSize: { width: 520, height: 420 },
    allowMultiple: false,
    supportsFullscreen: true,
    supportedNodeKinds: ["character", "world", "location", "organization", "scene", "canon"],
  },
  {
    workspaceId: "style",
    title: "文风工坊",
    shortLabel: "文风",
    description: "学习语料、评测风格提示词并管理正式挂载。",
    component: defineAsyncComponent(() => import("@/features/style-atelier/StyleAtelierView.vue")),
    defaultSize: { width: 680, height: 570 },
    minimumSize: { width: 480, height: 400 },
    allowMultiple: false,
    supportsFullscreen: true,
    supportedNodeKinds: ["style", "draft", "formal-prose", "review"],
  },
  {
    workspaceId: "quality",
    title: "语言与节奏",
    shortLabel: "质量",
    description: "管理标点、表达习惯、节奏曲线、审查阈值与修订方向。",
    component: defineAsyncComponent(() => import("@/features/quality/QualityView.vue")),
    defaultSize: { width: 660, height: 560 },
    minimumSize: { width: 460, height: 390 },
    allowMultiple: false,
    supportsFullscreen: true,
    supportedNodeKinds: ["review", "revision", "draft", "formal-prose", "chapter", "scene"],
  },
  {
    workspaceId: "strategy",
    title: "创作策略室",
    shortLabel: "策略",
    description: "查看全书结构、场景库存、执行计划与自适应编排。",
    component: defineAsyncComponent(() => import("@/features/strategy/CreationStrategyView.vue")),
    defaultSize: { width: 620, height: 540 },
    minimumSize: { width: 440, height: 380 },
    allowMultiple: false,
    supportsFullscreen: true,
    supportedNodeKinds: ["project", "story-architecture", "word-budget", "volume", "chapter", "event"],
  },
  {
    workspaceId: "observatory",
    title: "Agent 观测台",
    shortLabel: "观测",
    description: "观察真实会话、上下文摘要、工具事件、产物和受控重试。",
    component: defineAsyncComponent(() => import("@/features/observatory/AgentObservatoryView.vue")),
    defaultSize: { width: 690, height: 570 },
    minimumSize: { width: 500, height: 410 },
    allowMultiple: false,
    supportsFullscreen: true,
    supportedNodeKinds: ["project", "human-decision", "review", "revision", "draft"],
  },
  {
    workspaceId: "archaeology",
    title: "作品考古台",
    shortLabel: "考古",
    description: "从已有作品提取结构、人物、世界与可继续开发的正式候选。",
    component: defineAsyncComponent(() => import("@/features/archaeology/ArchaeologyView.vue")),
    defaultSize: { width: 650, height: 550 },
    minimumSize: { width: 460, height: 390 },
    allowMultiple: false,
    supportsFullscreen: true,
    supportedNodeKinds: ["project", "story-architecture", "world", "character", "style"],
  },
];

const byId = new Map(descriptors.map((descriptor) => [descriptor.workspaceId, descriptor]));

export const creativeWorkspaceRegistry = {
  all(): readonly WorkspaceDescriptor[] {
    return descriptors;
  },
  get(workspaceId: SpatialWindowKind): WorkspaceDescriptor | undefined {
    return byId.get(workspaceId as CreativeWorkspaceKind);
  },
  forNode(kind: CreativeNodeKind | undefined): readonly WorkspaceDescriptor[] {
    if (!kind) return [];
    return descriptors.filter((descriptor) => descriptor.supportedNodeKinds.includes(kind));
  },
  has(workspaceId: SpatialWindowKind): workspaceId is CreativeWorkspaceKind {
    return byId.has(workspaceId as CreativeWorkspaceKind);
  },
};
