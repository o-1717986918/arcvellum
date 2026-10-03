/* DOM behavior tests; no browser/network or visual verification is implied. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { JSDOM, VirtualConsole } = require("jsdom");

const html = fs.readFileSync(process.argv[2], "utf8");
const errors = [];
const consoleBridge = new VirtualConsole();
consoleBridge.on("jsdomError", (error) => errors.push(error));

function open(initial) {
  return new JSDOM(html, {
    url: "https://prompt-desk.test/", runScripts: "dangerously", virtualConsole: consoleBridge,
    beforeParse(window) {
      if (initial) window.localStorage.setItem("arcvellum-scene-prompt-design-v1", JSON.stringify(initial));
    }
  });
}

const page = open();
const w = page.window;
const d = w.document;
const api = w.PromptDesk;
const model = w.DeskState;
const sourceSelect = d.getElementById("sourceSelect");
const input = d.getElementById("promptText");
const click = (id) => d.getElementById(id).click();
const json = (value) => JSON.parse(JSON.stringify(value));
assert.equal(errors.length, 0, errors.map((error) => error.message).join("\n"));
assert.equal(api.exportPayload().slot_count, 26);
assert.equal(api.exportPayload().approved_count, 0);
assert.equal(api.exportPayload().slots.filter((slot) => slot.scope === "v2").length, 20);
assert.equal(Object.keys(model.sources).length, 64);
assert.equal(d.getElementById("sourceText").value, model.sources[model.slots[0].refs[0]].text);
assert.equal(d.getElementById("sourceHeading").textContent, "旧提示词全文");
click("showCurrentButton");
assert.equal(d.getElementById("sourceText").value, model.sources[model.slots[0].id].text);
click("showLegacyButton");
assert.equal(d.getElementById("sourceText").value, model.sources[model.slots[0].refs[0]].text);

api.select("scene.v2.creator.create");
const before = json(api.getState().slots["scene.v2.creator.create"]);
sourceSelect.value = "scene.creator.create";
sourceSelect.dispatchEvent(new w.Event("change"));
assert.equal(d.getElementById("sourceText").value, model.sources["scene.creator.create"].text);
const otherLegacy = d.querySelectorAll("#legacyList button")[1];
otherLegacy.click();
assert.equal(d.getElementById("sourceText").value, model.sources[otherLegacy.textContent].text);
sourceSelect.value = "scene.creator.create";
sourceSelect.dispatchEvent(new w.Event("change"));
assert.match(d.getElementById("sourceMeta").textContent, /SHA-256/);
click("adoptSourceButton");
let current = api.getState().slots["scene.v2.creator.create"];
assert.equal(current.content, model.sources["scene.creator.create"].text);
assert.equal(model.approved(current), true);
assert.equal(current.review_decision.type, "legacy");
assert.equal(current.review_decision.sources[0].sha256, model.sources["scene.creator.create"].sha256);
assert.equal(api.exportPayload().approved_count, 1);
click("undoButton");
assert.deepEqual(json(api.getState().slots["scene.v2.creator.create"]), before);

const checks = [...d.querySelectorAll("#legacyChecks input")];
checks.slice(0, 2).forEach((checkbox) => { checkbox.checked = true; });
const ids = checks.slice(0, 2).map((checkbox) => checkbox.value);
click("adoptManyButton");
current = api.getState().slots["scene.v2.creator.create"];
assert.equal(current.content, ids.map((id) => model.sources[id].text).join("\n\n"));
assert.deepEqual(json(current.review_decision.sources.map((source) => source.id)), ids);
assert.equal(model.approved(current), true);
const huge = "特色声音\n".repeat(15000);
input.value = huge;
input.dispatchEvent(new w.Event("input"));
assert.equal(current.content, huge);
assert.equal(model.approved(current), false);
click("approveButton");
assert.equal(model.approved(current), true);
const note = d.getElementById("designNote");
note.value = "应保留这一声音";
note.dispatchEvent(new w.Event("input"));
assert.equal(model.approved(current), true);
assert.equal(api.exportPayload().slots.find((slot) => slot.id === "scene.v2.creator.create").content.length, huge.length);
click("revokeButton");
assert.equal(model.approved(current), false);

input.value = "";
input.dispatchEvent(new w.Event("input"));
assert.equal(d.getElementById("approveButton").disabled, true);
input.value = "[PENDING_PROMPT_DESIGN: missing]";
input.dispatchEvent(new w.Event("input"));
assert.equal(d.getElementById("approveButton").disabled, true);

// Old ready means editable, not a new human approval. Unmentioned slots survive import.
api.select("project_agent.creative_direction");
click("approveButton");
const oldTop = json(api.getState().slots["project_agent.creative_direction"]);
api.replaceState(api.importPayload({
  schema: "arcvellum/prompt-design-submission/v1", project_title: "旧填写",
  slots: [{ id: "scene.v2.creator.create", content: "保留我的旧稿", status: "ready", design_note: "旧备注" }]
}));
assert.equal(api.getState().slots["scene.v2.creator.create"].content, "保留我的旧稿");
assert.equal(model.approved(api.getState().slots["scene.v2.creator.create"]), false);
assert.deepEqual(json(api.getState().slots["project_agent.creative_direction"]), oldTop);
const exported = json(api.exportPayload());
api.replaceState(api.importPayload(exported));
assert.equal(api.exportPayload().approved_count, 1);
exported.slots.find((slot) => slot.id === "project_agent.creative_direction").content += "已变更";
api.replaceState(api.importPayload(exported));
assert.equal(api.exportPayload().approved_count, 0);
assert.throws(() => api.importPayload({ schema: "wrong", slots: [] }), /v1/);

// Imported markup is text. Source embedding cannot terminate the JSON script.
const hostile = "</script><img src=x onerror='window.bad=1'>";
api.replaceState(api.importPayload({
  schema: "arcvellum/prompt-design-submission/v2",
  slots: [{ id: "scene.v2.creator.create", content: hostile }]
}));
api.select("scene.v2.creator.create");
assert.equal(input.value, hostile);
assert.equal(d.querySelector("img"), null);
assert.equal(w.bad, undefined);
assert.equal(d.getElementById("sourceSelect").options[0].value, "scene.v2.creator.create");
assert.ok([...d.getElementById("sourceSelect").options].some((option) => option.value === "scene.creator.create"));

// Browser drafts, including intentionally blank text, survive upgrades and reloads.
const stored = {
  projectTitle: "原方案", slots: {
    "scene.v2.creator.identity": { content: "用户自己的未导出文字", note: "保留", status: "ready" },
    "scene.v2.creator.create": { content: "", note: "有意留空" }
  }
};
const upgraded = open(stored);
assert.equal(upgraded.window.PromptDesk.getState().slots["scene.v2.creator.identity"].content, "用户自己的未导出文字");
assert.equal(upgraded.window.PromptDesk.getState().slots["scene.v2.creator.create"].content, "");
assert.equal(upgraded.window.PromptDesk.exportPayload().approved_count, 0);
assert.equal(upgraded.window.PromptDesk.exportPayload().slot_count, 26);
upgraded.window.close();

// Delete only the exact retired introduction, including in already saved/imported cards.
const history = model.sources["scene.v2.material.actor@package-v2"].text;
const cardWithEdits = history.replace("{{CORE_IDENTITY}}", "用户自己修改的身份区块");
const migrated = open({
  slots: { "scene.v2.material.actor": {
    content: cardWithEdits, note: "保留我的备注", status: "ready",
    review_decision: { decision: "approved", approved_content: cardWithEdits }
  } }
});
const cardRecord = migrated.window.PromptDesk.getState().slots["scene.v2.material.actor"];
assert.ok(cardRecord.content.startsWith("【PERSONA_LOAD】"));
assert.ok(cardRecord.content.includes("用户自己修改的身份区块"));
assert.equal(cardRecord.note, "保留我的备注");
assert.equal(cardRecord.review_decision, null);
migrated.window.close();
const importedCard = api.importPayload({
  schema: "arcvellum/prompt-design-submission/v2",
  slots: [{ id: "scene.v2.material.actor", content: cardWithEdits, design_note: "导入备注" }]
});
assert.ok(importedCard.slots["scene.v2.material.actor"].content.startsWith("【PERSONA_LOAD】"));
assert.equal(importedCard.slots["scene.v2.material.actor"].note, "导入备注");

// 26-slot DOM is accessible and navigable; this is not a rendered layout test.
assert.equal(d.querySelectorAll(".slot-button").length, 26);
api.select(model.slots[0].id);
assert.equal(d.getElementById("prevButton").disabled, true);
api.select(model.slots.at(-1).id);
assert.equal(d.getElementById("nextButton").disabled, true);
d.getElementById("searchSlots").value = "不存在的条目";
d.getElementById("searchSlots").dispatchEvent(new w.Event("input"));
assert.equal(d.querySelectorAll(".slot-button").length, 0);
assert.equal(errors.length, 0, errors.map((error) => error.message).join("\n"));
w.close();
console.log("PASS: full sources, legacy adoption, combined adoption, approvals, undo, long text, migration, provenance and text isolation");
