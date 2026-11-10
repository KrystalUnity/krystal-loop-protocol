"""Offline integrity and arithmetic controls; no model or benchmark execution."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ansible_evidence_verify', ROOT / 'verify.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReceiptChecks(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'receipts.json').read_text())

    def reject(self, change):
        changed = copy.deepcopy(self.data)
        change(changed)
        with self.assertRaises(ValueError):
            module.verify(changed, ROOT)

    def test_recorded_packet_passes(self):
        result = module.verify(self.data, ROOT)
        self.assertEqual(result['calls'], 341)
        self.assertEqual(result['included_api_usd'], '8.734512292')

    def test_missing_failed_call_rejected(self):
        self.reject(lambda d: d['inference_calls'].pop(0))

    def test_duplicate_id_rejected(self):
        self.reject(lambda d: d['inference_calls'][1].update(id=d['inference_calls'][0]['id']))

    def test_wrong_cost_rejected(self):
        self.reject(lambda d: d['inference_calls'][0].update(cost_usd='0'))

    def test_unsettled_charge_rejected(self):
        self.reject(lambda d: d['inference_calls'][0].update(billing_settled=False))

    def test_bad_cache_count_rejected(self):
        self.reject(lambda d: d['inference_calls'][0]['usage'].update(cached=10**12))

    def test_nan_rate_rejected(self):
        self.reject(lambda d: d['inference_calls'][0]['rates_usd_per_million'].update(input='NaN'))

    def test_plan_double_charge_rejected(self):
        self.reject(lambda d: d['accounting'].update(cumulative_api_usd='13.487561554'))

    def test_original_gemini_stop_cannot_be_called_solved(self):
        self.reject(lambda d: d['outcomes']['gemini_original'].update(official_solved=True))

    def test_quality_evidence_cannot_be_relabelled(self):
        self.reject(lambda d: d['outcomes']['gemini_followup'].update(formal_repairs=0))

    def test_unmeasured_semiotic_savings_rejected(self):
        self.reject(lambda d: d['semiotic_protocol'].update(incremental_savings_percentage=75))

    def test_group_cost_rejected(self):
        self.reject(lambda d: d['groups']['deepseek'].update(cost_usd='0.01'))

    def test_unknown_field_rejected(self):
        self.reject(lambda d: d['inference_calls'][0].update(raw_response='not allowed'))


if __name__ == '__main__':
    unittest.main()
