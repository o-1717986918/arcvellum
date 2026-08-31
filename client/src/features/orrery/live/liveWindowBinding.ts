import type { CreativeLiveSnapshot } from "@/features/creative-live/types";

export function liveWindowLabel(snapshot: CreativeLiveSnapshot | null): string {
  if (!snapshot) return "创作现场待命";
  if (snapshot.status === "blocked") return "创作现场需要处理";
  if (snapshot.status === "active") return String(snapshot.active_task?.title || "作品正在形成");
  return "创作现场已连接";
}

