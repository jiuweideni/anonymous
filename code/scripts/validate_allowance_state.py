#!/usr/bin/env python
"""Validate active ERC-20 allowance state for drift candidates."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aa_auth_lifecycle.rpc import RpcClient
from aa_auth_lifecycle.utils import load_json, read_jsonl


ALLOWANCE_SELECTOR = "0xdd62ed3e"
MAX_UINT256 = (1 << 256) - 1


def encode_address_word(address: str) -> str:
    return address.lower().replace("0x", "").rjust(64, "0")


def decode_uint256(hex_value: str) -> int:
    if not hex_value or hex_value == "0x":
        return 0
    return int(hex_value, 16)


def eth_call_allowance(
    client: RpcClient,
    token: str,
    owner: str,
    spender: str,
    block_tag: str,
) -> int:
    calldata = ALLOWANCE_SELECTOR + encode_address_word(owner) + encode_address_word(spender)
    result = client.call("eth_call", [{"to": token, "data": calldata}, block_tag])
    return decode_uint256(result)


def first_upgrade_blocks(events: list[dict[str, Any]]) -> dict[str, int]:
    upgrades: dict[str, int] = {}
    for event in events:
        if event.get("event_type") != "implementation_upgrade":
            continue
        proxy = str(event.get("proxy") or "").lower()
        block = int(event.get("block_number") or 0)
        if not proxy or not block:
            continue
        upgrades[proxy] = min(block, upgrades.get(proxy, block))
    return upgrades


def latest_preupgrade_states(
    approvals: list[dict[str, Any]],
    upgrades: dict[str, int],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in approvals:
        spender = str(row.get("spender") or "").lower()
        upgrade_block = upgrades.get(spender)
        if upgrade_block is None or int(row.get("block_number") or 0) >= upgrade_block:
            continue
        key = (
            str(row.get("token") or "").lower(),
            str(row.get("owner") or "").lower(),
            spender,
        )
        order = (int(row.get("block_number") or 0), int(row.get("log_index") or 0))
        previous = latest.get(key)
        if previous is None or order > previous["_order"]:
            item = dict(row)
            item["_order"] = order
            item["upgrade_block"] = upgrade_block
            latest[key] = item
    return latest


def trace_positive_spenders(summary_path: Path) -> set[str]:
    if not summary_path.exists():
        return set()
    summary = load_json(summary_path)
    return {
        str(row.get("spender") or "").lower()
        for row in summary.get("spenders", [])
        if int(row.get("transfer_from_match_count") or 0) > 0
    }


def choose_states(
    states: list[dict[str, Any]],
    per_spender_limit: int,
    global_limit: int,
) -> list[dict[str, Any]]:
    by_spender: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in states:
        by_spender[str(row["spender"]).lower()].append(row)

    selected: list[dict[str, Any]] = []
    for spender in sorted(by_spender):
        rows = sorted(
            by_spender[spender],
            key=lambda item: (int(item.get("value") or 0), int(item.get("block_number") or 0)),
            reverse=True,
        )
        selected.extend(rows[:per_spender_limit])
    if global_limit > 0:
        selected = selected[:global_limit]
    return selected


def pct(part: int, total: int) -> float:
    return round(part * 100.0 / total, 4) if total else 0.0


def summarize_checks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    upgrade_ok = [row for row in rows if row.get("allowance_at_upgrade_error") is None]
    latest_ok = [row for row in rows if row.get("latest_allowance_error") is None]
    upgrade_nonzero = sum(1 for row in upgrade_ok if int(row.get("allowance_at_upgrade") or 0) > 0)
    latest_nonzero = sum(1 for row in latest_ok if int(row.get("latest_allowance") or 0) > 0)
    return {
        "checked_states": len(rows),
        "upgrade_call_success": len(upgrade_ok),
        "latest_call_success": len(latest_ok),
        "upgrade_nonzero": upgrade_nonzero,
        "upgrade_nonzero_percent": pct(upgrade_nonzero, len(upgrade_ok)),
        "latest_nonzero": latest_nonzero,
        "latest_nonzero_percent": pct(latest_nonzero, len(latest_ok)),
        "latest_unlimited": sum(1 for row in latest_ok if int(row.get("latest_allowance") or 0) == MAX_UINT256),
        "call_error_count": len(rows) - min(len(upgrade_ok), len(latest_ok)),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Active Allowance State Validation")
    lines.append("")
    lines.append(f"- chain: {result['config']['chain_id']}")
    lines.append(f"- block window: {result['config']['from_block']}--{result['config']['to_block']}")
    lines.append(f"- candidate latest pre-upgrade states: {result['candidate_latest_preupgrade_states']}")
    lines.append(f"- checked states: {result['summary']['checked_states']}")
    lines.append(f"- upgrade-time nonzero: {result['summary']['upgrade_nonzero']} ({result['summary']['upgrade_nonzero_percent']}%)")
    lines.append(f"- latest nonzero: {result['summary']['latest_nonzero']} ({result['summary']['latest_nonzero_percent']}%)")
    lines.append(f"- latest unlimited: {result['summary']['latest_unlimited']}")
    lines.append("")
    lines.append("## Trace Group Comparison")
    lines.append("| Group | Checked | Upgrade nonzero | Latest nonzero | Latest unlimited |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for group in result["group_summary"]:
        lines.append(
            f"| {group['group']} | {group['checked_states']} | "
            f"{group['upgrade_nonzero']} ({group['upgrade_nonzero_percent']}%) | "
            f"{group['latest_nonzero']} ({group['latest_nonzero_percent']}%) | "
            f"{group['latest_unlimited']} |"
        )
    lines.append("")
    lines.append("## Per-Spender Summary")
    lines.append("| Spender | Trace positive | Checked | Upgrade nonzero | Latest nonzero |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    for row in result["spender_summary"]:
        spender = row["spender"]
        short = f"{spender[:6]}...{spender[-4:]}"
        lines.append(
            f"| `{short}` | {row['trace_positive']} | {row['checked_states']} | "
            f"{row['upgrade_nonzero']} ({row['upgrade_nonzero_percent']}%) | "
            f"{row['latest_nonzero']} ({row['latest_nonzero_percent']}%) |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config_polygon_upgrade_100k.json")
    parser.add_argument("--rpc-url", default=None)
    parser.add_argument("--per-spender-limit", type=int, default=50)
    parser.add_argument("--global-limit", type=int, default=0)
    args = parser.parse_args()

    cfg = load_json(args.config)
    if args.rpc_url:
        cfg["rpc_url"] = args.rpc_url
    out_dir = Path(cfg.get("output_dir", "data"))
    events = read_jsonl(out_dir / "normalized" / "events.jsonl")
    approvals = read_jsonl(out_dir / "backscan" / "upgrade_spender_approvals.jsonl")
    upgrades = first_upgrade_blocks(events)
    states = list(latest_preupgrade_states(approvals, upgrades).values())
    selected = choose_states(states, args.per_spender_limit, args.global_limit)
    positive = trace_positive_spenders(out_dir / "verification" / "trace_experiment_summary.json")

    client = RpcClient(cfg["rpc_url"], timeout=30, retries=3)
    checks: list[dict[str, Any]] = []
    for row in selected:
        token = row["token"]
        owner = row["owner"]
        spender = row["spender"]
        upgrade_block = int(row["upgrade_block"])
        check: dict[str, Any] = {
            "token": token,
            "owner": owner,
            "spender": spender,
            "approval_block": int(row["block_number"]),
            "approval_value": int(row.get("value") or 0),
            "upgrade_block": upgrade_block,
            "trace_positive_spender": spender.lower() in positive,
        }
        try:
            check["allowance_at_upgrade"] = eth_call_allowance(client, token, owner, spender, hex(upgrade_block))
            check["allowance_at_upgrade_error"] = None
        except Exception as exc:
            check["allowance_at_upgrade"] = None
            check["allowance_at_upgrade_error"] = str(exc)
        try:
            check["latest_allowance"] = eth_call_allowance(client, token, owner, spender, "latest")
            check["latest_allowance_error"] = None
        except Exception as exc:
            check["latest_allowance"] = None
            check["latest_allowance_error"] = str(exc)
        checks.append(check)

    spender_summary = []
    for spender in sorted({row["spender"].lower() for row in checks}):
        rows = [row for row in checks if row["spender"].lower() == spender]
        item = summarize_checks(rows)
        item["spender"] = spender
        item["trace_positive"] = spender in positive
        spender_summary.append(item)

    group_summary = []
    for label, predicate in (
        ("trace-positive", lambda row: bool(row["trace_positive_spender"])),
        ("trace-negative", lambda row: not bool(row["trace_positive_spender"])),
    ):
        rows = [row for row in checks if predicate(row)]
        item = summarize_checks(rows)
        item["group"] = label
        group_summary.append(item)

    result = {
        "config": {
            "chain_id": cfg.get("chain_id"),
            "from_block": cfg.get("from_block"),
            "to_block": cfg.get("to_block"),
            "output_dir": cfg.get("output_dir"),
        },
        "candidate_latest_preupgrade_states": len(states),
        "selected_policy": {
            "per_spender_limit": args.per_spender_limit,
            "global_limit": args.global_limit,
        },
        "summary": summarize_checks(checks),
        "group_summary": group_summary,
        "spender_summary": spender_summary,
        "checks": checks,
    }

    verify_dir = out_dir / "verification"
    verify_dir.mkdir(parents=True, exist_ok=True)
    json_path = verify_dir / "allowance_state_validation.json"
    md_path = verify_dir / "allowance_state_validation.md"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps({"json_path": str(json_path), "markdown_path": str(md_path), "checked_states": len(checks)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
