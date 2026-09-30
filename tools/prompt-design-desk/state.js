/* Review decisions are local human choices, never runtime configuration. */
(function () {
  "use strict";
  const library = JSON.parse(document.getElementById("promptLibrary").textContent);
  const slots = library.slots;
  const sources = library.sources;
  const key = "arcvellum-scene-prompt-design-v1";
  const schema = "arcvellum/prompt-design-submission/v2";
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const provenance = (id) => ({
    id, package_version: sources[id].package_version,
    sha256: sources[id].sha256, scope: "builtin_snapshot"
  });
  const usable = (text) => !!text.trim() && !text.includes("[PENDING_PROMPT_DESIGN:");

  function approved(record) {
    const review = record.review_decision;
    return usable(record.content) && review?.decision === "approved" &&
      review.approved_content === record.content;
  }

  function seed() {
    const state = { version: 2, projectTitle: "", generalNotes: "", slots: {} };
    slots.forEach((slot) => {
      state.slots[slot.id] = {
        content: sources[slot.id].text, note: "", status: "draft",
        origin: { type: "builtin_draft", sources: [provenance(slot.id)] },
        review_decision: null
      };
    });
    return state;
  }

  function normalize(row, allowUndo = true) {
    if (!row || typeof row !== "object") throw new Error("提示词记录格式不正确。");
    const sourceRows = Array.isArray(row.origin?.sources) ? row.origin.sources : [];
    const originSources = sourceRows.filter((source) => source && typeof source.id === "string").map((source) => ({
      id: source.id, package_version: source.package_version ?? "",
      sha256: String(source.sha256 || ""), scope: String(source.scope || "imported")
    }));
    const record = {
      content: String(row.content ?? ""), note: String(row.note ?? row.design_note ?? ""),
      status: row.status === "ready" ? "ready" : "draft",
      origin: { type: String(row.origin?.type || "imported"), sources: originSources },
      review_decision: row.review_decision ? clone(row.review_decision) : null
    };
    if (!approved(record)) record.review_decision = null;
    if (allowUndo && row.undo) record.undo = normalize(row.undo, false);
    return record;
  }

  function restore(raw) {
    const state = seed();
    if (!raw || !raw.slots || Array.isArray(raw.slots)) return state;
    state.projectTitle = String(raw.projectTitle || "");
    state.generalNotes = String(raw.generalNotes || "");
    slots.forEach((slot) => {
      if (Object.hasOwn(raw.slots, slot.id)) {
        state.slots[slot.id] = normalize(raw.slots[slot.id]);
      }
    });
    return state;
  }

  function load() {
    try { return restore(JSON.parse(localStorage.getItem(key) || "null")); }
    catch (_) { return seed(); }
  }

  function approve(record, type = "current") {
    if (!usable(record.content)) throw new Error("空白或占位稿不能通过，请先填写正文。");
    record.review_decision = {
      decision: "approved", type, approved_at: new Date().toISOString(),
      approved_content: record.content, sources: clone(record.origin.sources)
    };
    record.status = "ready";
  }

  function adopt(record, ids, pass) {
    if (!ids.length || ids.some((id) => !sources[id] || !usable(sources[id].text))) {
      throw new Error("请选择有完整正文的来源。");
    }
    const previous = clone(record);
    delete previous.undo;
    record.undo = previous;
    record.content = ids.map((id) => sources[id].text).join("\n\n");
    record.origin = { type: pass ? "legacy_adopted" : "source_adopted", sources: ids.map(provenance) };
    record.review_decision = null;
    record.status = "draft";
    if (pass) approve(record, "legacy");
  }

  function edit(record, value) {
    if (record.content === value) return;
    record.content = value;
    record.origin.type = "edited";
    record.review_decision = null;
    record.status = "draft";
  }

  function importPayload(payload, current) {
    if (!payload || !["arcvellum/prompt-design-submission/v1", schema].includes(payload.schema) ||
        !Array.isArray(payload.slots)) {
      throw new Error("请选择设计台导出的 v1 或 v2 JSON 文件。");
    }
    const next = clone(current);
    next.projectTitle = String(payload.project_title ?? current.projectTitle);
    next.generalNotes = String(payload.general_notes ?? current.generalNotes);
    let matched = 0;
    payload.slots.forEach((row) => {
      if (!row || !Object.hasOwn(next.slots, row.id)) return;
      next.slots[row.id] = normalize(row);
      matched++;
    });
    if (!matched) throw new Error("文件没有本设计台可识别的提示词 ID。");
    return next;
  }

  function exportPayload(state) {
    const rows = slots.map((slot) => {
      const record = state.slots[slot.id];
      const pass = approved(record);
      return {
        id: slot.id, group: slot.group, title: slot.title, scope: slot.scope,
        slot_type: slot.fixed ? "fixed_protocol" : "literary_design",
        status: record.content.trim() ? (pass ? "ready" : "draft") : "empty",
        content: record.content, design_note: record.note,
        legacy_references: slot.refs.slice(), origin: clone(record.origin),
        review_decision: pass ? clone(record.review_decision) : null
      };
    });
    return {
      schema, exported_at: new Date().toISOString(), project_title: state.projectTitle,
      general_notes: state.generalNotes, slot_count: rows.length,
      filled_count: rows.filter((row) => row.status !== "empty").length,
      approved_count: rows.filter((row) => row.review_decision).length,
      source_snapshot: clone(library.manifest), runtime_activation: "unchanged",
      slots: rows
    };
  }

  window.DeskState = {
    library, slots, sources, key, load, restore, seed, approved, usable,
    approve, adopt, edit, importPayload, exportPayload, clone
  };
})();
