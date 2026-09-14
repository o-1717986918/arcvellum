import { createRouter, createWebHashHistory } from "vue-router";

function agentWorkspace(workspace: string) {
  return { name: "project-agent", query: { workspace } };
}

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/projects" },
    { path: "/projects", name: "projects", component: () => import("@/features/projects/ProjectsView.vue"), meta: { label: "作品" } },
    { path: "/agent", name: "project-agent", component: () => import("@/features/project-agent/AgentWorkspaceView.vue"), meta: { label: "项目 Agent" } },
    { path: "/overview", name: "overview", component: () => import("@/features/workflow/OverviewView.vue"), meta: { label: "创作总控" } },
    { path: "/reader", name: "reader", redirect: () => agentWorkspace("reader"), meta: { label: "阅读" } },
    { path: "/library", name: "library", redirect: () => agentWorkspace("archive"), meta: { label: "作品档案" } },
    { path: "/archive", name: "archive", redirect: () => agentWorkspace("archive"), meta: { label: "档案管理" } },
    { path: "/archaeology", name: "archaeology", redirect: () => agentWorkspace("archaeology"), meta: { label: "作品考古" } },
    { path: "/style", name: "style", redirect: () => agentWorkspace("style"), meta: { label: "文风工坊" } },
    { path: "/quality", name: "quality", redirect: () => agentWorkspace("quality"), meta: { label: "创作规则" } },
    { path: "/strategy", name: "strategy", redirect: () => agentWorkspace("strategy"), meta: { label: "创作策略" } },
    { path: "/observatory", name: "observatory", redirect: () => agentWorkspace("live"), meta: { label: "创作现场" } },
    { path: "/delivery", name: "delivery", redirect: () => agentWorkspace("delivery"), meta: { label: "交付" } },
    { path: "/settings", name: "settings", component: () => import("@/features/settings/SettingsView.vue"), meta: { label: "设置" } },
    { path: "/help", name: "help", component: () => import("@/features/help/HelpView.vue"), meta: { label: "使用帮助" } },
    { path: "/details", name: "details", component: () => import("@/features/details/DetailsView.vue"), meta: { label: "详情" } },
    { path: "/legal", name: "legal", component: () => import("@/features/details/LegalView.vue"), meta: { label: "协议与隐私" } },
  ],
});
