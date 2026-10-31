/** Save an already authenticated response without exposing tokens in links. */
export async function saveResponseFile(response: Response, fallbackName: string): Promise<string> {
  if (!response.ok) throw new Error(`文件下载没有完成（${response.status}），请重试。`);
  const disposition = response.headers.get("content-disposition") || "";
  const name = disposition.match(/filename="?([^";]+)"?/)?.[1] || fallbackName;
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name.replace(/[/\\]/g, "_");
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  // The download handler must have time to consume the object URL.
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
  return name;
}
