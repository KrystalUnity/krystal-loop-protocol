"""Verify retained arithmetic offline, not provider bills or model correctness."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


EXPECTED_GROUPS = {
    'qualification': (2, '0.00061425'),
    'preparation_planning': (5, '0.4271040'),
    'comparison_planning': (6, '0.6174425'),
    'deepseek': (45, '0.287786292'),
    'gemini_original': (78, '1.122118125'),
    'gemini_followup': (205, '6.279447125'),
}
CALL_FIELDS = {
    'id', 'run', 'group', 'role', 'model', 'usage', 'rates_usd_per_million',
    'cost_usd', 'billing_settled', 'status', 'source_sha256', 'settlement_sha256',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def amount(value):
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Invalid monetary value') from exc
    require(number.is_finite() and number >= 0, 'Non-finite or negative monetary value')
    return number


def verify(data, root):
    require(data['schema'] == 'klp.ansible-evidence.v1', 'Unexpected schema')
    calls = data['inference_calls']
    require(len(calls) == len({c['id'] for c in calls}) == 341, 'Missing/duplicate call')
    require(set(data['groups']) == {c['group'] for c in calls} == set(EXPECTED_GROUPS), 'Unexpected groups')
    costs = {}
    for call in calls:
        require(set(call) == CALL_FIELDS, 'Unexpected exported call fields')
        require(call['billing_settled'] is True, 'Unsettled call')
        u, rates = call['usage'], call['rates_usd_per_million']
        require(set(u) == {'input', 'cached', 'write', 'output', 'reasoning'}, 'Usage shape')
        require(set(rates) == {'input', 'cached', 'write', 'output'}, 'Rates shape')
        require(all(type(u[k]) is int and u[k] >= 0 for k in ('input', 'cached', 'write', 'output')), 'Usage count')
        require(u['cached'] + u['write'] <= u['input'], 'Overlapping/excess cache counts')
        require(u['reasoning'] is None or (type(u['reasoning']) is int and 0 <= u['reasoning'] <= u['output']), 'Reasoning subset')
        r = {key: amount(value) for key, value in rates.items()}
        computed = ((u['input'] - u['cached'] - u['write']) * r['input']
                    + u['cached'] * r['cached'] + u['write'] * r['write']
                    + u['output'] * r['output']) / 1_000_000
        require(computed == amount(call['cost_usd']), 'Per-call cost mismatch: ' + call['id'])
        costs[call['id']] = computed
    for group, (count, total) in EXPECTED_GROUPS.items():
        rows = [c for c in calls if c['group'] == group]
        reported = data['groups'][group]
        require(len(rows) == count == reported['calls'], 'Group count mismatch')
        require(sum(costs[c['id']] for c in rows) == amount(total) == amount(reported['cost_usd']), 'Group cost mismatch')
        require(set(reported['roles']) == {c['role'] for c in rows}, 'Role groups mismatch')
        for role, value in reported['roles'].items():
            selected = [c for c in rows if c['role'] == role]
            require(len(selected) == value['calls'], 'Role count mismatch')
            require(sum(costs[c['id']] for c in selected) == amount(value['cost_usd']), 'Role cost mismatch')
    account = data['accounting']
    total = sum(costs.values())
    require(account['included_calls'] == 341, 'Account count mismatch')
    require(total == amount(account['included_api_usd']) == Decimal('8.734512292'), 'Included total mismatch')
    require(amount(account['earlier_other_experiments_usd']) == Decimal('4.444328012'), 'Carry-in changed')
    require(total + amount(account['earlier_other_experiments_usd']) == amount(account['cumulative_api_usd']) == Decimal('13.178840304'), 'Cumulative cost mismatch')
    require(amount(account['cumulative_api_usd']) <= amount(account['experiment_cap_usd']) == Decimal('50'), 'Budget mismatch')
    require(account['reference_plan_reused_not_recharged'] is True, 'Reused plan double charged')
    require(account['subscription_cash'] == 'unavailable_not_zero', 'Missing subscription boundary')
    require(amount(account['hosting_eur_estimate']) == Decimal('0.3366') and account['hosting_invoice_reconciled'] is False, 'Hosting boundary')
    require(any(c['status'] == 'output_limit' for c in calls), 'Lost failed planning attempt')
    require(any(c['status'] == 'failed' and c['settlement_sha256'] for c in calls), 'Lost qualification settlement')
    expected_results = {
        'deepseek': (True, 'PASS', 0, 207, '0.596507542'),
        'gemini_original': (False, None, 0, None, '1.430839375'),
        'gemini_followup': (True, 'PASS', 1, 226, '6.588168375'),
    }
    require(set(data['outcomes']) == set(expected_results), 'Missing outcome')
    for name, (solved, critic, repairs, tests, allocated) in expected_results.items():
        row = data['outcomes'][name]
        require(row['official_solved'] is solved and row['official_reward'] == int(solved), 'Recorded outcome mismatch')
        require(row['official_status'] == ('solved' if solved else 'unsolved'), 'Status mismatch')
        require(row['critic_verdict'] == critic and row['formal_repairs'] == repairs and row['source_tests_passed'] == tests, 'Quality summary mismatch')
        require(row['grading_attempts'] == 1, 'Grading count mismatch')
        require(amount(row['reference_plan_usd']) * 2 == amount(data['groups']['comparison_planning']['cost_usd']), 'Plan allocation mismatch')
        require(amount(data['groups'][name]['cost_usd']) + amount(row['reference_plan_usd']) == amount(row['allocated_workflow_usd']) == amount(allocated), 'Workflow allocation mismatch')
    inputs = json.loads((root / 'inputs.json').read_text())
    require(hashlib.sha256((root / 'frozen-plan.md').read_bytes()).hexdigest() == inputs['frozen_plan_sha256'], 'Frozen plan changed')
    protocol = data['semiotic_protocol']
    require(protocol['no_adapter_control'] is False and protocol['incremental_savings_percentage'] is None, 'Invented Semiotic saving')
    stages = protocol['stages']['gemini_followup']
    require({r['stage'] for r in stages} == {'worker-0', 'critic-0', 'worker-1', 'critic-1'} and len(stages) == 4, 'Missing dispatch')
    require(sum(r['transport_bytes'] for r in stages) == 3648, 'Transport bytes mismatch')
    for row in stages:
        require(row['state'] == 'completed' and row['model_coordination_calls'] == 0, 'Dispatch outcome mismatch')
        require(row['transport_reads'] == 1 and row['counters'] == {'scan_calls': 1, 'event_wait_calls': 0, 'poll_wait_calls': 0, 'execute_calls': 1}, 'Dispatch counters mismatch')
    return {'calls': len(calls), 'included_api_usd': str(total), 'cumulative_api_usd': account['cumulative_api_usd']}


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    result = verify(json.loads((root / 'receipts.json').read_text()), root)
    print(f"Verified {result['calls']} sanitized call receipts; Ansible API USD {result['included_api_usd']}.")
    print('DeepSeek workflow USD 0.596507542; Gemini follow-up USD 6.588168375, each including the same reference plan share.')
    print('Original Gemini stop and failed preparation retained; reused planning is not charged twice.')
    print('Four follow-up Semiotic Protocol dispatches; zero model coordination calls; no incremental savings claim.')
    print('Offline arithmetic only. Recorded outcomes are not freshly executed tests or authenticated provider invoices.')
