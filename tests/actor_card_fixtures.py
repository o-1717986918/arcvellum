"""A bounded creator-authored card for contract and runtime tests."""

from literary_engineering_studio_engine.public.literary import ACTOR_CARD_SCHEMA, ACTOR_CARD_SECTIONS


def actor_card_payload(target="阿青"):
    sections = {key: "暂无明确资料；不添加未经确认的经历。" for key in ACTOR_CARD_SECTIONS}
    sections.update({
        "PERSONA_LOAD": f"目标角色：{target}。中文回应；眼前只见到一个空信封。",
        "CORE_IDENTITY": f"姓名：{target}；其余身份暂无明确资料。",
        "SELF_IDENTITY": "自称：我；人物身份以当前场景已确认信息为准。",
        "PERSONALITY_CORE": "重视眼前证据；遇到疑问先询问，不替他人下结论。",
        "SELF_CLAIM_EXAMPLES": "面对空信封：‘信呢？’这只是声音范例。",
    })
    return {"schema": ACTOR_CARD_SCHEMA, "target": target, "sections": sections,
            "source_refs": [f"characters/{target}.yaml:1", "scene_brief"],
            "design_notes": "DIRECTOR_ONLY：未将信件的秘密变成人物记忆。"}
