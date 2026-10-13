import unittest
from literary_engineering_studio.runtime.usage_accounting import summarize_usage_events, public_price_estimate
from literary_engineering_studio.runtime.call_purpose import purpose_from_envelope, purpose_thinking


class UsageAccountingTests(unittest.TestCase):
    def test_duplicate_delivery_does_not_double_tokens_or_output_reasoning(self):
        data={'usage_id':'arcvellum-conversation-one','provider':'deepseek','model':'deepseek-v4-flash',
              'usage':{'input':100,'cache_read':200,'output':50,'reasoning':30,'total_tokens':350},'cost_usd':.1}
        events=[{'event':'usage.updated','at':'2026-10-11T00:00:00Z','data':data,'event_id':str(i)} for i in range(2)]
        result=summarize_usage_events(events)
        self.assertEqual(result['total_tokens'],350)
        self.assertEqual(result['updates'],1)
        self.assertAlmostEqual(result['public_estimate_cny'],.000304)
        self.assertIsNone(result['actual_charge'])

    def test_logical_turns_http_retries_and_unknown_usage_are_distinct(self):
        events=[{'event':'runner.provider.request.started','data':{'model_request_id':'one'}},
                *[{'event':'runner.http.attempt.started','data':{'http_attempt_id':str(i)}} for i in range(2)],
                {'event':'usage.updated','data':{'usage_id':'arcvellum-conversation-failed','usage_available':False,'cost_usd':0}}]
        result=summarize_usage_events(events)
        self.assertEqual(result['recorded_model_turns'],1)
        self.assertEqual(result['observed_http_attempts'],2)
        self.assertEqual(result['unknown_usage_updates'],1)
        self.assertEqual(result['unknown_catalog_cost_updates'],1)

    def test_unobserved_http_attempts_are_unknown_not_zero(self):
        self.assertIsNone(summarize_usage_events([])['observed_http_attempts'])

    def test_stage_is_explicit_and_record_repairs_disable_thinking(self):
        purpose=purpose_from_envelope('{"call_purpose":"record-repair","prompt":"任意正文"}','worker')
        self.assertEqual(purpose_thinking(purpose,'worker',{'thinking':'low'}),'off')
        with self.assertRaises(ValueError):purpose_from_envelope('{"call_purpose":"typo"}','worker')

    def test_unknown_model_price_is_not_fabricated(self):
        self.assertIsNone(public_price_estimate({'model':'other/model','usage':{'total_tokens':1}},'2026-10-11T00:00:00Z'))
