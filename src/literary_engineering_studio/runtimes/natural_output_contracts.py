"""Versioned source-only transport task fields."""
from literary_engineering_studio_engine.public.literary import ACTOR_CARD_SCHEMA, ACTOR_CARD_SECTIONS

_CREATOR_CONTRACT = {
    "material_plan": {"required_kinds": ["one or more of the five kind IDs"], "reason": "creator reason"},
    "material_requests": [{"kind": "actor/environment/character-description/event-narration/scene-description",
        "target": "actor: exact name from context.eligible_actors or briefing participants; other kinds: the creator's chosen commission subject",
        "purpose": "purpose", "scene_moment": "moment", "cue": "stimulus",
        "author_prompt": "verbatim contiguous creator invitation from source_text",
        "working_context": "verbatim contiguous creator note describing this call's current context, or empty",
        "style_direction": "verbatim contiguous style from source_text, or empty when unstated",
        "need_evidence": {"gap": "creator stated unresolved literary gap, verbatim",
            "why_existing_insufficient": "creator stated insufficiency or reason for first consultation, verbatim",
            "expected_use": "creator stated prose landing or indirect use, verbatim",
            "reviewed_candidate_ids": ["existing IDs explicitly checked, empty before first materials"],
            "existing_material_evidence": {"checked candidate ID": "verbatim candidate excerpt cited by creator"},
            "mount_reasons": {"archive:0 or material:0": "creator stated reason for this selected attachment, verbatim"}},
        "archive_attachments": [{"path": "relative archive path", "start_line": None,
                                "end_line": None,
                                "knowledge": "known or reference for actor; empty for other kinds"}],
        "material_attachments": [{"candidate_id": "an explicitly selected candidate ID from this transaction",
                                  "start_char": None, "end_char": None}],
        "character_card": "null when source has no card; otherwise extract the complete versioned card verbatim with schema, target, sections and source_refs"}],
    "prose": "exact contiguous source text of completed body, or empty during preparation",
    "decision_summary": "creator's working intention and decisions",
    "creative_intent": {"reader_experience": "intended experience", "reader_knows": "intended understanding",
                        "reader_misreads": "intended ambiguity", "withheld": "later revelation"},
    "scene_delta": {"character_changes": [], "canon_candidates": [], "continuity_changes": [],
        "promise_updates": [], "reader_question_updates": [], "next_handoff": [], "new_asset_candidates": []},
    "material_decisions": [{"candidate_id": "existing ID", "decision": "use/adapt/discard/defer", "reason": "creator's reason",
        "source_excerpt": "verbatim selected source fragment when stated; otherwise empty",
        "prose_excerpt": "verbatim current prose landing when stated; otherwise empty",
        "prose_location": "author stated paragraph or structural position, otherwise empty",
        "indirect_use": "author stated understanding/structure/voice use, otherwise empty"}],
    "editor_focus": [{"issue": "author requested local editing question", "excerpt": "verbatim current prose excerpt",
        "operation": "trailing-whitespace only when explicitly requested in source_text; otherwise empty"}],
}
_MATERIAL_CONTRACT = {
    "candidates": [{"text": "exact contiguous literary source text", "focus": "literary focus",
        "spoken": "exact source speech for actor", "first_person_action": "exact actor action",
        "private_impulse": "verbatim private impulse when explicitly present in source_text, otherwise empty",
        "basis": "event only: confirmed/attributed/proposed",
        "source_note": "event only: source or author's proposal note"}],
    "no_material_reason": "reason if creator offers no material",
}
_REVIEW_CONTRACT = {
    "editor_focus": [{"issue": "explicit local-language editing question, otherwise absent",
                      "excerpt": "verbatim current prose excerpt",
                      "operation": "trailing-whitespace only when explicitly requested in source_text; otherwise empty"}],
    "decision": "pass/revise/escalate", "summary": "editor's judgment",
    "strengths": [{"claim": "literary quality already working", "evidence": "verbatim excerpt from context.prose"}],
    "major_issues": [{"title": "reading problem", "evidence": "verbatim excerpt from context.prose",
        "reader_effect": "what the reader loses", "direction": "repair exploration",
        "prior_issue_id": "matching open issue ID or empty when newly observed"}],
    "optional_explorations": [{"question": "aesthetic possibility", "evidence": "verbatim current passage or empty",
        "direction": "possible reader experience"}],
    "issue_progress": [{"issue_id": "open issue ID from context.review_continuity",
        "status": "resolved/persists/changed/uncertain",
        "evidence": "verbatim current passage when it supports the status, otherwise empty"}],
    "revision_instructions": [], "evidence": [],
}
CONTRACTS = {"creator": _CREATOR_CONTRACT, "material": _MATERIAL_CONTRACT, "review": _REVIEW_CONTRACT}
CONTRACTS['material-plan'] = {'material_plan': _CREATOR_CONTRACT['material_plan']}
CONTRACTS["tone"] = {"edits": [{"rule_id": "1 through 11", "before": "exact original fragment",
    "after": "verbatim proposed replacement", "reason": "editor's stated literary reason"}],
    "summary": "editor's summary; empty edits when text is retained"}
