"""Offline arithmetic verification of the sanitized, recorded API usage."""
import json
from decimal import Decimal
from pathlib import Path


def verify():
    data = json.loads(
        Path(__file__).with_name("receipts.json").read_text(),
        parse_float=Decimal,
    )
    calls = data["inference_calls"]
    assert len(calls) == 55
    assert len({call["id"] for call in calls}) == 55
    totals = dict.fromkeys(("A", "B", "C", "shared"), Decimal(0))
    workers = dict.fromkeys(("A", "B", "C"), Decimal(0))
    for call in calls:
        assert call["status"] == "completed" and call["http_status"] == 200
        raw, cached, output, write = map(Decimal, call["rates"])
        uncached = call["input_tokens"] - call["cached_input_tokens"] - call["cache_write_tokens"]
        assert uncached >= 0
        cost = (
            uncached * raw + call["cached_input_tokens"] * cached
            + call["cache_write_tokens"] * write + call["output_tokens"] * output
        ) / 1_000_000
        assert abs(cost - call["charge_or_reservation_usd"]) < Decimal("0.000000001")
        totals[call["arm"]] += cost
        if call["role"] == "worker":
            workers[call["arm"]] += cost
    assert abs(sum(totals.values()) - data["total"]["usd"]) < Decimal("0.000000001")
    assert abs(totals["shared"] - data["shared"]["usd"]) < Decimal("0.000000001")
    for metric in ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens"):
        assert sum(c[metric] for c in calls) == data["total"][metric]
    share = totals["shared"] / 3
    for arm in "ABC":
        assert abs(totals[arm] - data["arms"][arm]["usd"]) < Decimal("0.000000001")
        assert abs(totals[arm] + share - data["arms"][arm]["with_equal_shared_usd"]) < Decimal("0.000000001")
    worker_saving = (1 - workers["C"] / workers["A"]) * 100
    full_saving = (1 - (totals["C"] + share) / (totals["A"] + share)) * 100
    for actual, name in (
        (worker_saving, "C_vs_A_worker_api_cost_reduction_pct"),
        (full_saving, "C_vs_A_including_equal_shared_api_cost_reduction_pct"),
    ):
        assert abs(actual - data["comparisons"][name]) < Decimal("0.000001")
    print(f"55 receipts verified; total API USD {sum(totals.values()):.9f}")
    print(f"Worker reduction C vs A: {worker_saving:.2f}%")
    print(f"API reduction C vs A, equal shared evaluation: {full_saving:.2f}%")
    print("Coordinator subscription cash allocation: unavailable, not zero")


if __name__ == "__main__":
    verify()
