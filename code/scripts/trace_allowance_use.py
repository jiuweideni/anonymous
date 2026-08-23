import argparse
import json
import sys
from pathlib import Path
from typing import Any

from eth_utils import to_checksum_address

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aa_auth_lifecycle.rpc import RpcClient
from aa_auth_lifecycle.utils import load_json


TRANSFER_FROM_SELECTOR = "0x23b872dd"
QUOTA_PATTERNS = (
    "quota",
    "rate limit",
    "rate-limit",
    "too many requests",
    "daily request count",
    "project id request rate exceeded",
    "exceeded",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def is_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(pattern in text for pattern in QUOTA_PATTERNS)


def checksum_or_none(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return to_checksum_address(value)
    except ValueError:
        return None


def calldata_address(calldata: str, index: int) -> str | None:
    if not calldata or not calldata.startswith(TRANSFER_FROM_SELECTOR):
        return None
    start = 10 + index * 64
    word = calldata[start:start + 64]
    if len(word) != 64:
        return None
    return checksum_or_none("0x" + word[-40:])


def calldata_uint256(calldata: str, index: int) -> int | None:
    if not calldata or not calldata.startswith(TRANSFER_FROM_SELECTOR):
        return None
    start = 10 + index * 64
    word = calldata[start:start + 64]
    if len(word) != 64:
        return None
    return int(word, 16)


def flatten_call_tracer(node: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [node]
    for child in node.get("calls", []) or []:
        rows.extend(flatten_call_tracer(child))
    return rows


def extract_debug_calls(trace: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for call in flatten_call_tracer(trace):
        rows.append({
            "from": checksum_or_none(call.get("from")),
            "to": checksum_or_none(call.get("to")),
            "input": call.get("input") or "",
            "type": call.get("type"),
            "value": call.get("value"),
            "gas": call.get("gas"),
            "gas_used": call.get("gasUsed"),
            "error": call.get("error"),
        })
    return rows


def extract_trace_transaction_calls(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in trace:
        action = item.get("action") or {}
        rows.append({
            "from": checksum_or_none(action.get("from")),
            "to": checksum_or_none(action.get("to")),
            "input": action.get("input") or "",
            "type": action.get("callType") or item.get("type"),
            "value": action.get("value"),
            "gas": action.get("gas"),
            "gas_used": (item.get("result") or {}).get("gasUsed"),
            "error": item.get("error"),
        })
    return rows


def trace_transaction(client: RpcClient, tx_hash: str) -> tuple[str, list[dict[str, Any]], Any]:
    try:
        result = client.call("debug_traceTransaction", [
            tx_hash,
            {"tracer": "callTracer", "timeout": "30s"},
        ])
        return "debug_traceTransaction.callTracer", extract_debug_calls(result), result
    except Exception as debug_error:
        try:
            result = client.call("trace_transaction", [tx_hash])
            return "trace_transaction", extract_trace_transaction_calls(result), result
        except Exception as trace_error:
            raise RuntimeError({
                "debug_traceTransaction": str(debug_error),
                "trace_transaction": str(trace_error),
            })


def find_transfer_from_matches(
    calls: list[dict[str, Any]],
    spender: str,
    approved_tokens: set[str],
    approved_owners: set[str],
) -> list[dict[str, Any]]:
    matches = []
    for call in calls:
        caller = call.get("from")
        token = call.get("to")
        data = call.get("input") or ""
        if caller != spender or token not in approved_tokens:
            continue
        if not data.startswith(TRANSFER_FROM_SELECTOR):
            continue
        owner = calldata_address(data, 0)
        recipient = calldata_address(data, 1)
        if owner not in approved_owners:
            continue
        matches.append({
            "caller": caller,
            "token": token,
            "owner": owner,
            "recipient": recipient,
            "amount": calldata_uint256(data, 2),
            "call_type": call.get("type"),
            "input_selector": data[:10],
            "gas": call.get("gas"),
            "gas_used": call.get("gas_used"),
            "error": call.get("error"),
        })
    return matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config_polygon_upgrade_100k.json")
    parser.add_argument("--spender", required=True)
    parser.add_argument("--max-txs", type=int, default=0)
    parser.add_argument("--rpc-url", default=None)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    cfg = load_json(args.config)
    out_dir = Path(cfg.get("output_dir", "data"))
    verify_dir = out_dir / "verification"
    spender = to_checksum_address(args.spender)
    spender_key = spender.lower()

    post_usage_path = verify_dir / f"post_upgrade_usage_{spender_key}.json"
    if not post_usage_path.exists():
        raise SystemExit(f"Missing post-upgrade usage file: {post_usage_path}")
    post_usage = load_json(post_usage_path)
    transfers = post_usage.get("sample_transfers", [])
    tx_hashes = sorted({row["tx_hash"] for row in transfers if row.get("tx_hash")})
    if args.max_txs:
        tx_hashes = tx_hashes[:args.max_txs]

    approvals = [
        row for row in read_jsonl(out_dir / "backscan" / "upgrade_spender_approvals.jsonl")
        if checksum_or_none(row.get("spender")) == spender
    ]
    approved_tokens = {to_checksum_address(row["token"]) for row in approvals}
    approved_owners = {to_checksum_address(row["owner"]) for row in approvals}

    result_path = verify_dir / f"trace_allowance_use_{spender_key}.json"
    state_path = verify_dir / f"trace_allowance_use_{spender_key}.state.json"
    marker_path = verify_dir / f"trace_quota_or_method_marker_{spender_key}.json"
    if args.reset:
        result = None
        for path in (result_path, state_path, marker_path):
            if path.exists():
                path.unlink()
    else:
        result = load_json(result_path) if result_path.exists() else None
    result = result or {
        "spender": spender,
        "trace_source": None,
        "rpc_label": "override" if args.rpc_url else "config",
        "candidate_tx_count": len(tx_hashes),
        "traced_tx_count": 0,
        "failed_tx_count": 0,
        "transfer_from_match_count": 0,
        "matched_txs": [],
        "failed_txs": [],
        "method_errors": [],
    }
    traced = {row["tx_hash"] for row in result.get("matched_txs", [])}
    traced.update(row["tx_hash"] for row in result.get("failed_txs", []) if not row.get("retryable"))

    client = RpcClient(args.rpc_url or cfg["rpc_url"], timeout=60, retries=1)
    for tx_hash in tx_hashes:
        if tx_hash in traced:
            continue
        try:
            source, calls, raw = trace_transaction(client, tx_hash)
            result["trace_source"] = result.get("trace_source") or source
            matches = find_transfer_from_matches(calls, spender, approved_tokens, approved_owners)
            if matches:
                result["matched_txs"].append({
                    "tx_hash": tx_hash,
                    "match_count": len(matches),
                    "matches": matches,
                })
                result["transfer_from_match_count"] += len(matches)
            result["traced_tx_count"] += 1
            write_json(state_path, {"next_tx_hash": tx_hash, "status": "running"})
            write_json(result_path, result)
        except Exception as exc:
            error_text = str(exc)
            failure = {"tx_hash": tx_hash, "error": error_text, "retryable": is_quota_error(exc)}
            result["failed_txs"].append(failure)
            result["failed_tx_count"] += 1
            result["method_errors"].append(failure)
            write_json(result_path, result)
            if args.continue_on_error:
                write_json(state_path, {
                    "status": "running",
                    "last_failed_tx_hash": tx_hash,
                    "continue_on_error": True,
                })
                continue
            if is_quota_error(exc) or "method" in error_text.lower() or "not available" in error_text.lower():
                write_json(marker_path, {
                    "status": "stopped",
                    "tx_hash": tx_hash,
                    "error": error_text,
                })
                print(json.dumps(load_json(marker_path), indent=2, ensure_ascii=False))
                return 2
            raise

    write_json(state_path, {"status": "complete", "traced_tx_count": result["traced_tx_count"]})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
