(function () {
  "use strict";
  const desk = window.PromptDesk;
  const button = (id, action) => document.getElementById(id).addEventListener("click", action);
  const exportText = () => JSON.stringify(desk.exportPayload(), null, 2) + "\n";

  function download() {
    const payload = desk.exportPayload();
    const name = (payload.project_title.trim().replace(/[\\/:*?"<>|]/g, "-").replace(/\s+/g, "-").slice(0, 38) ||
      "scene-prompt-review") + "-" + new Date().toISOString().slice(0, 10) + ".json";
    const url = URL.createObjectURL(new Blob([exportText()], { type: "application/json;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    desk.toast("已导出 " + name + "，含 " + payload.approved_count + " 项通过决定。");
  }

  async function copy() {
    const text = exportText();
    try { await navigator.clipboard.writeText(text); desk.toast("26 位结构化文本已复制。"); }
    catch (_) {
      const manual = document.getElementById("manualCopy");
      manual.value = text;
      document.getElementById("manualDialog").showModal();
      manual.focus();
      manual.select();
    }
  }

  button("downloadButton", download);
  button("downloadBottom", download);
  button("copyButton", copy);
  button("closeDialog", () => document.getElementById("manualDialog").close());
  button("copyIdButton", async () => {
    try { await navigator.clipboard.writeText(desk.getSelected()); desk.toast("提示词 ID 已复制。"); }
    catch (_) { desk.toast("剪贴板不可用，可选中提示词 ID 手动复制。"); }
  });
  button("importButton", () => document.getElementById("importFile").click());
  let previousImport;
  document.getElementById("importFile").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const next = desk.importPayload(JSON.parse(await file.text()));
      previousImport = window.DeskState.clone(desk.getState());
      desk.replaceState(next);
      document.getElementById("undoImportButton").hidden = false;
      desk.toast("已导入 " + file.name + "，未包含的提示词位保留；可撤销导入。");
    } catch (error) { desk.toast(error.message); }
    finally { event.target.value = ""; }
  });
  button("undoImportButton", () => {
    if (!previousImport) return;
    desk.replaceState(previousImport);
    previousImport = null;
    document.getElementById("undoImportButton").hidden = true;
    desk.toast("已恢复导入前的稿件。");
  });
})();
