"""Original case briefs and archive facts; body prose is always produced by the runtime."""
from pathlib import Path
import json

from literary_engineering_studio_engine.public.projects import InitOptions, init_work_project, atomic_write_batch
from literary_engineering_studio.application.style.owner_directive import read_owner_style_directive, write_owner_style_directive

CASES = {
    "daily": {
        "title": "退回来的搪瓷碗", "location": "老车站食堂",
        "premise": "停运前一天，食堂主人把多年前借出去的搪瓷碗收到手里。",
        "style": "克制、具体、有生活的阻力。沿物件的使用痕迹和对白间隙展开，停顿有实际来由，长短句随人的注意力变化。",
        "people": {
            "陶婶": "六十一岁，经营食堂。说话常从分量、火候、谁吃没吃开始，讨厌空口谈感情。紧张时先把不平的碗底扶正。希望女儿回来，又觉得催她是给她添债。",
            "许钉": "二十四岁的修车学徒，语气快、具体，喜欢用零件绰号记人。受了照顾便过度报账，怕被当作可怜人；急时话里漏出童年称呼。今晚将离开小城。",
        },
        "goals": ["许钉来退搪瓷碗，陶婶以汤的分量试探他今晚是否留下。借两种不同的声音和一件反复使用的物，形成一次没有说透的挽留；许钉留下来修一张晃动的桌子。",
                  "接上修桌的过程，陶婶收到女儿的语音，许钉听见她答复里的迟疑。桌子稳下来后，两人对今晚那顿饭达成具体约定，挽留的意思由行动发生变化。"],
        "materials": "希望实际咨询角色扮演器、环境创作者和人物描写者。",
        "secret": "陶婶把女儿旧饭盒留了七年，这件事许钉尚未得知。",
    },
    "conflict": {
        "title": "欠条上的红线", "location": "河堤票房",
        "premise": "涨水之前，票房老板和摆渡人争论一张可能救人也可能毁掉生计的欠条。",
        "style": "尖锐、带锋芒的口语与紧贴身体的叙述交替。让打断、改口和实际动作形成压力，人物的职业经验进入词语。",
        "people": {
            "顾砚": "守票房的前账房，凡事说清笔数和凭据，冷话尾部常落一个反问。害怕被说成靠规则吃人，越难堪越把纸折齐。想保住票房。",
            "季桑": "摆渡人，话短，常以水势和绳索判断事情，嘲笑别人也会先伸手拉人。怒时抬嗓门，真正害怕时声音压低。想把渡船移去接被困的人。",
        },
        "goals": ["两人争论是否兑现欠条释放船只。让各自正当的欲望相撞，季桑作出一个顾砚没预料到的让步，顾砚同意开柜找原票。",
                  "承接开柜，顾砚发现原票被水泡模糊，季桑把手伸向最后一张能证明债务的存根。通过一次具体选择改变双方风险分担方式，渡船获得出发条件。"],
        "materials": "希望实际咨询两人的角色扮演器和环境创作者，寻找交锋、退让与身体动作的不同质地。",
        "secret": "顾砚曾用自己的钱替季桑家垫过一笔药费，季桑不知道。",
    },
    "spatial": {
        "title": "换景前的绳结", "location": "县剧院后台",
        "premise": "灯光失灵，演员和舞台工在狭小后台完成一次临时换景。",
        "style": "有运动感、空间感的群像叙述。句子跟着目光、手势和受阻的动作移动，声音保留各人的位置与职业习惯。",
        "people": {
            "程绳": "老舞台工，只谈受力、轻重和哪只手空着；常用最小的动作纠正别人。怕退休后被遗忘，关照人时说成检查东西。",
            "白禾": "年轻演员，兴奋时连声重复对方最后一个词，平时以戏里的意象说日常事。压住慌张时突然说得非常直白，想证明自己能撑住临场变化。",
        },
        "goals": ["幕布绳结卡住，两人从不同位置发现问题。借角色响应和已有动作的场面构图呈现位置、遮挡与协作，白禾钻到侧台拿来备用绳。",
                  "延续拿绳的位置与台前声响，在观众看不见的后台完成换景。程绳改变原先单独操作的办法，让白禾承担一个关键动作，协作关系因此改变。"],
        "materials": "希望实际咨询角色扮演器、场面创作者和环境创作者，尤其寻找已发生动作的可感空间组织。",
        "secret": "程绳收到退休通知，白禾尚不知道。",
    },
    "revelation": {
        "title": "盐仓记事", "location": "旧盐仓档案间",
        "premise": "修缮盐仓时找到一本被反复涂改的账册，仓管和抄写员对它给出不同解释。",
        "style": "带旧物与地方记忆的叙述。让事件的来路从账册、口述和眼前用途逐步显现，叙述保持人的兴趣和时间的层次。",
        "people": {
            "邵仓": "仓管，说每件东西先说来处和保管方法；称数时总把零头算进去。珍惜可继续用的旧物，羞于承认记错，纠正自己时改称‘那一阵’。",
            "杜字": "抄写员，语气客气，追问却执拗。记话时复述别人的关键词，遇见删改会问谁当时在场。想找到文字与实际生活之间的错位。",
        },
        "goals": ["两人核对账册中的一处涂改，杜字提出追问，邵仓讲出一段可归于其亲历的旧事。把场外事件叙述带入眼前动作，保留仍待确认的地方。",
                  "接上账册与口述，两人到同一盐仓的封门处查看旧标记。新的可见证据改变上一场的一项理解，两人选择把哪个问题留给下一位在场者。"],
        "materials": "希望实际咨询角色扮演器、事件叙述者和人物描写者，让口述的来源与场外经历具有可读的文学层次。",
        "secret": "涂改由已离开的前任仓管完成，目前人物尚不能确认其目的。",
    },
}