CONTRACTS["card"] = {"card": {"schema": ACTOR_CARD_SCHEMA, "target": "target from context",
    "sections": {key: "verbatim card section" for key in ACTOR_CARD_SECTIONS}, "source_refs": [], "notes": ""}}
CONTRACTS["style-choice"] = {"preset_id": "one active ID explicitly selected in source_text",
    "reference_ids": ["IDs explicitly selected in source_text"],
    "literary_mode": "verbatim literary strategy from source_text", "reason": "verbatim selection reason from source_text"}
_PLANNED_UNIT = {"name": "unit title", "function": "literary purpose", "obligation": "reading experience",
    "participants": ["registered names; empty for narration"], "conflict": "stated conflict or empty",
    "information_release": "world/knowledge introduced or empty", "consequence": "experience or state change",
    "setup_payoff_role": "stated role or empty", "rhythm_role": "setup/escalation/climax/payoff/aftermath/bridge/transition",
    "narrative_strategy": "voice, focalization, time and scale", "story_time": "story time", "length_weight": 1}
CONTRACTS["planning-window"] = {"scenes": [_PLANNED_UNIT]}
CONTRACTS["planning-initial"] = {"premise": "premise", "central_question": "question", "ending_choice": "conditional closure",
    "narrative_design": {}, "volume_obligations": [], "volume_length_weights": [],
    "chapters": [{"title": "title", "dramatic_turn": "world/person/reading turn", "obligation": "reading experience",
                  "reader_question": "question or empty", "literary_task": "chapter literary significance", "length_weight": 1}],
    "first_window": [_PLANNED_UNIT], "characters": [{"name": "name", "role": "role", "importance": "major/secondary/cameo",
        "background": "history", "desire": "desire"}], "world_facts": []}
CONTRACTS["planning-future"] = {"narrative_design": {}, "chapters": [{"chapter_id": "requested chapter ID",
    "title": "title", "literary_task": "literary significance", "length_weight": "explicit chapter weight or 1", "obligation": "reading experience",
    "dramatic_turn": "world/person/reading turn", "reader_question": "question or empty",
    "irreversible_change": "only if explicitly stated, otherwise empty", "scenes": [_PLANNED_UNIT]}]}
CONTRACTS["planning-future-outline"] = {"narrative_design": {}, "chapters": [{"chapter_id": "requested ID",
    "title": "title", "literary_task": "reading experience", "length_weight": 1,
    "future_scene_count": "explicit number of future units", "unit_outline": "verbatim concise unit directory",
    "obligation": "reading task", "dramatic_turn": "literary turn", "reader_question": "reader curiosity"}]}
CONTRACTS["planning-future-chapter"] = {"chapter": CONTRACTS["planning-future"]["chapters"][0]}
_CHANGE = {"target_ref": "reference in context.briefing.scene_brief.source_refs; narrative future handoffs use next_handoff",
           "summary": "stated change",
           "evidence": "verbatim source passage", "operation": "update/create", "attributes": {}}
for _key in _CREATOR_CONTRACT["scene_delta"]:
    if _key != "next_handoff":
        _CREATOR_CONTRACT["scene_delta"][_key] = [_CHANGE]
