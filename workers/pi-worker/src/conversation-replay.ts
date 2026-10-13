import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile, rename, lstat, realpath, rmdir, unlink } from "node:fs/promises";
import { join, resolve, relative, isAbsolute } from "node:path";
import type { AgentMessage } from "@earendil-works/pi-agent-core";
import type { RuntimeEventSink } from "./contracts.ts";

const hash = (value: unknown) => createHash("sha256").update(JSON.stringify(value) ?? "undefined").digest("hex");
const record = (value: unknown): value is Record<string, any> => Boolean(value) && typeof value === "object" && !Array.isArray(value);
export interface ConversationSessionRef { schema: "arcvellum/conversation-session-ref/v1"; id: string; binding: string; }
interface Snapshot { head: string; fields: Record<string, unknown>; }
interface Checkpoint {
  schema: "arcvellum/conversation-replay/v1"; generation: number; binding: string; identity: string;
  status: "running" | "completed" | "blocked"; messages: AgentMessage[]; lastInput: string;
  answer: string; snapshot: Snapshot | null;
}
export function sessionRef(prompt: string): ConversationSessionRef | null {
  let value: any;
  try { value = JSON.parse(prompt); } catch { return null; }
  const ref = value?.conversation_session;
  if (ref === undefined) return null;
  if (!record(ref) || ref.schema !== "arcvellum/conversation-session-ref/v1" ||
      !/^[a-f0-9]{64}$/.test(ref.id) || !/^[a-f0-9]{64}$/.test(ref.binding)) throw new Error("invalid conversation session reference");
  return ref as ConversationSessionRef;
}
function snapshot(prompt: string): Snapshot | null {
  for (const marker of ["本次创作资料：\n", "本次审读资料：\n"]) {
    const at = prompt.indexOf(marker);
    if (at >= 0) {
      try { const fields = JSON.parse(prompt.slice(at + marker.length));
        return record(fields) ? { head: prompt.slice(0,at + marker.length), fields } : null;
      } catch { return null; }
    }
  }
  try { const fields = JSON.parse(prompt); return record(fields) ? {head:"",fields} : null; } catch { return null; }
}
export function contextUpdate(prior: Snapshot | null, prompt: string, revision: number) {
  const next = snapshot(prompt);
  if (!prior || !next || prior.head !== next.head) return { prompt, snapshot: next, changed: false };
  const changed = Object.fromEntries(Object.entries(next.fields).filter(([key,value]) => hash(value) !== hash(prior.fields[key])));
  const removed = Object.keys(prior.fields).filter(key => !(key in next.fields));
  return { prompt: "【当前授权上下文更新】以本版 changed 字段替代旧值；removed 字段不再生效。保留的候选与旧稿不代表已发生事实或已应用 Canon。\n" +
    JSON.stringify({revision, changed, removed}), snapshot:next, changed:true };
}
function inside(root: string, path: string) { const rel=relative(root,path); return rel==="" || (!rel.startsWith("..") && !isAbsolute(rel)); }
async function exists(path: string) { try { await lstat(path); return true; } catch (e) { if ((e as NodeJS.ErrnoException).code==="ENOENT") return false; throw e; } }
function authorizedProjection(messages: AgentMessage[]) {
  return messages.flatMap((msg:any) => msg.role==="user" ? [{role:"user",content:msg.content}] :
    msg.role==="assistant" ? [{role:"assistant",content:msg.content.filter((b:any)=>b.type==="text").map((b:any)=>b.text).join("")}] : []);
}

