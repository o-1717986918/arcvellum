import { createRouter, createWebHashHistory, type RouteLocation } from "vue-router";

const studioWorkspace = () => import("@/workspaces/StudioWorkspaceShell.vue");

function agentWorkspace(workspace: string, to: RouteLocation) {
  return { name: "project-agent", query: { ...to.query, workspace } };
}

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: { name: "project-agent" } },
    { path: "/projects", name: "projects", redirect: { name: "project-agent", query: { new: "1" } }, meta: { label: "作品" } },
    { path: "/agent", name: "project-agent", component: studioWorkspace, meta: { label: "项目 Agent" } },
    { path: "/overview", name: "overview", component: studioWorkspace, meta: { label: "创作总控" } },
    { path: "/character-chat", name: "character-chat", redirect: (to) => ({ name: "project-agent",
      query: { ...to.query, workspace: "character-chat", characterReturn: "archive" } }), meta: { label: "与角色交谈" } },
    { path: "/reader", name: "reader", redirect: (to) => agentWorkspace("reader", to), meta: { label: "阅读" } },
    { path: "/library", name: "library", redirect: (to) => agentWorkspace("archive", to), meta: { label: "作品档案" } },
    { path: "/archive", name: "archive", redirect: (to) => agentWorkspace("archive", to), meta: { label: "档案管理" } },
    { path: "/archaeology", name: "archaeology", redirect: (to) => agentWorkspace("archaeology", to), meta: { label: "作品考古" } },
    { path: "/style", name: "style", redirect: (to) => agentWorkspace("style", to), meta: { label: "文风工坊" } },
    { path: "/quality", name: "quality", redirect: (to) => agentWorkspace("quality", to), meta: { label: "创作规则" } },
    { path: "/strategy", name: "strategy", redirect: (to) => agentWorkspace("quality", to), meta: { label: "质量与节奏" } },
    { path: "/observatory", name: "observatory", redirect: (to) => agentWorkspace("live", to), meta: { label: "Agent 工作" } },
    { path: "/delivery", name: "delivery", redirect: (to) => agentWorkspace("delivery", to), meta: { label: "交付" } },
    { path: "/settings", name: "settings", redirect: (to) => agentWorkspace("settings", to), meta: { label: "设置" } },
    { path: "/help", name: "help", redirect: (to) => agentWorkspace("help", to), meta: { label: "使用帮助" } },
    { path: "/details", name: "details", redirect: (to) => agentWorkspace("details", to), meta: { label: "详情" } },
    { path: "/legal", name: "legal", redirect: (to) => agentWorkspace("legal", to), meta: { label: "协议与隐私" } },
  ],
});
