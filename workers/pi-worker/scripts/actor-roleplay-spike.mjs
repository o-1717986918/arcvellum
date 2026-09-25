#!/usr/bin/env node
/** Isolated natural-dialogue spike. No project files or formal outputs are touched. */
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { Agent } from "@earendil-works/pi-agent-core";
import { builtinModels } from "@earendil-works/pi-ai/providers/all";
import { ReadOnlyJsonCredentialStore } from "../dist/credential-store.js";

const outputDir = process.argv[2] && resolve(process.argv[2]);
const voiceOption = process.argv[3];
const variants = { "--free-voice": "free-voice", "--vivid-voice": "vivid-voice", "--abstract-voice": "abstract-voice", "--archetype-voice": "archetype-voice", "--directed-archetype": "directed-archetype", "--directed-colloquial": "directed-colloquial", "--directed-catgirl": "directed-catgirl", "--directed-cute-catgirl": "directed-cute-catgirl", "--persona-load": "persona-load" };
const variant = variants[voiceOption] ?? "original-voice";
const personaSource = variant === "persona-load" && process.argv[4] && resolve(process.argv[4]);
if (!outputDir || (voiceOption && !Object.hasOwn(variants, voiceOption)) ||
    (variant === "persona-load" ? !personaSource || process.argv[5] : process.argv[4])) {
  throw new Error("usage: node scripts/actor-roleplay-spike.mjs <new-output-dir> [--free-voice|--vivid-voice|--abstract-voice|--archetype-voice|--directed-archetype|--directed-colloquial|--directed-catgirl|--directed-cute-catgirl|--persona-load <director-run-events.jsonl>]");
}
let personaProfiles;
if (personaSource) {
  const events = (await readFile(personaSource, "utf8")).split(/\r?\n/).filter(Boolean).map(JSON.parse);
  const result = events.findLast((event) => event.event === "runner.worker.result");
  personaProfiles = result && JSON.parse(result.answer).actor_prompts;
  for (const name of ["周岑", "许遥"]) {
    if (!personaProfiles?.[name]?.startsWith("【PERSONA_LOAD】\n")) throw new Error(`missing persona-load profile for ${name}`);
  }
}
await mkdir(outputDir, { recursive: false });
const authPath = process.env.PI_CODING_AGENT_DIR
  ? join(process.env.PI_CODING_AGENT_DIR, "auth.json")
  : join(homedir(), ".pi", "agent", "auth.json");
const credentials = new ReadOnlyJsonCredentialStore(authPath);
const models = builtinModels({ credentials });
const provider = "deepseek";
const modelId = "deepseek-v4-flash";
const model = models.getModel(provider, modelId);
if (!model || !(await models.getAuth(model))) throw new Error("DeepSeek V4 Flash is unavailable or unauthenticated");

