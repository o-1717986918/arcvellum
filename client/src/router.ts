import { createRouter, createWebHashHistory } from "vue-router";

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/projects" },
    { path: "/projects", name: "projects", component: () => import("@/features/projects/ProjectsView.vue"), meta: { label: "作品" } },
    { path: "/overview", name: "overview", component: () => import("@/features/workflow/OverviewView.vue"), meta: { label: "创作总控" } },
    { path: "/reader", name: "reader", component: () => import("@/features/spatial-os/SpatialWorkspaceRoute.vue"), props: { workspace: "reader" }, meta: { label: "阅读" } },
    { path: "/library", name: "library", component: () => import("@/features/spatial-os/SpatialWorkspaceRoute.vue"), props: { workspace: "archive" }, meta: { label: "作品档案" } },
    { path: "/archive", name: "archive", component: () => import("@/features/spatial-os/SpatialWorkspaceRoute.vue"), props: { workspace: "archive" }, meta: { label: "档案管理" } },
    { path: "/archaeology", name: "archaeology", component: () => import("@/features/spatial-os/SpatialWorkspaceRoute.vue"), props: { workspace: "archaeology" }, meta: { label: "作品考古" } },
    { path: "/style", name: "style", component: () => import("@/features/spatial-os/SpatialWorkspaceRoute.vue"), props: { workspace: "style" }, meta: { label: "文风工坊" } },
    { path: "/quality", name: "quality", component: () => import("@/features/spatial-os/SpatialWorkspaceRoute.vue"), props: { workspace: "quality" }, meta: { label: "创作规则" } },
    { path: "/strategy", name: "strategy", component: () => import("@/features/spatial-os/SpatialWorkspaceRoute.vue"), props: { workspace: "strategy" }, meta: { label: "创作策略" } },
    { path: "/observatory", name: "observatory", component: () => import("@/features/spatial-os/SpatialWorkspaceRoute.vue"), props: { workspace: "observatory" }, meta: { label: "Agent 观测台" } },
    { path: "/delivery", name: "delivery", component: () => import("@/features/spatial-os/SpatialWorkspaceRoute.vue"), props: { workspace: "delivery" }, meta: { label: "交付" } },
    { path: "/settings", name: "settings", component: () => import("@/features/settings/SettingsView.vue"), meta: { label: "设置" } },
    { path: "/help", name: "help", component: () => import("@/features/help/HelpView.vue"), meta: { label: "使用帮助" } },
    { path: "/details", name: "details", component: () => import("@/features/details/DetailsView.vue"), meta: { label: "详情" } },
    { path: "/legal", name: "legal", component: () => import("@/features/details/LegalView.vue"), meta: { label: "协议与隐私" } },
  ],
});
