import { defineAsyncComponent, type Component } from "vue";
import { creativeWorkspaceRegistry } from "@/workspaces/creativeWorkspaceRegistry";

export type ProjectAgentWorkspaceId =
  | "projects"
  | "reader"
  | "live"
  | "rehearsal"
  | "archive"
  | "style"
  | "quality"
  | "archaeology"
  | "delivery"
  | "settings"
  | "help"
  | "details"
  | "legal";

export type ProjectAgentWorkspaceScope = "project" | "application";

export interface ProjectAgentWorkspaceDescriptor {
  id: ProjectAgentWorkspaceId;
  title: string;
  shortLabel: string;
  description: string;
  component: Component;
  scope: ProjectAgentWorkspaceScope;
  requiresProject: boolean;
}

function asyncWorkspace(loader: () => Promise<{ default: Component }>): Component {
  return defineAsyncComponent({
    loader,
    timeout: 15_000,
    onError(error, retry, fail, attempts) {
      const message = error instanceof Error ? error.message : String(error);
      if (/fetch|load|module|network|import/i.test(message) && attempts < 2) {
        window.setTimeout(retry, 350);
        return;
      }
      fail();
    },
  });
}

function migrated(id: "archive" | "style" | "quality" | "archaeology"): Component {
  const descriptor = creativeWorkspaceRegistry.get(id);
  if (!descriptor) throw new Error(`missing creative workspace: ${id}`);
  return descriptor.component;
}

const workspaces: ProjectAgentWorkspaceDescriptor[] = [
  {
    id: "projects",
    title: "作品库",
    shortLabel: "作品",
    description: "建立、打开和继续作品，也可以进入随安装提供的文学工程示范。",
    component: asyncWorkspace(() => import("@/features/projects/ProjectsView.vue")),
    scope: "application",
    requiresProject: false,
  },
  {
    id: "reader",
    title: "正文长卷",
    shortLabel: "正文",
    description: "连续阅读已经晋升的正式正文，创作推进时会自动接入新内容。",
    component: asyncWorkspace(() => import("@/features/reader/ReaderView.vue")),
    scope: "project",
    requiresProject: true,
  },
  {
    id: "live",
    title: "创作现场",
    shortLabel: "现场",
    description: "观察主创会话、候选正文、审查结论与修订过程。",
    component: asyncWorkspace(() => import("@/features/creative-live/CreativeLiveView.vue")),
    scope: "project",
    requiresProject: true,
  },
  {
    id: "rehearsal",
    title: "推演观察",
    shortLabel: "推演",
    description: "按角色轮次观看正在进行与已经完成的场景推演。",
    component: asyncWorkspace(() => import("@/features/creative-live/SceneRehearsalView.vue")),
    scope: "project",
    requiresProject: true,
  },
  {
    id: "archive",
    title: "作品档案",
    shortLabel: "档案",
    description: "查阅和校勘人物、地点、组织、世界规则与作品资产。",
    component: migrated("archive"),
    scope: "project",
    requiresProject: true,
  },
  {
    id: "style",
    title: "文风工作台",
    shortLabel: "文风",
    description: "开发中，不完善。可查看语料、文风版本与当前挂载。",
    component: migrated("style"),
    scope: "project",
    requiresProject: true,
  },
  {
    id: "quality",
    title: "质量与节奏",
    shortLabel: "规则",
    description: "调整语言规则、审查阈值和全书叙事节奏曲线。",
    component: migrated("quality"),
    scope: "project",
    requiresProject: true,
  },
  {
    id: "archaeology",
    title: "作品考古",
    shortLabel: "考古",
    description: "开发中，不完善。可尝试从已有文本重建人物、世界与结构候选。",
    component: migrated("archaeology"),
    scope: "project",
    requiresProject: true,
  },
  {
    id: "delivery",
    title: "交付中心",
    shortLabel: "交付",
    description: "检查交付准备度并取得已经通过门禁的正式作品文件。",
    component: asyncWorkspace(() => import("@/features/delivery/DeliveryView.vue")),
    scope: "project",
    requiresProject: true,
  },
  {
    id: "settings",
    title: "设置",
    shortLabel: "设置",
    description: "连接模型、选择工作模型并管理场域、更新和本地作品库。",
    component: asyncWorkspace(() => import("@/features/settings/SettingsView.vue")),
    scope: "application",
    requiresProject: false,
  },
  {
    id: "help",
    title: "使用帮助",
    shortLabel: "帮助",
    description: "按当前状态理解 ArcVellum 的主要操作和故障恢复方法。",
    component: asyncWorkspace(() => import("@/features/help/HelpView.vue")),
    scope: "application",
    requiresProject: false,
  },
  {
    id: "details",
    title: "作品与应用",
    shortLabel: "详情",
    description: "查看当前作品规模、应用版本、数据位置和运行边界。",
    component: asyncWorkspace(() => import("@/features/details/DetailsView.vue")),
    scope: "application",
    requiresProject: false,
  },
  {
    id: "legal",
    title: "协议与隐私",
    shortLabel: "协议",
    description: "查阅本地数据、模型服务、第三方许可和公开发布约定。",
    component: asyncWorkspace(() => import("@/features/details/LegalView.vue")),
    scope: "application",
    requiresProject: false,
  },
];

const byId = new Map(workspaces.map((workspace) => [workspace.id, workspace]));

export const projectAgentWorkspaces = {
  all(): readonly ProjectAgentWorkspaceDescriptor[] {
    return workspaces;
  },
  forScope(scope: ProjectAgentWorkspaceScope): readonly ProjectAgentWorkspaceDescriptor[] {
    return workspaces.filter((workspace) => workspace.scope === scope);
  },
  get(id: string | null | undefined): ProjectAgentWorkspaceDescriptor | undefined {
    return id ? byId.get(id as ProjectAgentWorkspaceId) : undefined;
  },
  has(id: string | null | undefined): id is ProjectAgentWorkspaceId {
    return Boolean(id && byId.has(id as ProjectAgentWorkspaceId));
  },
};