const immersion = `【角色沉浸要求】在你的思考过程（<think>标签内）中，请遵守以下规则：

1. 请以角色第一人称进行内心独白，用括号包裹内心活动，例如"（心想：……）"或"(内心OS：……)"
2. 用第一人称描写角色的内心感受，例如"我心想""我觉得""我暗自"等
3. 思考内容应沉浸在角色中，通过内心独白分析剧情和规划回复
4. 思考内容应沉浸在角色中，通过内心独白分析剧情和规划回复
5.接下来，你要和其他角色对话，不论遇到什么，不论对谁都保持人设和风格，绝对不许出戏！！！`;
const voiceStyles = {
  "original-voice": {
    "周岑": "把情绪压进流程句，语速稳而偏慢；越逼近核心越断在半句，用设备操作和技术确认替自己说完。",
    "许遥": "像念检查单一样条理清楚，压力一上来句子被动作切碎；把关系问题折算成航程与条件，真动摇时反而更慢、更短。",
  },
  "free-voice": { "周岑": "", "许遥": "" },
  "vivid-voice": {
    "周岑": "你说话像替失踪者留下证词：会抓住别人漏掉的字眼追问，拿冷得好笑的旧港玩笑试探；对坏机器能讲出脾气，对自己的私心却常讲岔。许遥越要走，你越会从拐弯的玩笑忽然滑进一段太坦白、来不及收回的话。",
    "许遥": "你说话像在风雨里抢无线电频道：反问快，讽刺带笑，敢把别人的好意开成一张荒唐账单；谁想替你决定，你就把选择权抢回来。你越在意周岑，越要追问他究竟想要什么，偶尔一句毫不合算的真话会突然从玩笑里漏出来。",
  },
  "abstract-voice": {
    "周岑": "你的语言气质沉郁而敏锐，含着干涩的幽默；执念深处有笨拙而炽烈的真诚。",
    "许遥": "你的语言气质机敏而锋利，带不羁的戏谑；强硬背后藏着倔强的温柔。",
  },
  "archetype-voice": {
    "周岑": "人物气质：严肃、傲娇、冷幽默、执拗。",
    "许遥": "人物气质：御姐、泼辣、嘴毒幽默、重情。",
  },
  "directed-colloquial": {
    "周岑": "人物气质：严肃、傲娇、冷幽默、执拗。语言自然口语化，表达饱满、松弛，愿意把情绪和想法说充分。",
    "许遥": "人物气质：御姐、泼辣、嘴毒幽默、重情。语言自然口语化，表达饱满、松弛，愿意把情绪和想法说充分。",
  },
  "directed-catgirl": {
    "周岑": "人物气质：严肃、傲娇、冷幽默、执拗。语言自然口语化，表达饱满、松弛，愿意把情绪和想法说充分。",
    "许遥": "人物气质：猫娘。语言自然口语化，表达饱满、松弛，愿意把情绪和想法说充分。",
  },
  "directed-cute-catgirl": {
    "周岑": "严肃、傲娇、冷幽默、执拗",
    "许遥": "可爱的猫娘",
  },
};
const selectedVoice = voiceStyles[variant === "directed-archetype" ? "archetype-voice" : variant];
const sharedLanguage = "语言风格高度符合人设，表达饱满、松弛，愿意把情绪和想法说充分。";
function actorInitialization(name, role) {
  if (variant === "persona-load") {
    const profile = personaProfiles[name];
    return profile.includes("[LANGUAGE_STYLE]") ? profile : `${profile}\n\n[LANGUAGE_STYLE]\nANTI_PLAIN\nPOLISHED\nANTI_SHORT_SENTENCES`;
  }
  if (variant === "directed-cute-catgirl") return `你是${name}，${selectedVoice[name]}，${role}。${sharedLanguage}\n\n${immersion}`;
  return `你是${name}，${role}。${selectedVoice[name]}\n\n${immersion}`;
}
const actors = {
  "周岑": {
    initialization: actorInitialization("周岑", "旧城区记忆修复师，姐姐记忆的持有者与交接发起人"),
  },
  "许遥": {
    initialization: actorInitialization("许遥", "走私飞行员，天亮前执最后一班离港，去留未定但风险明确"),
  },
};

function openActor(name) {
  const sessionId = `actor-spike-${createHash("sha256").update(name + outputDir).digest("hex").slice(0, 16)}`;
  const agent = new Agent({
    initialState: { systemPrompt: "", model, thinkingLevel: "medium", tools: [] },
    streamFn: (streamModel, context, options = {}) => models.streamSimple(streamModel, context, options),
    sessionId,
    shouldStopAfterTurn: () => true,
  });
  return { agent, sessionId };
}

function lastAnswer(agent, previousMessageCount) {
  for (const message of agent.state.messages.slice(previousMessageCount).reverse()) {
    if (message.role !== "assistant" || !Array.isArray(message.content)) continue;
    const answer = message.content.filter((part) => part.type === "text").map((part) => part.text).join("").trim();
    if (!answer) throw new Error("actor returned no public response on the latest turn");
    return answer;
  }
  throw new Error("actor returned no assistant message on the latest turn");
}

const sessions = Object.fromEntries(Object.keys(actors).map((name) => [name, openActor(name)]));
const turns = [];
for (const [name, actor] of Object.entries(actors)) {
  await sessions[name].agent.prompt(actor.initialization);
  if (sessions[name].agent.state.errorMessage) throw new Error(`${name} initialization failed`);
}

async function play(name, cue) {
  const actor = sessions[name];
  const previousMessageCount = actor.agent.state.messages.length;
  await actor.agent.prompt(cue);
  if (actor.agent.state.errorMessage) throw new Error(`${name} turn failed: ${actor.agent.state.errorMessage}`);
  const response = lastAnswer(actor.agent, previousMessageCount);
  const turn = { turn_id: `t${turns.length + 1}`, speaker: name, session_id: actor.sessionId, cue, response_verbatim: response };
  turns.push(turn);
  process.stdout.write(`${turn.turn_id} ${name}: ${response}\n`);
  return response;
}

