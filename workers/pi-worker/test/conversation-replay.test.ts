import { afterEach, describe, expect, it } from "vitest";
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ConversationReplay, contextUpdate, sessionRef } from "../src/conversation-replay.ts";

const roots:string[]=[];
afterEach(async()=>{ for(const root of roots.splice(0)) await rm(root,{recursive:true,force:true}); });
async function fixture() {
  const root=await mkdtemp(join(tmpdir(),"arc-replay-"));roots.push(root);
  const workspace=join(root,"work");await mkdir(workspace);
  return {workspace,store:join(root,"private")};
}
const ref={schema:"arcvellum/conversation-session-ref/v1" as const,id:"a".repeat(64),binding:"b".repeat(64)};
const messages:any[]=[{role:"user",content:"first",timestamp:1},
  {role:"assistant",content:[{type:"thinking",thinking:"retained SDK replay",thinkingSignature:"reasoning_content"},
    {type:"text",text:"answer"}],stopReason:"stop",timestamp:2}];
describe("private conversation replay",()=>{
  it("restores complete SDK messages and sends only changed context on a later process",async()=>{
    const f=await fixture(),events:any[]=[];
    const prompt='guidance\n本次创作资料：\n{"canon":"candidate, not applied","stage":"prepare","body":"full source"}';
    const first=await ConversationReplay.open(f.store,f.workspace,ref,{model:"m"},prompt,[],false,10000,(e,d)=>events.push(d));
    await first.finish(messages,"answer",true);await first.close();
    const next=prompt.replace('"prepare"','"create"');
    const second=await ConversationReplay.open(f.store,f.workspace,ref,{model:"m"},next,[],false,10000,(e,d)=>events.push(d));
    expect(second.messages).toEqual(messages);
    expect(second.prompt).toContain('"stage":"create"');
    expect(second.prompt).not.toContain("full source");
    expect(events[1].restored).toBe(true);
    expect(await readFile(join(f.store,ref.id,"current.json"),"utf8")).toContain("reasoning_content");
    await second.close();
  });
  it("reuses a completed identical invocation without a model request",async()=>{
    const f=await fixture();
    const first=await ConversationReplay.open(f.store,f.workspace,ref,{model:"m"},"first",[],false,10000,()=>{});
    await first.finish(messages,"answer",true);await first.close();
    const next=await ConversationReplay.open(f.store,f.workspace,ref,{model:"m"},"first",[],false,10000,()=>{});
    expect(next.reusedAnswer).toBe("answer");await next.close();
  });
  it("a projected history can restore only its exact authorized prior dialogue",async()=>{
    const f=await fixture();let receipt:any;
    let next=await ConversationReplay.open(f.store,f.workspace,ref,{tools:[]},"first",[],true,10000,()=>{});
    await next.finish(messages,"answer",true);await next.close();
    next=await ConversationReplay.open(f.store,f.workspace,ref,{tools:[]},"second",messages,true,10000,(e,d)=>receipt=d);
    expect(receipt.restored).toBe(true);await next.finish([...messages,{role:"user",content:"second"} as any],"next",true);await next.close();
    next=await ConversationReplay.open(f.store,f.workspace,ref,{tools:[]},"third",
      [{role:"user",content:"adapted reference"} as any],true,10000,(e,d)=>receipt=d);
    expect(receipt.reason).toBe("authorized-history-changed");
    expect(next.messages).toHaveLength(1);await next.close();
  });
  it("permission changes, incomplete attempts and context budget create fresh generations",async()=>{
    const f=await fixture();let receipt:any;
    let next=await ConversationReplay.open(f.store,f.workspace,ref,{tools:["read"]},"first",[],false,10000,()=>{});
    await expect(ConversationReplay.open(f.store,f.workspace,ref,{},"x",[],false,10000,()=>{})).rejects.toThrow("busy");
    await next.finish(messages,"answer",false);await next.close();
    next=await ConversationReplay.open(f.store,f.workspace,ref,{tools:["read"]},"retry",[],false,10000,(e,d)=>receipt=d);
    expect(receipt.reason).toBe("incomplete-generation");
    await next.finish(messages,"answer",true);await next.close();
    next=await ConversationReplay.open(f.store,f.workspace,ref,{tools:[]},"new",[],false,10000,(e,d)=>receipt=d);
    expect(receipt.reason).toBe("binding-changed");
    await next.finish(messages,"answer",true);await next.close();
    next=await ConversationReplay.open(f.store,f.workspace,ref,{tools:[]},"tiny",[],false,50,(e,d)=>receipt=d);
    expect(receipt.reason).toBe("context-budget");expect(next.prompt).toBe("tiny");await next.close();
  });
  it("rejects project writes and invalid opaque references",async()=>{
    const f=await fixture();
    await expect(ConversationReplay.open(join(f.workspace,"private"),f.workspace,ref,{},"first",[],false,10000,()=>{})).rejects.toThrow("outside");
    expect(()=>sessionRef(JSON.stringify({conversation_session:{...ref,id:"../escape"}}))).toThrow("invalid");
    expect(sessionRef("legacy plain text")).toBeNull();
    expect(contextUpdate({head:"",fields:{canon:"applied",old:"stale"}},'{"canon":"pending"}',2).prompt).toContain('"removed":["old"]');
  });
  it("appends newly introduced fields and withdraws removed values without losing original text",()=>{
    const update=contextUpdate({head:"",fields:{canon:"pending",old:"撤回资料"}},
      '{"canon":"pending","feedback":"新增反馈原文"}',2);
    expect(update.prompt).toContain('"changed":{"feedback":"新增反馈原文"}');
    expect(update.prompt).toContain('"removed":["old"]');
    expect(update.snapshot?.fields).toEqual({canon:"pending",feedback:"新增反馈原文"});
  });
});
