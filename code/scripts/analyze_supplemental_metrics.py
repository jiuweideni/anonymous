#!/usr/bin/env python
"""Compute read-only supplemental metrics from existing experiment artifacts."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


MAX_UINT256 = (1 << 256) - 1


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def pct(part: int, total: int) -> float:
    return round(part * 100.0 / total, 4) if total else 0.0


def percentile(values: list[int], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    k = (len(ordered) - 1) * (p / 100.0)
    lower = math.floor(k)
    upper = math.ceil(k)
    if lower == upper:
        return float(ordered[int(k)])
    return float(ordered[lower] * (upper - k) + ordered[upper] * (k - lower))


def short(addr: str) -> str:
    return f"{addr[:6]}...{addr[-4:]}" if len(addr) > 12 else addr


def fmt_number(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"
    return str(value)


def find_first_upgrade_blocks(events: list[dict[str, Any]]) -> dict[str, int]:
    first: dict[str, int] = {}
    for event in events:
        if event.get("event_type") != "implementation_upgrade":
            continue
        proxy = str(event.get("proxy") or event.get("contract") or "").lower()
        block = event.get("block_number")
        if not proxy or block is None:
            continue
        block_int = int(block)
        if proxy not in first or block_int < first[proxy]:
            first[proxy] = block_int
    return first


def latest_approval_states(approvals: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in approvals:
        key = (
            str(row.get("token", "")).lower(),
            str(row.get("owner", "")).lower(),
            str(row.get("spender", "")).lower(),
        )
        order = (int(row.get("block_number", 0)), int(row.get("log_index", 0)))
        previous = latest.get(key)
        if previous is None or order > previous["_order"]:
            copied = dict(row)
            copied["_order"] = order
            latest[key] = copied
    return latest


def top_rows(counter: Counter[str], total: int, limit: int = 10) -> list[dict[str, Any]]:
    return [
        {"address": address, "count": count, "share_percent": pct(count, total)}
        for address, count in counter.most_common(limit)
    ]


def render_markdown(metrics: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Supplemental Metrics")
    lines.append("")
    lines.append("This report is computed only from existing local artifacts. It does not query an RPC endpoint or change the detector output.")
    lines.append("")
    lines.append("## Exposure")
    exposure = metrics["approval_exposure"]
    lines.append(f"- Historical approval events: {exposure['approval_events']}")
    lines.append(f"- Non-zero approval events: {exposure['nonzero_approval_events']} ({exposure['nonzero_approval_event_percent']}%)")
    lines.append(f"- Zero-value revocation events: {exposure['zero_approval_events']} ({exposure['zero_approval_event_percent']}%)")
    lines.append(f"- Unlimited approval events: {exposure['unlimited_approval_events']} ({exposure['unlimited_approval_event_percent']}%)")
    lines.append(f"- Unique token-owner-spender states: {exposure['unique_token_owner_spender_states']}")
    lines.append(f"- Latest non-zero states: {exposure['latest_nonzero_states']} ({exposure['latest_nonzero_state_percent']}%)")
    lines.append("")
    lines.append("## Approval Age")
    age = metrics["approval_to_upgrade_age_blocks"]
    lines.append(f"- Matched approval events with upgrade block: {age['count']}")
    lines.append(f"- Median blocks before upgrade: {fmt_number(age['median'])}")
    lines.append(f"- P90 blocks before upgrade: {fmt_number(age['p90'])}")
    lines.append(f"- P99 blocks before upgrade: {fmt_number(age['p99'])}")
    lines.append(f"- Max blocks before upgrade: {fmt_number(age['max'])}")
    lines.append("")
    lines.append("## Concentration")
    concentration = metrics["concentration"]
    lines.append(f"- Top spender share: {concentration['top1_spender_share_percent']}%")
    lines.append(f"- Top 3 spender share: {concentration['top3_spender_share_percent']}%")
    lines.append("")
    lines.append("| Rank | Spender | Approval events | Share |")
    lines.append("| --- | --- | ---: | ---: |")
    for idx, row in enumerate(concentration["top_spenders"], start=1):
        lines.append(f"| {idx} | `{short(row['address'])}` | {row['count']} | {row['share_percent']}% |")
    lines.append("")
    lines.append("## Validation Funnel")
    funnel = metrics["validation_funnel"]
    lines.append(f"- Candidate upgraded spenders with historical approvals: {funnel['candidate_spenders']}")
    lines.append(f"- Implementation-change verified spenders: {funnel['implementation_change_verified_spenders']}")
    lines.append(f"- Spenders with post-upgrade transfer activity: {funnel['post_upgrade_transfer_activity_spenders']}")
    lines.append(f"- Trace-positive spenders: {funnel['trace_positive_spenders']}")
    lines.append(f"- Trace-positive rate among candidates: {funnel['trace_positive_candidate_rate_percent']}%")
    lines.append(f"- Trace-confirmed transaction rate among traced transactions: {funnel['trace_confirmed_tx_rate_among_traced_percent']}%")
    lines.append(f"- Trace-confirmed transferFrom calls: {funnel['trace_confirmed_transfer_from_calls']}")
    lines.append(f"- Trace-confirmed transaction count: {funnel['trace_confirmed_transactions']}")
    lines.append("")
    lines.append("## Trace-Positive Spenders")
    lines.append("| Spender | Approval events | Traced txs | Matched txs | transferFrom matches |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for row in metrics["trace_positive_spenders"]:
        lines.append(
            f"| `{short(row['spender'])}` | {row['approval_count']} | {row['traced_tx_count']} | "
            f"{row['matched_tx_count']} | {row['transfer_from_match_count']} |"
        )
    lines.append("")
    lines.append("## Trace-Positive vs Trace-Negative Groups")
    lines.append("| Group | Spenders | Approval events | Latest non-zero states | Post-upgrade txs | Traced txs | Matched txs |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for group in metrics["trace_group_comparison"]:
        lines.append(
            f"| {group['group']} | {group['spender_count']} | {group['approval_events']} | "
            f"{group['latest_nonzero_states']} | {group['post_upgrade_unique_transfer_txs']} | "
            f"{group['traced_tx_count']} | {group['matched_tx_count']} |"
        )
    lines.append("")
    return "\n".join(lines)


def analyze(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    out_dir = (config_path.parent / config["output_dir"]).resolve()
    approvals = read_jsonl(out_dir / "backscan" / "upgrade_spender_approvals.jsonl")
    events = read_jsonl(out_dir / "normalized" / "events.jsonl")
    summary = load_json(out_dir / "verification" / "trace_experiment_summary.json")

    first_upgrade = find_first_upgrade_blocks(events)
    latest_states = latest_approval_states(approvals)

    values = [int(row.get("value", 0)) for row in approvals]
    nonzero_events = sum(1 for value in values if value > 0)
    zero_events = sum(1 for value in values if value == 0)
    unlimited_events = sum(1 for value in values if value == MAX_UINT256)
    latest_nonzero = sum(1 for row in latest_states.values() if int(row.get("value", 0)) > 0)

    spender_counter = Counter(str(row.get("spender", "")).lower() for row in approvals)
    owner_counter = Counter(str(row.get("owner", "")).lower() for row in approvals)
    token_counter = Counter(str(row.get("token", "")).lower() for row in approvals)

    approval_ages: list[int] = []
    per_spender_ages: dict[str, list[int]] = defaultdict(list)
    for row in approvals:
        spender = str(row.get("spender", "")).lower()
        upgrade_block = first_upgrade.get(spender)
        if upgrade_block is None:
            continue
        delta = upgrade_block - int(row.get("block_number", 0))
        if delta >= 0:
            approval_ages.append(delta)
            per_spender_ages[spender].append(delta)

    spenders = summary.get("spenders", [])
    trace_positive = [row for row in spenders if int(row.get("transfer_from_match_count") or 0) > 0]
    post_upgrade_active = [row for row in spenders if int(row.get("post_upgrade_unique_transfer_txs") or 0) > 0]
    implementation_verified = [row for row in spenders if row.get("implementation_changed_at_upgrade") is True]
    traced_tx_count = sum(int(row.get("traced_tx_count") or 0) for row in spenders)
    positive_spenders = {str(row.get("spender", "")).lower() for row in trace_positive}
    all_candidate_spenders = {str(row.get("spender", "")).lower() for row in spenders}

    group_rows: list[dict[str, Any]] = []
    for label, selected in [
        ("trace-positive", positive_spenders),
        ("trace-negative", all_candidate_spenders - positive_spenders),
    ]:
        selected_summary = [
            row for row in spenders if str(row.get("spender", "")).lower() in selected
        ]
        selected_ages = [
            age
            for spender, values_for_spender in per_spender_ages.items()
            if spender in selected
            for age in values_for_spender
        ]
        selected_latest_states = [
            row
            for (_token, _owner, spender), row in latest_states.items()
            if spender in selected
        ]
        selected_latest_nonzero = sum(
            1 for row in selected_latest_states if int(row.get("value", 0)) > 0
        )
        group_rows.append(
            {
                "group": label,
                "spender_count": len(selected),
                "approval_events": sum(int(row.get("approval_count") or 0) for row in selected_summary),
                "latest_states": len(selected_latest_states),
                "latest_nonzero_states": selected_latest_nonzero,
                "latest_nonzero_state_percent": pct(selected_latest_nonzero, len(selected_latest_states)),
                "median_approval_age_blocks": percentile(selected_ages, 50),
                "post_upgrade_unique_transfer_txs": sum(
                    int(row.get("post_upgrade_unique_transfer_txs") or 0) for row in selected_summary
                ),
                "traced_tx_count": sum(int(row.get("traced_tx_count") or 0) for row in selected_summary),
                "matched_tx_count": sum(int(row.get("matched_tx_count") or 0) for row in selected_summary),
                "transfer_from_match_count": sum(
                    int(row.get("transfer_from_match_count") or 0) for row in selected_summary
                ),
            }
        )

    total_approvals = len(approvals)
    top_counts = [count for _addr, count in spender_counter.most_common(3)]

    metrics: dict[str, Any] = {
        "config": {
            "chain_id": config.get("chain_id"),
            "from_block": config.get("from_block"),
            "to_block": config.get("to_block"),
            "output_dir": config.get("output_dir"),
        },
        "approval_exposure": {
            "approval_events": total_approvals,
            "nonzero_approval_events": nonzero_events,
            "nonzero_approval_event_percent": pct(nonzero_events, total_approvals),
            "zero_approval_events": zero_events,
            "zero_approval_event_percent": pct(zero_events, total_approvals),
            "unlimited_approval_events": unlimited_events,
            "unlimited_approval_event_percent": pct(unlimited_events, total_approvals),
            "unique_token_owner_spender_states": len(latest_states),
            "latest_nonzero_states": latest_nonzero,
            "latest_nonzero_state_percent": pct(latest_nonzero, len(latest_states)),
        },
        "approval_to_upgrade_age_blocks": {
            "count": len(approval_ages),
            "min": min(approval_ages) if approval_ages else None,
            "median": percentile(approval_ages, 50),
            "p90": percentile(approval_ages, 90),
            "p99": percentile(approval_ages, 99),
            "max": max(approval_ages) if approval_ages else None,
            "per_spender": [
                {
                    "spender": spender,
                    "count": len(values_for_spender),
                    "median": percentile(values_for_spender, 50),
                    "p90": percentile(values_for_spender, 90),
                }
                for spender, values_for_spender in sorted(
                    per_spender_ages.items(),
                    key=lambda item: len(item[1]),
                    reverse=True,
                )
            ],
        },
        "concentration": {
            "top1_spender_share_percent": pct(top_counts[0], total_approvals) if top_counts else 0.0,
            "top3_spender_share_percent": pct(sum(top_counts), total_approvals),
            "top_spenders": top_rows(spender_counter, total_approvals),
            "top_owners": top_rows(owner_counter, total_approvals),
            "top_tokens": top_rows(token_counter, total_approvals),
        },
        "validation_funnel": {
            "candidate_spenders": len(spenders),
            "implementation_change_verified_spenders": len(implementation_verified),
            "post_upgrade_transfer_activity_spenders": len(post_upgrade_active),
            "trace_positive_spenders": len(trace_positive),
            "trace_positive_candidate_rate_percent": pct(len(trace_positive), len(spenders)),
            "traced_transactions": traced_tx_count,
            "trace_confirmed_transfer_from_calls": int(summary.get("global_transfer_from_match_count") or 0),
            "trace_confirmed_transactions": int(summary.get("global_matched_tx_count") or 0),
            "trace_confirmed_tx_rate_among_traced_percent": pct(
                int(summary.get("global_matched_tx_count") or 0),
                traced_tx_count,
            ),
        },
        "trace_positive_spenders": sorted(
            trace_positive,
            key=lambda row: int(row.get("transfer_from_match_count") or 0),
            reverse=True,
        ),
        "trace_group_comparison": group_rows,
    }
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config_polygon_upgrade_100k.json")
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--md-out", default=None)
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    metrics = analyze(config_path)
    out_dir = (config_path.parent / metrics["config"]["output_dir"] / "verification").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = Path(args.json_out).resolve() if args.json_out else out_dir / "supplemental_metrics.json"
    md_out = Path(args.md_out).resolve() if args.md_out else out_dir / "supplemental_metrics.md"

    json_out.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(metrics), encoding="utf-8")
    print(f"Wrote {json_out}")
    print(f"Wrote {md_out}")


if __name__ == "__main__":
    main()
