"""A user-owned roleplay session with facts and history separate from scene creation."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import threading
from typing import Any, Callable
from uuid import uuid4

from literary_engineering_studio_engine.public.literary import (
    ACTOR_CARD_SECTIONS, parse_actor_character_card, render_actor_character_card,
)
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from .character_chat_ports import CharacterChatArchivePort, CharacterChatRepositoryPort, CharacterConversationPort


class CharacterChatService:
    def __init__(self, repository: CharacterChatRepositoryPort, conversation: CharacterConversationPort,
                 archive: CharacterChatArchivePort, prompt_resolver: Callable | None = None):
        self.repository, self.conversation, self.archive = repository, conversation, archive
        self.prompt_resolver = prompt_resolver
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def setup(self, project_root: Path) -> dict[str, Any]:
        root = _work(project_root)
        spec = prompt_layer_spec("scene.v2.material.actor")
        return {"sections": list(ACTOR_CARD_SECTIONS), "system_template": spec.default_text,
                "cards": self.repository.cards(root), "sessions": self.repository.list(root)}

    def archive_list(self, project_root: Path, *, prefix="", cursor=0):
        return self.archive.list(_work(project_root), prefix=prefix, cursor=cursor)

    def archive_read(self, project_root: Path, path: str, *, offset=0):
        return self.archive.read(_work(project_root), path, offset=offset)

    def create(self, project_root: Path, *, target: str, card: dict[str, Any],
               attachments: list[dict[str, Any]], context: str = "") -> dict[str, Any]:
        root = _work(project_root)
        parsed = parse_actor_character_card(card, target)
        if len(context) > 16000:
            raise ValueError("独立场景上下文过长，请缩小到本轮相关内容。")
        for item in attachments:
            if item.get("knowledge") != "known":
                raise ValueError("角色对话请选择角色可知资料。")
        frozen = self.archive.freeze(root, attachments)
        template = (self.prompt_resolver("scene.v2.material.actor", root) if self.prompt_resolver
                    else prompt_layer_spec("scene.v2.material.actor").default_text)
        system = render_actor_character_card(template, parsed)
        now = _now()
        session = {"schema": "arcvellum/character-chat/v1", "session_id": str(uuid4()),
            "project_root": str(root), "target": target, "created_at": now, "updated_at": now,
            "card": parsed.to_dict(), "system_prompt": system,
            "system_sha256": sha256(system.encode("utf-8")).hexdigest(),
            "known_archive": frozen, "context": context, "turns": []}
        self.repository.save(root, session)
        return session

    def read(self, project_root: Path, session_id: str) -> dict[str, Any]:
        return self.repository.read(_work(project_root), session_id)

    def draft_card(self, project_root: Path, *, target: str, attachments: list[dict[str, Any]],
                   context: str = "") -> dict[str, Any]:
        root = _work(project_root)
        if not target.strip() or len(context) > 16000:
            raise ValueError("请填写人物名与本段对话的场景。")
        if any(item.get("knowledge") != "known" for item in attachments):
            raise ValueError("角色对话请选择角色可知资料。")
        frozen = self.archive.freeze(root, attachments)
        spec = prompt_layer_spec("scene.v2.creator.actor-card")
        guidance = self.prompt_resolver(spec.layer_id, root) if self.prompt_resolver else spec.default_text
        draft = self.conversation.draft_card(root, guidance=guidance, context={
            "target": target, "context": context, "known_archive": frozen,
            "template": prompt_layer_spec("scene.v2.material.actor").default_text})
        card = dict(draft["card"])
        card["source_refs"] = [item["path"] for item in frozen] or card.get("source_refs") or ["用户独立对话设定"]
        return {"card": parse_actor_character_card(card, target).to_dict(), "draft_text": draft["draft_text"]}

    def ask(self, project_root: Path, session_id: str, message: str, *, timeout=300) -> dict[str, Any]:
        root = _work(project_root)
        if not message.strip() or len(message) > 12000:
            raise ValueError("请输入一条有效的对话消息。")
        with self._guard:
            lock = self._locks.setdefault(str(root) + ":" + session_id, threading.Lock())
        if not lock.acquire(blocking=False):
            raise ValueError("这段对话仍在等待角色回应。")
        try:
            session = self.repository.read(root, session_id)
            if len(session["turns"]) >= 16:
                raise ValueError("本段对话已达上下文容量，可带新的上下文开始另一段对话。")
            prompt = _current_prompt(session, message)
            history = [(item["prompt"], item["answer"]) for item in session["turns"]]
            answer = self.conversation.reply(root, system=session["system_prompt"], history=history,
                                             prompt=prompt, timeout=max(10, min(900, timeout)))
            if not answer.strip():
                raise RuntimeError("角色本轮尚未返回文字。")
            session["turns"].append({"message": message, "prompt": prompt, "answer": answer, "at": _now()})
            session["updated_at"] = _now()
            self.repository.save(root, session)
            return session
        finally:
            lock.release()


def _current_prompt(session: dict[str, Any], message: str) -> str:
    if session["turns"]:
        return f"独立对话 {session['session_id']}\n\n" + message
    return (f"独立对话 {session['session_id']}\n\n当前场景：\n{session['context']}\n\n"
            + "角色已知资料：\n" + json.dumps(session["known_archive"], ensure_ascii=False)
            + "\n\n对话消息：\n" + message)


def _work(project_root: Path) -> Path:
    root = project_root.expanduser().resolve()
    if not (root / "project.yaml").is_file():
        raise ValueError("请选择一部已初始化的作品。")
    return root


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

