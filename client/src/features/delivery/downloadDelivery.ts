import { deliveryClient } from "./services/deliveryClient";
import { saveResponseFile } from "@/services/saveResponseFile";

/** Fetch through the authenticated feature client before creating a local download. */
export async function downloadDelivery(root: string, path: string, name?: string): Promise<void> {
  const response = await deliveryClient.download(root, path);
  await saveResponseFile(response, name || path.replace(/\\/g, "/").split("/").at(-1) || "ArcVellum-manuscript");
}
