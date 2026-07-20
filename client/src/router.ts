import { createRouter, createWebHashHistory } from "vue-router";
import ProjectsView from "@/features/projects/ProjectsView.vue";
import OverviewView from "@/features/workflow/OverviewView.vue";
import LibraryView from "@/features/library/LibraryView.vue";
import DeliveryView from "@/features/delivery/DeliveryView.vue";
import SettingsView from "@/features/settings/SettingsView.vue";
import ReaderView from "@/features/reader/ReaderView.vue";

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/projects" },
    { path: "/projects", name: "projects", component: ProjectsView, meta: { label: "作品" } },
    { path: "/overview", name: "overview", component: OverviewView, meta: { label: "创作总控" } },
    { path: "/reader", name: "reader", component: ReaderView, meta: { label: "阅读" } },
    { path: "/library", name: "library", component: LibraryView, meta: { label: "作品档案" } },
    { path: "/delivery", name: "delivery", component: DeliveryView, meta: { label: "交付" } },
    { path: "/settings", name: "settings", component: SettingsView, meta: { label: "设置" } },
  ],
});
