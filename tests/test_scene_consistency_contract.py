from copy import deepcopy
import unittest
from literary_engineering_studio_engine.public.literary import (
    delta_inventory, validate_creator_consistency, validate_current_review,
    SceneConsistencyError, CONSISTENCY_CATEGORIES, current_fact_alerts,
)


def creator():
    return {'prose':'许钉把桌子修稳了。', 'scene_delta':{}, 'material_requests':[],
            'consistency_record':{'canon_change':False,'no_canon_change_reason':'没有新增世界规则。',
                'facts':[],'no_persistent_facts_reason':'仅重述原有状态。'}}


def review():
    return {'decision':'pass','summary':'本稿事实清楚。','strengths':[], 'major_issues':[],
        'optional_explorations':[],'issue_progress':[], 'consistency_checks':[
            {'category':category,'status':'clear','evidence':[],'note':'核对当前稿，没有该类冲突。'}
            for category in CONSISTENCY_CATEGORIES]}


class SceneConsistencyContractTests(unittest.TestCase):
    def test_unstructured_scene_delta_is_a_repairable_author_error(self):
        row=creator();row['scene_delta']=[{'target_ref':'canon/facts.json','summary':'新事实'}]
        with self.assertRaises(SceneConsistencyError) as caught:
            validate_creator_consistency(row)
        self.assertEqual(caught.exception.fields,('/scene_delta',))
        row['scene_delta']={'canon_candidates':['bad proposal']}
        with self.assertRaises(SceneConsistencyError) as caught:
            validate_creator_consistency(row)
        self.assertEqual(caught.exception.fields,('/scene_delta',))

    def test_relative_year_alert_cannot_be_silently_cleared(self):
        body='碗底是去年冬天崩出来的坑，三年了没变形回去。'
        self.assertEqual(len(current_fact_alerts(body)),1)
        row=review()
        with self.assertRaises(SceneConsistencyError): validate_current_review(row,body)
        row['decision']='escalate';row['consistency_checks'][0]['status']='uncertain'
        validate_current_review(row,body)

    def test_time_alert_excludes_speech_separate_events_and_explicit_time_jump(self):
        for body in ('“去年崩出来的坑，三年了没变形回去。”他胡说。',
                     '去年磕坏了碗。桌子三年了没修。',
                     '去年写在日记里。此后又过了三年，坑仍没有修。',
                     '去年碗摔坏了，后来过了三年还没有修。',
                     '去年崩出的坑，一年了没修。'):
            self.assertEqual(current_fact_alerts(body),[],body)

    def test_unsubmitted_prior_change_cannot_vanish_as_already_recorded(self):
        prior={'continuity_changes':[{'target_ref':'workflow/continuity/current.json',
            'summary':'桌子已修稳','evidence':'桌子不晃了。','operation':'update'}]}
        row=creator();row['consistency_record']['prior_delta_dispositions']=[{
            'proposal_id':delta_inventory(prior)[0]['proposal_id'],'action':'retain','reason':'本稿仍成立'}]
        with self.assertRaises(SceneConsistencyError) as caught: validate_creator_consistency(row,prior)
        self.assertIn('/scene_delta',caught.exception.fields)
        row['scene_delta']=deepcopy(prior)
        validate_creator_consistency(row,prior)

    def test_withdrawal_is_an_explicit_author_decision_not_automatic_merge(self):
        prior={'promise_updates':[{'target_ref':'scenes/s1.yaml','summary':'明日吃面'}]}
        row=creator();row['consistency_record']['prior_delta_dispositions']=[{
            'proposal_id':delta_inventory(prior)[0]['proposal_id'],'action':'withdraw','reason':'本稿已删除这项约定'}]
        validate_creator_consistency(row,prior)
        self.assertEqual(row['scene_delta'],{})

    def test_all_prior_proposals_must_be_accounted_for(self):
        prior={'character_changes':[{'target_ref':'characters/p.yaml','summary':'愿意留下'}]}
        row=creator();row['consistency_record']['prior_delta_dispositions']=[]
        with self.assertRaises(SceneConsistencyError): validate_creator_consistency(row,prior)

    def test_new_durable_fact_needs_an_actual_delta_proposal(self):
        row=creator();row['consistency_record']['facts']=[{'subject':'桌子','predicate':'状态','value':'修稳',
            'evidence':row['prose'],'source_state':'new','durable':True,'delta_group':'continuity_changes',
            'delta_target':'workflow/continuity/current.json','delta_summary':'桌子修稳'}]
        with self.assertRaises(SceneConsistencyError): validate_creator_consistency(row)
        row['scene_delta']['continuity_changes']=[{'target_ref':'workflow/continuity/current.json','summary':'桌子修稳'}]
        validate_creator_consistency(row)

    def test_false_canon_classification_requires_reason_and_no_canon_proposal(self):
        row=creator();row['consistency_record']['no_canon_change_reason']=''
        with self.assertRaises(SceneConsistencyError): validate_creator_consistency(row)
        row['consistency_record']['canon_change']=True
        with self.assertRaises(SceneConsistencyError): validate_creator_consistency(row)
        row['scene_delta']['canon_candidates']=[{'target_ref':'canon/facts.json','summary':'新规矩'}]
        row['consistency_record']['facts']=[{'subject':'规则','predicate':'状态','value':'新规矩',
            'evidence':row['prose'],'source_state':'new','durable':True,
            'delta_group':'canon_candidates','delta_target':'canon/facts.json','delta_summary':'新规矩'}]
        validate_creator_consistency(row)

    def test_exact_link_diagnostic_identifies_punctuation_without_relaxing_contract(self):
        row=creator();row['scene_delta']['continuity_changes']=[{
            'target_ref':'workflow/continuity/current.json','summary':'桌子修稳。'}]
        fact={'subject':'桌子','predicate':'状态','value':'修稳','evidence':row['prose'],
              'source_state':'new','durable':True,'delta_group':'continuity_changes',
              'delta_target':'workflow/continuity/current.json','delta_summary':'桌子修稳'}
        row['consistency_record']['facts']=[fact]
        with self.assertRaises(SceneConsistencyError) as caught:
            validate_creator_consistency(row)
        message=str(caught.exception)
        self.assertIn('"delta_summary": "桌子修稳"',message)
        self.assertIn('"summary": "桌子修稳。"',message)
        self.assertEqual(caught.exception.fields,('/consistency_record','/scene_delta'))
        fact['delta_summary']='桌子修稳。'
        validate_creator_consistency(row)

    def test_unlinked_canon_diagnostic_names_proposal_and_count(self):
        row=creator();row['consistency_record']['canon_change']=True
        row['scene_delta']['canon_candidates']=[{'target_ref':'canon/facts.json','summary':'桌腿短一寸'}]
        with self.assertRaises(SceneConsistencyError) as caught:
            validate_creator_consistency(row)
        self.assertIn('"summary": "桌腿短一寸"',str(caught.exception))
        self.assertIn('持续事实数=0',str(caught.exception))

    def test_canon_proposal_cannot_merge_multiple_durable_details(self):
        row=creator();row['consistency_record']['canon_change']=True
        summary='车站明天停；桌腿短一寸；碗架存两只碗'
        row['scene_delta']['canon_candidates']=[{'target_ref':'canon/facts.json','summary':summary}]
        row['consistency_record']['facts']=[{'subject':'车站','predicate':'停运','value':'明天',
            'evidence':row['prose'],'source_state':'new','durable':True,
            'delta_group':'canon_candidates','delta_target':'canon/facts.json','delta_summary':summary}]
        with self.assertRaises(SceneConsistencyError) as caught: validate_creator_consistency(row)
        self.assertIn('/scene_delta',caught.exception.fields)

    def test_each_canon_proposal_needs_one_linked_fact(self):
        row=creator();row['consistency_record']['canon_change']=True
        row['scene_delta']['canon_candidates']=[{'target_ref':'canon/facts.json','summary':'桌腿短一寸'}]
        with self.assertRaises(SceneConsistencyError): validate_creator_consistency(row)
        row['consistency_record']['facts']=[{'subject':'桌腿','predicate':'长度','value':'短一寸',
            'evidence':row['prose'],'source_state':'new','durable':True,
            'delta_group':'canon_candidates','delta_target':'canon/facts.json','delta_summary':'桌腿短一寸'}]
        validate_creator_consistency(row)

    def test_stale_problem_cannot_survive_by_attaching_a_replacement_quote(self):
        body='他站起来，手伸到碗下面，端起来，放回桌边。'
        row=review();row['decision']='revise';row['major_issues']=[{'title':'端碗路径',
            'evidence':body,'problem_excerpt':'走到灶台边','direction':'删去走到灶台边'}]
        with self.assertRaises(SceneConsistencyError) as caught: validate_current_review(row,body)
        self.assertIn('/major_issues/0',caught.exception.fields)
        self.assertIn('/decision',caught.exception.fields)
        self.assertNotIn('/major_issues/0/evidence',caught.exception.fields)

    def test_current_problem_excerpt_must_be_in_its_own_evidence_not_elsewhere(self):
        first='他走到灶台边还碗。';last='他在桌边直接端起汤碗。';body=first+'\n\n'+last
        row=review();row['decision']='revise';row['major_issues']=[{'evidence':last,'problem_excerpt':'走到灶台边'}]
        with self.assertRaises(SceneConsistencyError): validate_current_review(row,body)

    def test_consistency_findings_cannot_disappear_into_a_pass_verdict(self):
        body='去年冬天磕坏的碗，三年了还没修。';row=review()
        row['consistency_checks'][0].update(status='issue',evidence=[body])
        with self.assertRaises(SceneConsistencyError): validate_current_review(row,body)

    def test_uncertain_facts_require_escalation_instead_of_a_false_pass(self):
        row=review();row['consistency_checks'][0]['status']='uncertain'
        with self.assertRaises(SceneConsistencyError): validate_current_review(row,'正文')
        row['decision']='escalate';validate_current_review(row,'正文')