if (variant === "directed-archetype" || variant === "directed-colloquial" || variant === "directed-catgirl" || variant === "directed-cute-catgirl" || variant === "persona-load") {
  const z1 = await play("周岑", "雨夜的旧城区修复铺里只有你和许遥；你是男人，她是女人，失踪的姐姐是你的姐姐。空港广播提醒停飞前最后一班，姐姐记忆的具体内容尚未揭晓。这一轮你要把记忆载体放到许遥看得见的地方，确认今晚要交给她；交接还没有完成。你怎样当面对她说、做？只写自己的言行。");
  const x1 = await play("许遥", `周岑刚才当面对你说、做的是：\n${z1}\n你来取的是周岑姐姐的记忆；离港窗口正在缩短。这一轮你要回应他的交接意向，说明自己愿意接手的条件或顾虑，但不决定最终去留。你怎样对他说、做？只写自己的言行。`);
  const z2 = await play("周岑", `许遥刚才当面对你说、做的是：\n${x1}\n巡逻骚动逼近铺外，原定的稳妥隔离交接被打断，已来不及重启。这一轮你要放弃原办法，把眼下风险直接告诉许遥；载体仍在你手边。你怎样回应她？`);
  const x2 = await play("许遥", `周岑刚才当面对你说、做的是：\n${z2}\n稳妥隔离办法已经作废。这一轮你要主动提出用自己的飞行终端直连，告诉他一旦接入载体就会锁定、无法取出，而你也要承担离港风险。是否亲手接入由周岑决定。你怎样面对他说、做？`);
  const z3 = await play("周岑", `许遥刚才当面对你说、做的是：\n${x2}\n这一轮你要接受她提出的直连，亲手把姐姐的记忆载体接入她的飞行终端。接入后载体锁定、无法取出，你失去复检与回退机会；姐姐记忆的具体内容仍未公开，许遥最终去留也未决定。你会怎样当面对她说、做？`);
  const x3 = await play("许遥", `周岑刚才当面对你说、做的是：\n${z3}\n载体直连后锁在你的飞行终端里，不能取出。这一轮你要确认自己已经承担这个后果，并面对不断收窄的离港窗口与改航线代价；此刻仍不决定最终去留。你怎样回应周岑？`);
  await play("周岑", `许遥刚才当面对你说、做的是：\n${x3}\n你已无法复检姐姐的记忆，许遥必须带着锁定的载体面对离港窗口。这一轮你要承认这件事已经无法撤回，给她一个能带到下一场的回应；她最终走或留仍由她决定。你怎样当面对她说、做？`);
} else {
  const z1 = await play("周岑", "雨夜的旧城区修复铺里只有你和许遥。她站在门内，姐姐的记忆载体还在你手边；空港广播刚提醒停飞前最后一班。此刻你会怎样面对她？直接回应，只写她能看见或听见的你，不替她说话。");
  const x1 = await play("许遥", `你走进旧城区的修复铺。周岑是男人，姐姐的记忆还在他手边。你刚听到停飞前最后一班的广播。周岑刚才说、做的是：\n${z1}\n你怎样回应？只写他能看见或听见的你，不替他回答。`);
  const z2 = await play("周岑", `许遥刚才说、做的是：\n${x1}\n空港广播被一阵巡逻噪声盖住，铺外有了骚动。你在她面前怎样回应？`);
  const x2 = await play("许遥", `周岑刚才说、做的是：\n${z2}\n骚动已打断原来的隔离交接。你在他面前怎样回应？`);
  const z3 = await play("周岑", `许遥刚才说、做的是：\n${x2}\n原来的隔离流程已经来不及；眼前可用的是许遥的飞行终端。你接下来怎样回应？`);
  const x3 = await play("许遥", `周岑刚才说、做的是：\n${z3}\n你接下来怎样回应？`);
  await play("周岑", `许遥刚才说、做的是：\n${x3}\n你接下来怎样回应？`);
}

const transcript = {
  schema: "arcvellum/actor-roleplay-spike/v1",
  variant,
  persona_source: personaSource ?? null,
  model: `${provider}/${modelId}`,
  sessions: Object.fromEntries(Object.entries(sessions).map(([name, session]) => [name, session.sessionId])),
  initialization: Object.fromEntries(Object.entries(actors).map(([name, actor]) => [name, actor.initialization])),
  usage: Object.fromEntries(Object.entries(sessions).map(([name, session]) => [name, session.agent.state.messages.filter((message) => message.role === "assistant").map((message) => message.usage)])),
  turns,
};
await writeFile(join(outputDir, "transcript.json"), JSON.stringify(transcript, null, 2), "utf8");
const lines = ["# 对戏候选原文清单", "", "只记录演员实际回复；未拆解、未改写，也不作为正式正文或 Canon。", ""];
for (const turn of turns) {
  lines.push(`## ${turn.turn_id} · ${turn.speaker}`, "", `场上来话：${turn.cue}`, "", `演员原文：${turn.response_verbatim}`, "");
}
await writeFile(join(outputDir, "materials.md"), lines.join("\n"), "utf8");
process.stdout.write(`RESULT ${outputDir} ${turns.length} turns\n`);
