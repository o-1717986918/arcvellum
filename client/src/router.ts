import { createRouter, createWebHashHistory } from "vue-router";

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/projects" },
    { path: "/projects", name: "projects", component: () => import("@/features/projects/ProjectsView.vue"), meta: { label: "作品" } },
    { path: "/overview", name: "overview", component: () => import("@/features/workflow/OverviewView.vue"), meta: { label: "创作总控" } },
    { path: "/reader", name: "reader", component: () => import("@/features/reader/ReaderView.vue"), meta: { label: "阅读" } },
    { path: "/library", name: "library", component: () => import("@/features/library/LibraryView.vue"), meta: { label: "作品档案" } },
    { path: "/quality", name: "quality", component: () => import("@/features/quality/QualityView.vue"), meta: { label: "创作规则" } },
    { path: "/delivery", name: "delivery", component: () => import("@/features/delivery/DeliveryView.vue"), meta: { label: "交付" } },
    { path: "/settings", name: "settings", component: () => import("@/features/settings/SettingsView.vue"), meta: { label: "设置" } },
    { path: "/help", name: "help", component: () => import("@/features/help/HelpView.vue"), meta: { label: "使用帮助" } },
    { path: "/details", name: "details", component: () => import("@/features/details/DetailsView.vue"), meta: { label: "详情" } },
    { path: "/legal", name: "legal", component: () => import("@/features/details/LegalView.vue"), meta: { label: "协议与隐私" } },
  ],
});
