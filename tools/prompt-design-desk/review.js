/* Render all prompt text as text, including user supplied sources. */
(function () {
  "use strict";
  const model = window.DeskState;
  const slots = model.slots;
  const byId = Object.fromEntries(slots.map((slot) => [slot.id, slot]));
  const dom = Object.fromEntries([
    "promptText", "designNote", "sourceSelect", "sourceText", "sourceMeta", "slotNav",
    "progressCount", "readyCount", "meterFill", "searchSlots", "reviewState",
    "draftOrigin", "saveState", "legacyChecks", "toast", "projectTitle", "generalNotes"
  ].map((id) => [id, document.getElementById(id)]));
  let state = model.load();
  let selected = slots[0].id;
  let toastTimer;
  const record = () => state.slots[selected];

  function toast(message) {
    clearTimeout(toastTimer);
    dom.toast.textContent = message;
    dom.toast.classList.add("show");
    toastTimer = setTimeout(() => dom.toast.classList.remove("show"), 4500);
  }

  function persist() {
    try {
      localStorage.setItem(model.key, JSON.stringify(state));
      dom.saveState.textContent = "已保存到当前浏览器";
    } catch (_) {
      dom.saveState.textContent = "浏览器存储不可用或已满，请导出 JSON 保存";
    }
  }

  function renderProgress() {
    const count = slots.filter((slot) => model.approved(state.slots[slot.id])).length;
    dom.progressCount.textContent = count + " / " + slots.length;
    const v2 = slots.filter((slot) => slot.scope === "v2" && model.approved(state.slots[slot.id])).length;
    dom.readyCount.textContent = "v2 " + v2 + "/20 通过";
    dom.meterFill.style.width = (count / slots.length * 100) + "%";
  }

  function renderNav() {
    dom.slotNav.replaceChildren();
    const query = dom.searchSlots.value.toLowerCase().trim();
    for (const group of new Set(slots.map((slot) => slot.group))) {
      const visible = slots.filter((slot) => slot.group === group &&
        (slot.title + slot.id + group).toLowerCase().includes(query));
      if (!visible.length) continue;
      const heading = document.createElement("h3");
      heading.className = "group-title";
      heading.textContent = group;
      dom.slotNav.append(heading);
      visible.forEach((slot) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "slot-button" + (slot.id === selected ? " active" : "");
        button.setAttribute("aria-current", slot.id === selected ? "true" : "false");
        const index = document.createElement("span");
        index.className = "slot-index";
        index.textContent = String(slots.indexOf(slot) + 1).padStart(2, "0");
        const name = document.createElement("span");
        name.className = "slot-name";
        name.textContent = slot.title;
        const dot = document.createElement("span");
        const pass = model.approved(state.slots[slot.id]);
        dot.className = "slot-dot " + (pass ? "ready" : state.slots[slot.id].content.trim() ? "draft" : "");
        button.title = slot.id + (pass ? " · 已通过" : " · 待评审");
        button.append(index, name, dot);
        button.addEventListener("click", () => select(slot.id));
        dom.slotNav.append(button);
      });
    }
    if (!dom.slotNav.children.length) dom.slotNav.textContent = "没有匹配的提示词位，请换个关键词。";
  }

  function renderReview() {
    const current = record();
    const pass = model.approved(current);
    dom.reviewState.textContent = pass ? "已通过 · 修改正文后需重新评审" :
      current.status === "ready" ? "旧稿曾标记可整理 · 请点击通过确认本次评审" : "待评审";
    dom.reviewState.className = "review-state" + (pass ? " approved" : "");
    const originLabel = { builtin_draft: "内置初稿", imported: "导入稿", edited: "已修改",
      source_adopted: "采用来源稿", legacy_adopted: "采用旧稿" }[current.origin.type] || "导入来源";
    dom.draftOrigin.textContent = "稿件来源：" + originLabel + " · " +
      (current.origin.sources.map((source) => source.id + " v" + source.package_version).join(" + ") || "用户填写／导入");
    document.getElementById("charCount").textContent = current.content.length + " 字符";
    document.getElementById("revokeButton").disabled = !pass;
    document.getElementById("approveButton").disabled = !model.usable(current.content) || pass;
    document.getElementById("undoButton").disabled = !current.undo;
    renderProgress();
    renderNav();
  }

  function renderSource() {
    const id = dom.sourceSelect.value;
    const source = model.sources[id];
    dom.sourceText.value = source.text;
    dom.sourceMeta.textContent = "内置快照 · v" + source.package_version + " · " +
      source.text.length + " 字符\nSHA-256 " + source.sha256;
    const legacy = id !== selected || byId[selected].scope === "legacy_review";
    document.getElementById("sourceHeading").textContent = legacy ? "旧提示词全文" : "当前 v2 初稿全文";
    document.getElementById("showLegacyButton").setAttribute("aria-pressed", String(legacy));
    document.getElementById("showCurrentButton").setAttribute("aria-pressed", String(!legacy));
    document.getElementById("adoptSourceButton").disabled = !legacy || !model.usable(source.text);
  }

  function showSource(id) {
    dom.sourceSelect.value = id;
    renderSource();
  }

  function renderSources(slot) {
    dom.sourceSelect.replaceChildren();
    [slot.id, ...slot.refs].forEach((id) => {
      const option = document.createElement("option");
      option.value = id;
      option.textContent = (id === slot.id ? (slot.scope === "v2" ? "当前 v2 初稿 · " : "现有旧稿 · ") : "旧稿 · ") + id;
      dom.sourceSelect.append(option);
    });
    dom.sourceSelect.value = slot.refs[0] || slot.id;
    document.getElementById("showCurrentButton").hidden = slot.scope !== "v2";
    dom.legacyChecks.replaceChildren();
    slot.refs.forEach((id) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = id;
      label.append(input, document.createTextNode(id));
      dom.legacyChecks.append(label);
    });
    document.getElementById("legacyCombination").hidden = !slot.refs.length;
    const refs = document.getElementById("legacyList");
    refs.replaceChildren();
    slot.refs.forEach((id) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = id;
      button.title = model.sources[id].purpose;
      button.addEventListener("click", () => {
        showSource(id);
        dom.sourceText.focus();
      });
      refs.append(button);
    });
    if (!slot.refs.length) refs.textContent = "此位直接评审现有顶层提示词。";
    renderSource();
  }

  function select(id) {
    if (!byId[id]) return;
    selected = id;
    const slot = byId[id];
    const index = slots.indexOf(slot);
    document.getElementById("slotNumber").textContent = String(index + 1).padStart(2, "0") + " / " + slots.length;
    document.getElementById("slotGroup").textContent = slot.group;
    const kind = document.getElementById("slotKind");
    kind.textContent = slot.fixed ? "固定合同 · 可评审文案" : "文学设计位";
    kind.className = "pill" + (slot.fixed ? " fixed" : "");
    document.getElementById("slotTitle").textContent = slot.title;
    document.getElementById("slotPurpose").textContent = slot.purpose;
    document.getElementById("slotId").textContent = slot.id;
    const rule = document.getElementById("ruleNote");
    rule.textContent = slot.note + (slot.fixed ? " 装载时保持 v2 权限和结构合同。" : "");
    rule.className = "rule-note" + (slot.fixed ? " fixed" : "");
    dom.promptText.value = record().content;
    dom.designNote.value = record().note;
    document.getElementById("prevButton").disabled = index === 0;
    document.getElementById("nextButton").disabled = index === slots.length - 1;
    renderSources(slot);
    renderReview();
  }

  function adopt(ids, pass) {
    try {
      model.adopt(record(), ids, pass);
      persist();
      select(selected);
      toast(pass ? "已采用旧稿并通过，可撤销上次采用。" : "已采用来源正文，可继续修改。");
    } catch (error) { toast(error.message); }
  }

  function replaceState(next) {
    state = next;
    dom.projectTitle.value = state.projectTitle;
    dom.generalNotes.value = state.generalNotes;
    persist();
    select(selected);
  }

  dom.promptText.addEventListener("input", () => {
    model.edit(record(), dom.promptText.value);
    persist();
    renderReview();
  });
  dom.designNote.addEventListener("input", () => { record().note = dom.designNote.value; persist(); });
  dom.sourceSelect.addEventListener("change", renderSource);
  document.getElementById("showLegacyButton").addEventListener("click", () =>
    showSource(byId[selected].refs[0] || selected));
  document.getElementById("showCurrentButton").addEventListener("click", () => showSource(selected));
  dom.searchSlots.addEventListener("input", renderNav);
  document.getElementById("copySourceButton").addEventListener("click", () => adopt([dom.sourceSelect.value], false));
  document.getElementById("adoptSourceButton").addEventListener("click", () => adopt([dom.sourceSelect.value], true));
  document.getElementById("adoptManyButton").addEventListener("click", () =>
    adopt([...dom.legacyChecks.querySelectorAll("input:checked")].map((input) => input.value), true));
  document.getElementById("approveButton").addEventListener("click", () => {
    try { model.approve(record()); persist(); renderReview(); toast("当前填写稿已通过。"); }
    catch (error) { toast(error.message); }
  });
  document.getElementById("revokeButton").addEventListener("click", () => {
    record().review_decision = null; record().status = "draft"; persist(); renderReview();
  });
  document.getElementById("undoButton").addEventListener("click", () => {
    if (!record().undo) return;
    state.slots[selected] = record().undo; persist(); select(selected); toast("已恢复采用前的稿件。");
  });
  ["prev", "next"].forEach((direction) => {
    document.getElementById(direction + "Button").addEventListener("click", () =>
      select(slots[slots.findIndex((slot) => slot.id === selected) + (direction === "prev" ? -1 : 1)]?.id));
  });
  dom.projectTitle.addEventListener("input", () => { state.projectTitle = dom.projectTitle.value; persist(); });
  dom.generalNotes.addEventListener("input", () => { state.generalNotes = dom.generalNotes.value; persist(); });
  dom.projectTitle.value = state.projectTitle;
  dom.generalNotes.value = state.generalNotes;
  window.PromptDesk = {
    select, toast, replaceState, getState: () => state, getSelected: () => selected,
    exportPayload: () => model.exportPayload(state),
    importPayload: (payload) => model.importPayload(payload, state)
  };
  select(selected);
})();
