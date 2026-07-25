import { api, query } from "@/services/api";
import type {
  StyleAuthorCreatePayload,
  StyleAtelierWorkbench,
  StyleSourceCreatePayload,
  StyleTransactionReceipt,
  StyleVersionDetail,
  StyleWorkCreatePayload,
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

export function createStyleAuthor(
  payload: StyleAuthorCreatePayload,
): Promise<StyleTransactionReceipt> {
  return postStyleTransaction("/style-lab/authors", payload);
}

export function createStyleWork(
  payload: StyleWorkCreatePayload,
): Promise<StyleTransactionReceipt> {
  return postStyleTransaction("/style-lab/works", payload);
}

export function importStyleSource(
  payload: StyleSourceCreatePayload,
): Promise<StyleTransactionReceipt> {
  return postStyleTransaction("/style-lab/sources", payload);
}

function postStyleTransaction(
  path: string,
  payload: StyleAuthorCreatePayload | StyleWorkCreatePayload | StyleSourceCreatePayload,
): Promise<StyleTransactionReceipt> {
  return api(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
