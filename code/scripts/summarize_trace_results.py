import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from eth_utils import to_checksum_address

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aa_auth_lifecycle.rpc import RpcClient
from aa_auth_lifecycle.utils import load_json


DECIMALS_SELECTOR = "0x313ce567"
SYMBOL_SELECTOR = "0x95d89b41"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def checksum_or_none(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return to_checksum_address(value)
    except ValueError:
        return None


def decode_uint256_hex(value: str) -> int | None:
    if not value or value == "0x":
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def decode_symbol(value: str) -> str | None:
    if not value or value == "0x":
        return None
    raw = bytes.fromhex(value[2:])
    if len(raw) == 32:
        return raw.rstrip(b"\x00").decode("utf-8", errors="ignore") or None
    if len(raw) >= 96:
        length = int.from_bytes(raw[32:64], "big")
        return raw[64:64 + length].decode("utf-8", errors="ignore") or None
    return None


def token_metadata(client: RpcClient | None, token: str) -> dict[str, Any]:
    meta: dict[str, Any] = {"address": token, "symbol": None, "decimals": None}
    if not client:
        return meta
    try:
        decimals = client.call("eth_call", [{"to": token, "data": DECIMALS_SELECTOR}, "latest"])
        meta["decimals"] = decode_uint256_hex(decimals)
    except Exception as exc:
        meta["decimals_error"] = str(exc)
    try:
        symbol = client.call("eth_call", [{"to": token, "data": SYMBOL_SELECTOR}, "latest"])
        meta["symbol"] = decode_symbol(symbol)
    except Exception as exc:
        meta["symbol_error"] = str(exc)
    return meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config_polygon_upgrade_100k.json")
    parser.add_argument("--rpc-url", default=None)
    args = parser.parse_args()

    cfg = load_json(args.config)
    out_dir = Path(cfg.get("output_dir", "data"))
    verify_dir = out_dir / "verification"
    client = RpcClient(args.rpc_url or cfg["rpc_url"], timeout=30, retries=2) if (args.rpc_url or cfg.get("rpc_url")) else None

    approvals = read_jsonl(out_dir / "backscan" / "upgrade_spender_approvals.jsonl")
    approvals_by_spender: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in approvals:
        spender = checksum_or_none(row.get("spender"))
        if spender:
            approvals_by_spender[spender.lower()].append(row)

    spender_rows = []
    all_tokens: set[str] = set()
    global_totals: Counter[str] = Counter()
    global_trace_matches = 0
    global_matched_txs = 0

    for key, rows in sorted(approvals_by_spender.items(), key=lambda item: len(item[1]), reverse=True):
        usage_path = verify_dir / f"post_upgrade_usage_{key}.json"
        trace_path = verify_dir / f"trace_allowance_use_{key}.json"
        impl_path = verify_dir / f"impl_change_{key}.json"
        usage = load_json(usage_path) if usage_path.exists() else {}
        trace = load_json(trace_path) if trace_path.exists() else {}
        impl = load_json(impl_path) if impl_path.exists() else {}
        amount_by_token: Counter[str] = Counter()
        owners = set()
        recipients = set()
        matched_tx_hashes = set()

        for tx in trace.get("matched_txs", []):
            matched_tx_hashes.add(tx.get("tx_hash"))
            for match in tx.get("matches", []):
                token = checksum_or_none(match.get("token"))
                owner = checksum_or_none(match.get("owner"))
                recipient = checksum_or_none(match.get("recipient"))
                amount = match.get("amount")
                if token and isinstance(amount, int):
                    amount_by_token[token] += amount
                    global_totals[token] += amount
                    all_tokens.add(token)
                if owner:
                    owners.add(owner)
                if recipient:
                    recipients.add(recipient)

        match_count = int(trace.get("transfer_from_match_count", 0) or 0)
        global_trace_matches += match_count
        global_matched_txs += len(matched_tx_hashes)
        spender_rows.append({
            "spender": rows[0]["spender"],
            "approval_count": len(rows),
            "unique_approval_owners": len({checksum_or_none(r.get("owner")) for r in rows if r.get("owner")}),
            "unique_approval_tokens": len({checksum_or_none(r.get("token")) for r in rows if r.get("token")}),
            "first_upgrade_block": usage.get("first_upgrade_block"),
            "post_upgrade_transfer_events": usage.get("post_upgrade_transfer_from_approved_owner_count", 0),
            "post_upgrade_unique_transfer_txs": usage.get("unique_transfer_txs", 0),
            "direct_top_level_calls_to_spender": usage.get("direct_top_level_calls_to_spender_count", 0),
            "traced_tx_count": trace.get("traced_tx_count", 0),
            "failed_tx_count": trace.get("failed_tx_count", 0),
            "transfer_from_match_count": match_count,
            "matched_tx_count": len(matched_tx_hashes),
            "matched_owner_count": len(owners),
            "matched_recipient_count": len(recipients),
            "raw_amount_by_token": dict(amount_by_token),
            "implementation_changed_at_upgrade": impl.get("implementation_changed_at_upgrade"),
            "latest_matches_upgrade": impl.get("latest_matches_upgrade"),
            "previous_implementation": impl.get("previous_implementation"),
            "implementation_at_upgrade_block": impl.get("implementation_at_upgrade_block"),
            "latest_implementation": impl.get("latest_implementation"),
            "previous_implementation_code_hash": (impl.get("previous_implementation_code") or {}).get("code_hash"),
            "implementation_at_upgrade_code_hash": (impl.get("implementation_at_upgrade_code") or {}).get("code_hash"),
            "latest_implementation_code_hash": (impl.get("latest_implementation_code") or {}).get("code_hash"),
        })

    metadata = {token: token_metadata(client, token) for token in sorted(all_tokens)}
    for row in spender_rows:
        normalized = {}
        for token, amount in row["raw_amount_by_token"].items():
            decimals = metadata.get(token, {}).get("decimals")
            normalized[token] = str(amount / (10 ** decimals)) if isinstance(decimals, int) else None
        row["normalized_amount_by_token"] = normalized

    summary = {
        "config": {
            "chain_id": cfg.get("chain_id"),
            "from_block": cfg.get("from_block"),
            "to_block": cfg.get("to_block"),
            "output_dir": str(out_dir),
        },
        "backscan_state": load_json(out_dir / "backscan" / "backscan_state.json") if (out_dir / "backscan" / "backscan_state.json").exists() else None,
        "spender_count": len(spender_rows),
        "approval_count": len(approvals),
        "trace_positive_spender_count": sum(1 for row in spender_rows if row["transfer_from_match_count"] > 0),
        "global_transfer_from_match_count": global_trace_matches,
        "global_matched_tx_count": global_matched_txs,
        "token_metadata": metadata,
        "raw_global_amount_by_token": dict(global_totals),
        "spenders": spender_rows,
    }

    write_json(verify_dir / "trace_experiment_summary.json", summary)

    lines = [
        "# Trace Experiment Summary",
        "",
        f"- chain: {summary['config']['chain_id']}",
        f"- block window: {summary['config']['from_block']}--{summary['config']['to_block']}",
        f"- backscan state: {summary['backscan_state']}",
        f"- candidate spenders: {summary['spender_count']}",
        f"- historical approvals: {summary['approval_count']}",
        f"- trace-positive spenders: {summary['trace_positive_spender_count']}",
        f"- matched transferFrom calls: {summary['global_transfer_from_match_count']}",
        "",
        "| spender | approvals | usage txs | traced | matches | matched owners | impl changed | amount |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in spender_rows:
        amount_text = "; ".join(
            f"{metadata.get(token, {}).get('symbol') or token}: {row['normalized_amount_by_token'].get(token) or amount}"
            for token, amount in row["raw_amount_by_token"].items()
        ) or "-"
        lines.append(
            f"| `{row['spender']}` | {row['approval_count']} | {row['post_upgrade_unique_transfer_txs']} | "
            f"{row['traced_tx_count']} | {row['transfer_from_match_count']} | {row['matched_owner_count']} | "
            f"{row['implementation_changed_at_upgrade']} | {amount_text} |"
        )
    (verify_dir / "trace_experiment_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "summary_path": str(verify_dir / "trace_experiment_summary.json"),
        "markdown_path": str(verify_dir / "trace_experiment_summary.md"),
        "trace_positive_spender_count": summary["trace_positive_spender_count"],
        "global_transfer_from_match_count": summary["global_transfer_from_match_count"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
