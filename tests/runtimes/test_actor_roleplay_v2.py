"""New roleplay invitations, faithful card versions and legacy transaction recovery."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio_engine.public.literary import (
    ACTOR_CARD_SCHEMA, ACTOR_CARD_SECTIONS, LEGACY_ACTOR_CARD_SCHEMA, LEGACY_ACTOR_CARD_SECTIONS,
    CreatorMaterialPlanV1, SceneMaterialRequestV4, parse_actor_character_card, render_actor_character_card,
)
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from literary_engineering_studio.application.actor_card_store import ActorCardStore
from literary_engineering_studio.runtimes.scene_creator_v2_materials import (
    SceneCreatorV2MaterialCoordinator, render_material_invocation, _parse_candidates,
)
from literary_engineering_studio.runtimes.scene_creator_workspace import SceneCreatorWorkspace
from literary_engineering_studio.runtimes.natural_card_source import restore_labelled_card_sections
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
from tests.actor_card_fixtures import actor_card_payload


def legacy_payload():
    card=actor_card_payload()
    card['schema']=LEGACY_ACTOR_CARD_SCHEMA
    card['sections']={key:card['sections'].get(key,'旧版性情的完整原文') for key in LEGACY_ACTOR_CARD_SECTIONS}
    return card


def layers():
    keys=['scene.v2.material.actor','scene.v2.actor.turn','scene.v2.transport.extractor']
    return {key:prompt_layer_spec(key).default_text for key in keys}


class ActorRoleplayV2Tests(unittest.TestCase):
    def request(self):
        return SceneMaterialRequestV4('actor','阿青','PRIVATE_AUTHOR_GOAL','此刻','她问：信在哪里？',
            '阿青，阿婶把空信封放到你面前，问你：信在哪里？',
            character_card=parse_actor_character_card(actor_card_payload(),'阿青'))

    def test_actor_receives_roleplay_stimulus_and_author_purpose_stays_in_record(self):
        request=self.request();call=render_material_invocation(request,[],layers(),scene_id='s1')
        self.assertEqual(call.initialization,render_actor_character_card(layers()['scene.v2.material.actor'],request.character_card))
        self.assertTrue(call.initialization.startswith('【PERSONA_LOAD】'))
        self.assertIn('用自己的声音直接回应来话',call.prompt)
        self.assertIn(request.author_prompt,call.prompt)
        self.assertNotIn('PRIVATE_AUTHOR_GOAL',call.prompt)
        self.assertNotIn('【创作邀请】',call.prompt)
        self.assertNotIn('希望读者感受到',call.prompt)

    def test_other_material_writer_retains_its_literary_invitation(self):
        current=layers();current['scene.v2.material.environment']='地方作家\n{{STYLE_DIRECTION}}'
        request=replace(self.request(),kind='environment',character_card=None,style_direction='浪漫长句')
        call=render_material_invocation(request,[],current,scene_id='s1')
        self.assertIn('【创作邀请】',call.prompt)
        self.assertIn('PRIVATE_AUTHOR_GOAL',call.prompt)
        self.assertIn('浪漫长句',call.initialization)

    def test_legacy_snapshot_keeps_all_sixteen_sections_and_the_original_invitation(self):
        old=Path(__file__).resolve().parents[2]/'tools/prompt-design-desk/history/2026-10-10-actor-repair/scene.v2.material.actor.md'
        current=layers();current.pop('scene.v2.actor.turn');current['scene.v2.material.actor']=old.read_text(encoding='utf-8').strip()
        card=parse_actor_character_card(legacy_payload(),'阿青');request=replace(self.request(),character_card=card)
        call=render_material_invocation(request,[],current,scene_id='old')
        self.assertIn('【PERSONALITY_CORE】',call.initialization)
        self.assertIn('【创作邀请】',call.prompt)
        self.assertEqual(card.to_dict(),legacy_payload())

    def test_explicit_legacy_chat_card_preserves_its_five_extra_sections(self):
        card=parse_actor_character_card(legacy_payload(),'阿青')
        system=render_actor_character_card(layers()['scene.v2.material.actor'],card)
        self.assertEqual(len(card.sections),16)
        self.assertIn('【PERSONALITY_SUMMARY】',system)
        self.assertIn('旧版性情的完整原文',system)

    def test_new_card_preserves_layer_mode_and_speech_pairs_verbatim(self):
        card=actor_card_payload();card['sections']['PERSONA_LOAD']='SELF_CLAIM_AQING\nLANG_ZH_CN_ONLY'
        card['sections']['PRIVATE_BEHAVIOR_MODES']='MODE_1：【爱给窗台封爵】\n- 行为：我敲敲窗台。\n- 台词示例：“侯爷，开门。”'
        source=render_actor_character_card(layers()['scene.v2.material.actor'],parse_actor_character_card(card,'阿青'))
        restored=restore_labelled_card_sections(source,{'card':deepcopy(card)})['card']
        self.assertEqual(restored,card)
        self.assertEqual(len(restored['sections']),11)
        with TemporaryDirectory() as directory:
            process=NaturalOutputProcessor(Path(directory),'extract',lambda *_:json.dumps({'card':card},ensure_ascii=False))
            self.assertEqual(process.process(source,kind='card',context={})['card'],card)

    def test_old_work_card_becomes_reference_until_creator_supplies_new_version(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir();(work/'project.yaml').write_text('title: demo',encoding='utf-8')
            old=ActorCardStore(root/'data').save(work,legacy_payload(),provenance={'author':'old-creator'})
            coordinator=SceneCreatorV2MaterialCoordinator(root/'tx',SceneCreatorWorkspace(work,root/'data'),layers(),scene_id='s1')
            coordinator.save_plan(CreatorMaterialPlanV1(('actor',),'听人物回应'))
            context=coordinator.creator_card_context()
            self.assertEqual(context['work_cards'],[])
            self.assertEqual(context['previous_work_cards'][0]['digest'],old['digest'])
            with self.assertRaisesRegex(ValueError,'十一块'):
                coordinator.execute(replace(self.request(),character_card=None),lambda _:self.fail('must request a new card before invoking'))
            coordinator.execute(self.request(),lambda _:{'candidates':[{'spoken':'信呢？','text':'信呢？我扶住碗。','first_person_action':'我扶住碗。','private_impulse':'','focus':'问'}]})
            saved=ActorCardStore.read(work,'阿青')
            self.assertEqual(saved['card']['schema'],ACTOR_CARD_SCHEMA)
            self.assertTrue((work/'characters/role-cards/history'/(old['digest']+'.json')).is_file())
            self.assertEqual(saved['provenance']['previous_digest'],old['digest'])

    def test_large_actor_fields_are_reported_without_silent_clipping(self):
        response={'candidates':[{'text':'原文','spoken':'字'*1201,'first_person_action':'','focus':'声音'}]}
        with self.assertRaisesRegex(ValueError,'without clipping'):
            _parse_candidates(response,self.request(),'id')

    def test_imported_work_keeps_active_cards_visible_without_a_private_catalog(self):
        from literary_engineering_studio.persistence.character_chats import FileCharacterChatRepository
        with TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir();(work/'project.yaml').write_text('title: imported',encoding='utf-8')
            saved=ActorCardStore(root/'original-studio').save(work,actor_card_payload(),provenance={'author':'creator'})
            fresh=FileCharacterChatRepository(root/'new-studio')
            self.assertEqual(fresh.cards(work)[0]['digest'],saved['digest'])
            self.assertTrue(fresh.cards(work)[0]['work_active'])
            self.assertFalse((root/'new-studio').exists())

    def test_creator_keeps_the_card_version_even_when_card_design_is_already_complete(self):
        from literary_engineering_studio.runtimes.scene_natural_output import validate_extracted_text
        payload={'material_requests':[{'character_card':legacy_payload(),'author_prompt':'阿青，信呢？'}]}
        source=render_actor_character_card(layers()['scene.v2.material.actor'],parse_actor_character_card(legacy_payload(),'阿青'))+'\n阿青，信呢？'
        with self.assertRaisesRegex(ValueError,'current frozen template'):
            validate_extracted_text(source,payload,'creator',{'actor_card_schema':ACTOR_CARD_SCHEMA})
        validate_extracted_text(source,payload,'creator',{'actor_card_schema':LEGACY_ACTOR_CARD_SCHEMA})


if __name__=='__main__':unittest.main()