def prepare_case(folder: Path, case_id: str) -> Path:
    case, project = CASES[case_id], folder / "work"
    if (folder / "case-seed.json").is_file():
        if json.loads((folder / "case-seed.json").read_text(encoding="utf-8")) != case:
            raise ValueError("案例种子已变化，请用新的 variant 保存独立对照。")
        return project
    if not (project / "project.yaml").is_file():
        init_work_project(InitOptions(project, title=case["title"], target_length=2200, premise=case["premise"]))
    files = {project / "canon/world_rules.yaml": "rules: [人物依靠亲历与交谈获得信息, 物件与行动遵循日常物理条件]\n"}
    for index, (name, detail) in enumerate(case["people"].items()):
        files[project / f"characters/person-{index+1}.yaml"] = f"name: {name}\ncharacter_id: person-{index+1}\nprofile: {detail}\n"
    for index, goal in enumerate(case["goals"], 1):
        files[project / f"scenes/scene_{index:04d}.yaml"] = (
            f"scene_id: scene_{index:04d}\nchapter_id: chapter_01\nscene_goal: {goal}\n"
            f"participants: [{', '.join(case['people'])}]\nlocation: {case['location']}\nviewpoint: {next(iter(case['people']))}\n"
            "word_count_target: 850\nword_count_min: 500\nword_count_max: 1400\ncharacter_state_change: 2\n"
            "input_state:\n  canon_refs: [canon/world_rules.yaml]\n")
    direction = case["style"] + "\n" + case["materials"]
    files[project / "workflow/studio/user_directions.md"] = "# 作者方向\n" + direction
    files[project / "workflow/studio/user_directions.jsonl"] = json.dumps({"message": direction}, ensure_ascii=False) + "\n"
    files[project / "plot/lean_project_plan.json"] = json.dumps({"premise": case["premise"],
        "central_question": "具体处境如何改变两人理解和承担彼此的方式？", "ending_choice": case["goals"][-1]}, ensure_ascii=False)
    files[project / "canon/director_reference.md"] = "# 作者设定参考\n" + case["secret"]
    atomic_write_batch(files)
    write_owner_style_directive(project, content=case["style"], base_revision=read_owner_style_directive(project)["revision"], reason="本次隔离文学验收的作者文风")
    (folder / "case-seed.json").write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    return project
