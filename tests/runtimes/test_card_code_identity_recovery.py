import unittest
from literary_engineering_studio_engine.public.literary import ACTOR_CARD_SECTIONS
from literary_engineering_studio.runtimes.natural_local_delivery import local_cards


def source(name, identity):
    return '### 角色卡 · ' + name + '\n\n' + '\n\n'.join(
        '【' + field + '】\n' + (identity if field == 'CORE_IDENTITY' else field + ' 的完整原文。')
        for field in ACTOR_CARD_SECTIONS)


class CardCodeIdentityRecoveryTests(unittest.TestCase):
    def test_explicit_card_heading_routes_an_independent_code_without_editing_sections(self):
        text = source('陶婶', '代号：T_SHEN\n职业：食堂主人。')
        cards = local_cards(text, {'eligible_actors':['陶婶','许钉']})
        self.assertEqual(cards['陶婶']['sections']['CORE_IDENTITY'],'代号：T_SHEN\n职业：食堂主人。')
        self.assertEqual(set(cards['陶婶']['sections']),set(ACTOR_CARD_SECTIONS))

    def test_conflicting_explicit_name_and_heading_is_not_recovered(self):
        text = source('陶婶', '姓名：许钉\n代号：X_DING')
        self.assertEqual(local_cards(text, {'eligible_actors':['陶婶','许钉']}),{})

    def test_unknown_heading_and_code_does_not_guess_from_another_person_mention(self):
        text = source('未知人', '代号：UNKNOWN\n职业：给陶婶送货。')
        self.assertEqual(local_cards(text, {'eligible_actors':['陶婶','许钉']}),{})

    def test_repeated_identity_source_is_ambiguous(self):
        text=source('陶婶','代号：T_SHEN')+'\n'+source('许钉','代号：T_SHEN')
        self.assertEqual(local_cards(text, {'eligible_actors':['陶婶','许钉']}),{})


if __name__=='__main__':
    unittest.main()