/** A private SDK checkpoint, not project facts. Incomplete generations are never resumed. */
export class ConversationReplay {
  messages: AgentMessage[]=[];
  prompt: string;
  reusedAnswer: string | null=null;
  requestSeriesId: string;
  private state: Checkpoint;
  private dir: string;
  private lease: string;
  private constructor(dir: string, emit: RuntimeEventSink, lease: string,
      ref: ConversationSessionRef, identity: string, prompt: string, seed: AgentMessage[],
      projected: boolean, limit: number, old: Checkpoint | null) {
    this.dir=dir; this.lease=lease;
    let reason="initial";
    let usable=old?.status==="completed" && old.binding===ref.binding && old.identity===identity;
    if (old && !usable) reason=old.status!=="completed" ? "incomplete-generation" : "binding-changed";
    if (usable && projected && hash(authorizedProjection(seed))!==hash(authorizedProjection(old!.messages))) {
      usable=false; reason="authorized-history-changed";
    }
    const size=usable ? Buffer.byteLength(JSON.stringify(old!.messages)+prompt,"utf8") : 0;
    if (usable && size>limit) { usable=false;reason="context-budget"; }
    if (!usable && Buffer.byteLength(JSON.stringify(seed)+prompt,"utf8") > limit)
      throw new Error("authorized conversation snapshot exceeds context budget");
    const generation=usable ? old!.generation : (old?.generation ?? 0)+1;
    this.requestSeriesId="arcvellum-series-"+ref.id.slice(0,24)+"-"+generation;
    this.prompt=prompt;
    this.state={schema:"arcvellum/conversation-replay/v1",generation,binding:ref.binding,identity,
      status:"running",messages:usable ? old!.messages : seed,lastInput:hash(prompt),answer:"",snapshot:snapshot(prompt)};
    this.messages=this.state.messages;
    if (usable && old!.lastInput===hash(prompt) && !projected) this.reusedAnswer=old!.answer;
    else if (usable && !projected) {
      const update=contextUpdate(old!.snapshot,prompt,generation);
      this.prompt=update.prompt;
    }
    emit("runner.conversation.replay",{schema:"arcvellum/conversation-replay-receipt/v1",
      request_series_id:this.requestSeriesId,generation,restored:usable,reason,
      message_count:this.messages.length,local_answer_reused:this.reusedAnswer!==null});
  }
  static async open(root: string, workspace: string, ref: ConversationSessionRef, identity: unknown,
      prompt: string, seed: AgentMessage[], projected: boolean, limit: number, emit: RuntimeEventSink) {
    const target=resolve(root);
    if (inside(resolve(workspace),target)) throw new Error("conversation replay must remain outside the work project");
    await mkdir(target,{recursive:true});
    if (inside(await realpath(workspace),await realpath(target))) throw new Error("conversation replay escapes its private store");
    const dir=join(target,ref.id);
    if (await exists(dir) && (await lstat(dir)).isSymbolicLink()) throw new Error("symlink replay directory rejected");
    await mkdir(dir,{recursive:true});
    const lease=join(dir,".lease");
    try { await mkdir(lease); } catch (e) {
      if ((e as NodeJS.ErrnoException).code!=="EEXIST") throw e;
      if ((await lstat(lease)).isSymbolicLink()) throw new Error("symlink replay lease rejected");
      let alive=true;
      try { const pid=Number(await readFile(join(lease,"pid"),"utf8")); if (!Number.isSafeInteger(pid) || pid<=0) throw new Error("invalid replay lease"); process.kill(pid,0); }
      catch (failure) { if ((failure as NodeJS.ErrnoException).code==="ESRCH") alive=false; else throw new Error("conversation replay lease is busy or invalid"); }
      if (alive) throw new Error("conversation replay is busy");
      await unlink(join(lease,"pid")); await rmdir(lease); await mkdir(lease);
    }
    await writeFile(join(lease,"pid"),String(process.pid),{flag:"wx"});
    try {
      const path=join(dir,"current.json");
      let old: Checkpoint | null=null;
      if (await exists(path)) {
        if ((await lstat(path)).isSymbolicLink()) throw new Error("symlink replay checkpoint rejected");
        old=JSON.parse(await readFile(path,"utf8"));
        if (!old || old.schema!=="arcvellum/conversation-replay/v1" || !Array.isArray(old.messages) ||
            !Number.isSafeInteger(old.generation)) throw new Error("invalid conversation replay checkpoint");
      }
      const replay=new ConversationReplay(dir,emit,lease,ref,hash(identity),prompt,seed,projected,limit,old);
      if (replay.reusedAnswer===null) await replay.persist();
      return replay;
    } catch (error) { await unlink(join(lease,"pid")); await rmdir(lease);throw error; }
  }
  async finish(messages: AgentMessage[], answer: string, completed: boolean) {
    this.state.messages=messages;
    this.state.answer=answer;
    this.state.status=completed ? "completed" : "blocked";
    await this.persist();
  }
  private async persist() {
    const bytes=JSON.stringify(this.state);
    if (Buffer.byteLength(bytes,"utf8")>8_000_000) throw new Error("conversation replay exceeds private storage budget");
    const temporary=join(this.dir,"checkpoint-"+randomUUID()+".tmp");
    await writeFile(temporary,bytes,{flag:"wx"});
    await rename(temporary,join(this.dir,"current.json"));
    const generationPath=join(this.dir,"generation-"+this.state.generation+".json");
    if (await exists(generationPath) && (await lstat(generationPath)).isSymbolicLink()) throw new Error("symlink replay generation rejected");
    await writeFile(generationPath,bytes);
  }
  async close() { await unlink(join(this.lease,"pid")); await rmdir(this.lease); }
}
