import { describe, expect, it } from "vitest";
import { readParameterFiles } from "./stylometryImport";
function file(name: string, data: unknown): File {
  const text = typeof data === "string" ? data : JSON.stringify(data);
  return { name, size: text.length, text: async () => text } as File;
}
describe("Lab parameter files", () => {
  it("combines profile, legacy controls and a saved dependency tree without changing bands", async () => {
    const controls = { schema: "style-controls/v1", axes: { sentence_length_han: { min: 9.125, max: 24.875, unit: "汉字/句" } } };
    const result = await readParameterFiles([file("profile.json", { schema: "stylometric-profile/v1", profile_sha256: "abc" }),
      file("controls.json", controls), file("tree.json", { schema: "style-dependency-parse/v1", parse_hash: "tree" })]);
    expect(JSON.parse(result.parameters_json)).toEqual(controls);
    expect(JSON.parse(result.dependency_json).parse_hash).toBe("tree");
  });
  it("imports a host review export's current controls and intent rather than an older saved version", async () => {
    const doc = { schema: "arcvellum/stylometry-review-export/v1", title: "当前草稿", intent: "缓慢的声音",
      profile: { profile_json: '{"schema":"stylometric-profile/v1"}' }, controls: { targets: [{ min: 18 }] },
      saved_version: { title: "旧版", intent: "旧意图", controls_json: '{"targets":[{"min":3}]}' }, dependency_json: "" };
    const result = await readParameterFiles([file("review.json", doc)]);
    expect(result.title).toBe("当前草稿"); expect(result.intent).toBe("缓慢的声音");
    expect(JSON.parse(result.parameters_json)).toEqual(doc.controls);
  });
  it("rejects conflicting and unsupported files, and reads UTF-8 BOM cards", async () => {
    await expect(readParameterFiles([file("one.json", { schema: "style-controls/v1", axes: {} }),
      file("two.json", { schema: "style-controls/v1", axes: { other: {} } })])).rejects.toThrow("分开导入");
    await expect(readParameterFiles([file("other.json", { schema: "other" })])).rejects.toThrow("不是计量台");
    const result = await readParameterFiles([file("card.json", '\uFEFF{"schema":"style-parameter-card/v1","title":"河"}')]);
    expect(result.title).toBe("河");
  });
  it("retains integral float tokens and escaped nested text required by Lab digests", async () => {
    const raw = '{"schema":"stylometric-host/v1","profile":{"schema":"stylometric-profile/v1","axis":0.0,"text":"a\\\"},b"},"controls":{"value":1.0}}';
    const result = await readParameterFiles([file("host.json", raw)]);
    expect(result.profile_json).toContain('"axis":0.0'); expect(result.parameters_json).toBe('{"value":1.0}');
    const card = '{"schema":"style-parameter-card/v1","axes":[{"value":0.0}]}';
    expect((await readParameterFiles([file("card.json", card)])).parameters_json).toBe(card);
  });
});
