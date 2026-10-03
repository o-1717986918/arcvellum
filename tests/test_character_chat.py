"""Separate facts, cards and history never touch a scene creator transaction."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from literary_engineering_studio.application.character_chat import CharacterChatService
from literary_engineering_studio.persistence.character_chats import FileCharacterChatRepository
from literary_engineering_studio.infrastructure.character_chat import CharacterChatArchiveAdapter
from tests.actor_card_fixtures import actor_card_payload

class Conversation:
    def __init__(self):
        self.calls = []
        self.fail = False
    def reply(self, root, **kwargs):
        self.calls.append(kwargs)
        if self.fail: raise RuntimeError("temporarily unavailable")
        return "我把信封翻了过来。你什么时候看见它的？"
    def draft_card(self, root, **kwargs):
        self.calls.append(kwargs)
        return {"card":actor_card_payload(), "draft_text":"完整的自然角色卡"}

class CharacterChatTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/"work"
        self.root.mkdir()
        (self.root/"project.yaml").write_text("title: 信\n",encoding="utf-8")
        (self.root/"known.md").write_text("我看见了空信封。\n秘密另有来源。",encoding="utf-8")
        self.data=Path(temp.name)/"data"
        self.conversation=Conversation()
        self.service=CharacterChatService(FileCharacterChatRepository(self.data),self.conversation,
                                         CharacterChatArchiveAdapter(self.data))
        self.attachment={"path":"known.md","start_line":1,"end_line":1,"knowledge":"known"}

    def create(self):
        return self.service.create(self.root,target="阿青",card=actor_card_payload(),
            attachments=[self.attachment],context="你坐在雨停后的窗边。")

    def test_facts_frozen_history_restored_and_scene_transactions_untouched(self):
        transaction=self.data/"scene-transactions"/"main"
        transaction.mkdir(parents=True)
        sentinel=transaction/"history.json"
        sentinel.write_text('{"main":"original"}',encoding="utf-8")
        first=self.create()
        second=self.create()
        (self.root/"known.md").write_text("后来发现了另一封信。",encoding="utf-8")
        updated=self.service.ask(self.root,first["session_id"],"信还在吗？")
        self.assertEqual(len(updated["turns"]),1)
        self.assertIn("我看见了空信封",self.conversation.calls[0]["prompt"])
        self.assertNotIn("秘密",self.conversation.calls[0]["prompt"])
        self.assertTrue(self.conversation.calls[0]["system"].startswith("【PERSONA_LOAD】"))
        self.assertEqual(self.service.read(self.root,second["session_id"])["turns"],[])
        self.service.ask(self.root,first["session_id"],"你记得我问过什么？")
        self.assertEqual(len(self.conversation.calls[1]["history"]),1)
        self.assertEqual(sentinel.read_text(encoding="utf-8"),'{"main":"original"}')

    def test_failure_and_invalid_mount_do_not_save_turn(self):
        first=self.create()
        self.conversation.fail=True
        with self.assertRaises(RuntimeError):
            self.service.ask(self.root,first["session_id"],"你好")
        self.assertEqual(self.service.read(self.root,first["session_id"])["turns"],[])
        with self.assertRaises(ValueError):
            self.service.create(self.root,target="阿青",card=actor_card_payload(),
                attachments=[{"path":"../outside","knowledge":"known"}])
        with self.assertRaises(ValueError):
            self.service.create(self.root,target="阿青",card=actor_card_payload(),
                attachments=[{"path":"known.md","knowledge":"reference"}])
        with self.assertRaises(ValueError):
            self.service.read(self.root,"../../main")

    def test_draft_card_uses_only_current_dialogue_context(self):
        result=self.service.draft_card(self.root,target="阿青",attachments=[self.attachment],context="独立场景")
        self.assertEqual(result["card"]["source_refs"],["known.md"])
        self.assertEqual(self.conversation.calls[0]["context"]["context"],"独立场景")
        self.assertEqual(self.service.setup(self.root)["sessions"],[])

if __name__=="__main__": unittest.main()

