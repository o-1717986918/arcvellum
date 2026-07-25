import { api, query } from "@/services/api";
import type {
  StyleAtelierWorkbench,
  StyleVersionDetail,
} from "../types";

export function fetchStyleWorkbench(
  projectRoot: string,
): Promise<StyleAtelierWorkbench> {
  return api(`/style-lab/workbench?${query({ project_root: projectRoot })}`);
}

export function fetchStyleVersionDetail(
  projectRoot: string,
  styleId: string,
  versionId: string,
): Promise<StyleVersionDetail> {
  const suffix = query({ project_root: projectRoot });
  return api(
    `/style-lab/versions/${encodeURIComponent(styleId)}/${encodeURIComponent(versionId)}?${suffix}`,
  );
}
