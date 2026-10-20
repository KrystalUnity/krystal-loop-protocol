"""Recompute recorded coordination usage and costs offline; no provider calls."""
import json
from decimal import Decimal
from pathlib import Path


def verify():
    data = json.loads(
        Path(__file__).with_name("receipts.json").read_text(),
        parse_float=Decimal,
    )
    calls = data["inference_calls"]
    expected_roles = {
        "worker", "critic", "A-clean", "B-clean",
        "A-duplicate", "A-stale", "A-restart",
    }
    assert len(calls) == len({c["id"] for c in calls}) == 7
    assert {c["role"] for c in calls} == expected_roles
    costs = {}
    for call in calls:
        assert call["status"] == "completed" and call["http_status"] == 200
        raw, cached, output, write = map(Decimal, call["rates"])
        uncached = (
            call["input_tokens"] - call["cached_input_tokens"]
            - call["cache_write_tokens"]
        )
        assert uncached >= 0
        cost = (
            uncached * raw + call["cached_input_tokens"] * cached
            + call["cache_write_tokens"] * write + call["output_tokens"] * output
        ) / 1_000_000
        assert cost == call["charge_or_reservation_usd"]
        costs[call["role"]] = cost
    groups = {
        "A": [c for c in calls if c["role"].startswith("A-")],
        "B": [c for c in calls if c["role"].startswith("B-")],
        "shared": [c for c in calls if c["role"] in {"worker", "critic"}],
    }
    for name, group in groups.items():
        expected = data["totals"][name]
        assert len(group) == expected["calls"]
        for field in (
            "input_tokens", "cached_input_tokens", "cache_write_tokens",
            "output_tokens", "prompt_bytes",
        ):
            assert sum(c[field] for c in group) == expected[field]
        assert sum(costs[c["role"]] for c in group) == expected["usd"]
    assert sum(costs.values()) == data["totals"]["total_api_usd"]
    share = data["totals"]["shared"]["usd"] / 2
    for arm in ("A", "B"):
        row = data["totals"][arm]
        assert row["usd"] + share == row["with_equal_shared_usd"]
        assert set(data["outcomes"][arm]) == {"clean", "duplicate", "stale", "restart"}
        assert all(value is True for value in data["outcomes"][arm].values())
    a_clean = next(c for c in calls if c["role"] == "A-clean")
    b_clean = next(c for c in calls if c["role"] == "B-clean")
    assert a_clean["input_tokens"] == b_clean["input_tokens"] == 1331
    a_input_cost = (
        costs["A-clean"]
        - a_clean["output_tokens"] * Decimal(a_clean["rates"][2]) / 1_000_000
    )
    b_output_cost = b_clean["output_tokens"] * Decimal(b_clean["rates"][2]) / 1_000_000
    equalized = a_input_cost + b_output_cost
    assert equalized == data["cache_sensitivity"]["B_coordination_cache_equalized_usd"]
    assert equalized + share == data["cache_sensitivity"]["B_with_equal_shared_usd"]
    a, b = data["totals"]["A"], data["totals"]["B"]
    input_saving = (1 - Decimal(b["input_tokens"]) / a["input_tokens"]) * 100
    assert input_saving.quantize(Decimal("0.01")) == Decimal("75.00")
    assert (1 - Decimal(b["calls"]) / a["calls"]) * 100 == 75
    print(f"7 sanitized receipts verified; experiment API USD {sum(costs.values()):.7f}")
    print(f"Coordination input reduction: {input_saving:.2f}%; calls 4 -> 1; outcomes 4/4 each")
    print(f"Cache-equalized cost reduction (calculation): {(1 - equalized / a['usd']) * 100:.2f}%")
    print("Outcome fields are retained evidence summaries, not re-executed quality tests.")
    print("Coordinator subscription cash allocation: unavailable, not zero.")


if __name__ == "__main__":
    verify()
