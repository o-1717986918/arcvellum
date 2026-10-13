import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { ActiveContextReads } from "../src/active-context-reads.ts";
import { createSceneArchiveTool, workArchiveOperation } from "../src/scene-creator-workspace-tool.ts";

describe("active context source delivery", () => {
  it("ignores object-key order but preserves array order, versions and knowledge", () => {
    const context = new ActiveContextReads();
    const first = { path: "facts", knowledge: "known", file_sha256: "v1",
      content: { lines: ["甲", "乙"], note: "完整原文" } };
    context.receipt(first, "first");
    expect(context.receipt({ content: { note: "完整原文", lines: ["甲", "乙"] },
      file_sha256: "v1", knowledge: "known", path: "facts" }, "reordered")).toHaveProperty("content_receipt");
    for (const value of [
      { ...first, knowledge: "reference" }, { ...first, file_sha256: "v2" },
      { ...first, content: { ...first.content, lines: ["乙", "甲"] } },
      { ...first, content: { ...first.content, note: "改变原文" } },
    ]) expect(context.receipt(value, "changed")).not.toHaveProperty("content_receipt");
    expect(new ActiveContextReads().receipt(first, "fresh")).toHaveProperty("content");
  });
  it("gives a receipt only after delivering the same source in this context", () => {
    const value = { candidate_id: "x", content: { spoken: "先让我听完这场雨。" } };
    const context = new ActiveContextReads();
    expect(context.receipt(value,"first")).toEqual(value);
    expect(context.receipt(value,"again")).toMatchObject({ candidate_id: "x",
      content_receipt: { source_tool_call_id: "first" } });
    expect(new ActiveContextReads().receipt(value,"new")).toEqual(value);
    expect(context.receipt({ ...value, content: { spoken: "新刺激改变了回应。" } },"changed")).not.toHaveProperty("content_receipt");
  });

  it("batch and individual reads match, repeat receipts retain version and new contexts receive text", async () => {
    const root = await mkdtemp(join(tmpdir(),"archive-cost-"));
    try {
      await writeFile(join(root,"facts.md"),"甲\n乙\n丙\n");
      const selectors=[{ path:"facts.md", start_line:1, end_line:2 },{ path:"facts.md",start_line:3,end_line:3 }];
      const batch=await workArchiveOperation(root,{ action:"read_batch", reads:selectors });
      const single=await Promise.all(selectors.map((row)=>workArchiveOperation(root,{ ...row,action:"read" })));
      expect(batch.reads).toEqual(single);
      const tool=createSceneArchiveTool(root,()=>{});
      const first=await tool.execute("first",{ action:"read",...selectors[0] });
      const second=await tool.execute("second",{ action:"read",...selectors[0] });
      expect(JSON.stringify(first.content)).toContain("甲");
      expect(JSON.stringify(second.content)).toContain("content_receipt");
      const newTool=createSceneArchiveTool(root,()=>{});
      expect(JSON.stringify((await newTool.execute("new",{ action:"read",...selectors[0] })).content)).toContain("甲");
      await expect(workArchiveOperation(root,{ action:"read_batch",reads:[{ path:"../outside" }] })).rejects.toThrow();
    } finally { await rm(root,{ recursive:true,force:true }); }
  });
});
