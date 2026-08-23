import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from eth_abi import decode
from eth_utils import to_checksum_address

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aa_auth_lifecycle.constants import TOPIC_ERC20_APPROVAL, TOPIC_ERC20_TRANSFER
from aa_auth_lifecycle.rpc import RpcClient
from aa_auth_lifecycle.utils import address_to_topic, load_json, read_jsonl, topic_to_address, write_json


EIP1967_ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
EIP1967_IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"


def checksum_or_none(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return to_checksum_address(value)
    except Exception:
        return None


def decode_storage_address(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.lower().replace("0x", "").rjust(64, "0")
    addr = "0x" + raw[-40:]
    if int(addr, 16) == 0:
        return None
    return to_checksum_address(addr)


def hex_int(value: str | int | None) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    return int(value, 16)


def pct(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) * 100.0 / float(denominator), 4)


def short(address: str | None) -> str:
    if not address:
        return "-"
    return f"{address[:6]}...{address[-4:]}"


def read_optional_json(path: Path) -> dict[str, Any]:
    return load_json(path) if path.exists() else {}


def flatten_matches(trace: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for tx in trace.get("matched_txs", []):
        for match in tx.get("matches", []):
            rows.append({
                "tx_hash": tx.get("tx_hash"),
                "caller": checksum_or_none(match.get("caller")),
                "token": checksum_or_none(match.get("token")),
                "owner": checksum_or_none(match.get("owner")),
                "recipient": checksum_or_none(match.get("recipient")),
                "amount": int(match.get("amount") or 0),
                "call_type": match.get("call_type"),
            })
    return rows


def normalize_transfer(log: dict[str, Any]) -> dict[str, Any]:
    data = bytes.fromhex((log.get("data") or "0x")[2:])
    (value,) = decode(["uint256"], data)
    topics = log.get("topics") or []
    return {
        "block_number": hex_int(log.get("blockNumber")),
        "tx_hash": log.get("transactionHash"),
        "log_index": hex_int(log.get("logIndex")),
        "token": to_checksum_address(log["address"]),
        "from": topic_to_address(topics[1]),
        "to": topic_to_address(topics[2]),
        "value": int(value),
    }


def normalize_approval(log: dict[str, Any]) -> dict[str, Any]:
    data = bytes.fromhex((log.get("data") or "0x")[2:])
    (value,) = decode(["uint256"], data)
    topics = log.get("topics") or []
    return {
        "block_number": hex_int(log.get("blockNumber")),
        "tx_hash": log.get("transactionHash"),
        "log_index": hex_int(log.get("logIndex")),
        "token": to_checksum_address(log["address"]),
        "owner": topic_to_address(topics[1]),
        "spender": topic_to_address(topics[2]),
        "value": int(value),
    }


def fetch_tx(client: RpcClient, tx_hash: str, cache: dict[str, Any]) -> dict[str, Any]:
    if tx_hash not in cache:
        cache[tx_hash] = client.call("eth_getTransactionByHash", [tx_hash]) or {}
    return cache[tx_hash]


def fetch_receipt(client: RpcClient, tx_hash: str, cache: dict[str, Any]) -> dict[str, Any]:
    if tx_hash not in cache:
        cache[tx_hash] = client.call("eth_getTransactionReceipt", [tx_hash]) or {}
    return cache[tx_hash]


def fetch_block_timestamp(client: RpcClient, block_number: int) -> int | None:
    block = client.call("eth_getBlockByNumber", [hex(block_number), False]) or {}
    timestamp = block.get("timestamp")
    return int(timestamp, 16) if timestamp else None


def account_code_summary(client: RpcClient, address: str | None) -> dict[str, Any] | None:
    if not address:
        return None
    code = client.call("eth_getCode", [address, "latest"])
    code_bytes = max(0, (len(code or "0x") - 2) // 2)
    return {
        "address": address,
        "is_contract": code_bytes > 0,
        "code_bytes": code_bytes,
    }


def find_level5_spender(exploit: dict[str, Any], requested: str | None) -> str:
    if requested:
        return to_checksum_address(requested)
    for row in exploit.get("spenders", []):
        if int(row.get("evidence_level") or 0) >= 5:
            return to_checksum_address(row["spender"])
    raise SystemExit("No Level-5 spender found. Pass --spender explicitly if needed.")


def scan_transfer_logs(
    client: RpcClient,
    token: str,
    topic_index: int,
    account: str,
    from_block: int,
    to_block: int,
    chunk_size: int,
) -> list[dict[str, Any]]:
    rows = []
    account_topic = address_to_topic(account)
    cur = from_block
    while cur <= to_block:
        end = min(to_block, cur + chunk_size - 1)
        topics: list[str | None] = [TOPIC_ERC20_TRANSFER, None, None]
        topics[topic_index] = account_topic
        logs = client.get_logs(token, topics, cur, end)
        rows.extend(normalize_transfer(log) for log in logs)
        cur = end + 1
    return rows


def scan_post_upgrade_approvals(
    client: RpcClient,
    token: str,
    spender: str,
    from_block: int,
    to_block: int,
    chunk_size: int,
) -> list[dict[str, Any]]:
    rows = []
    spender_topic = address_to_topic(spender)
    cur = from_block
    while cur <= to_block:
        end = min(to_block, cur + chunk_size - 1)
        logs = client.get_logs(token, [TOPIC_ERC20_APPROVAL, None, spender_topic], cur, end)
        rows.extend(normalize_approval(log) for log in logs)
        cur = end + 1
    return rows


def token_amounts(rows: list[dict[str, Any]], token_metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    totals: Counter[str] = Counter()
    for row in rows:
        token = row.get("token")
        if token:
            totals[token] += int(row.get("value") or row.get("amount") or 0)
    out = {}
    for token, raw in totals.items():
        meta = token_metadata.get(token) or token_metadata.get(token.lower()) or {}
        decimals = meta.get("decimals")
        normalized = str(raw / (10 ** decimals)) if isinstance(decimals, int) else None
        out[token] = {
            "symbol": meta.get("symbol") or token,
            "raw_amount": raw,
            "normalized_amount": normalized,
        }
    return out


def build_markdown(result: dict[str, Any]) -> str:
    case = result["case"]
    lines = [
        "# Level-5 Case Study",
        "",
        f"- Spender: `{case['spender']}`",
        f"- Evidence label: {case['evidence_label']} (Level {case['evidence_level']})",
        f"- Upgrade block: {case['upgrade_block']}",
        f"- First matched transfer block: {case['first_transfer_block']}",
        f"- Upgrade-to-first-transfer gap: {case['upgrade_to_first_transfer_blocks']} blocks; {case.get('upgrade_to_first_transfer_seconds')} seconds",
        f"- Upgrade tx sender: `{case.get('upgrade_tx_sender')}`",
        f"- Dominant matched tx sender: `{case.get('dominant_tx_sender')}`",
        f"- EIP-1967 admin at upgrade/latest: `{case.get('admin_at_upgrade')}` / `{case.get('admin_latest')}`",
        f"- Implementation at upgrade/latest: `{case.get('implementation_at_upgrade')}` / `{case.get('implementation_latest')}`",
        "",
        "## Matched Allowance Use",
        "",
        f"- Matched transferFrom calls: {case['matched_transfer_from_calls']}",
        f"- Successful matched txs: {case['successful_matched_txs']}",
        f"- Non-owner calls: {case['non_owner_transfer_from_calls']} ({case['non_owner_transfer_from_percent']}%)",
        f"- Unique owners: {case['unique_owners']}",
        f"- Unique tx senders: {case['unique_tx_senders']}",
        f"- Unique recipients: {case['unique_recipients']}",
        f"- Recipient is spender: {case['recipient_is_spender_count']}",
        "",
        "## Concentration",
        "",
        "| Type | Address | Count | Share |",
        "|---|---|---:|---:|",
    ]
    for row in case.get("top_tx_senders", []):
        lines.append(f"| tx sender | `{short(row['address'])}` | {row['count']} | {row['share_percent']}% |")
    for row in case.get("top_recipients", []):
        lines.append(f"| recipient | `{short(row['address'])}` | {row['count']} | {row['share_percent']}% |")

    lines.extend([
        "",
        "## Account Code Summary",
        "",
        "| Account | Address | Contract | Code bytes |",
        "|---|---|---:|---:|",
    ])
    for label, row in (result.get("account_code") or {}).items():
        if row:
            lines.append(f"| {label} | `{short(row['address'])}` | {row['is_contract']} | {row['code_bytes']} |")

    lines.extend([
        "",
        "## Token Flow Window",
        "",
        f"- Scan range: {result['flow_window']['from_block']}--{result['flow_window']['to_block']}",
        f"- Incoming transfers to spender: {result['flow_window']['incoming_transfer_count']}",
        f"- Outgoing transfers from spender: {result['flow_window']['outgoing_transfer_count']}",
        f"- Post-upgrade approvals to spender on matched tokens: {result['flow_window']['post_upgrade_approval_count']}",
        "",
        "### Top incoming senders",
        "",
        "| Address | Count | Share |",
        "|---|---:|---:|",
    ])
    for row in result["flow_window"].get("top_incoming_senders", []):
        lines.append(f"| `{short(row['address'])}` | {row['count']} | {row['share_percent']}% |")

    lines.extend([
        "",
        "### Top outgoing recipients",
        "",
        "| Address | Count | Share |",
        "|---|---:|---:|",
    ])
    for row in result["flow_window"].get("top_outgoing_recipients", []):
        lines.append(f"| `{short(row['address'])}` | {row['count']} | {row['share_percent']}% |")

    lines.extend([
        "",
        "## Amounts",
        "",
    ])
    for label in ("matched_amounts", "incoming_amounts", "outgoing_amounts"):
        lines.append(f"### {label}")
        amounts = result.get(label) or {}
        if not amounts:
            lines.append("- none")
        for token, row in amounts.items():
            lines.append(f"- `{short(token)}` {row['symbol']}: {row['normalized_amount'] or row['raw_amount']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config_polygon_upgrade_100k.json")
    parser.add_argument("--spender", default=None)
    parser.add_argument("--rpc-url", default=None)
    parser.add_argument("--extra-blocks", type=int, default=100000)
    parser.add_argument("--chunk-size", type=int, default=5000)
    args = parser.parse_args()

    cfg = load_json(args.config)
    out_dir = Path(cfg.get("output_dir", "data"))
    verify_dir = out_dir / "verification"
    summary = load_json(verify_dir / "trace_experiment_summary.json")
    exploit = load_json(verify_dir / "exploit_evidence.json")
    spender = find_level5_spender(exploit, args.spender)
    key = spender.lower()
    client = RpcClient(args.rpc_url or cfg["rpc_url"], timeout=45, retries=2)

    evidence = next(row for row in exploit.get("spenders", []) if to_checksum_address(row["spender"]) == spender)
    trace = load_json(verify_dir / f"trace_allowance_use_{key}.json")
    matches = flatten_matches(trace)
    tx_hashes = sorted({row["tx_hash"] for row in matches if row.get("tx_hash")})
    tx_cache: dict[str, Any] = {}
    receipt_cache: dict[str, Any] = {}
    txs = {tx_hash: fetch_tx(client, tx_hash, tx_cache) for tx_hash in tx_hashes}
    receipts = {tx_hash: fetch_receipt(client, tx_hash, receipt_cache) for tx_hash in tx_hashes}

    upgrade_block = int(evidence.get("upgrade_block") or 0)
    first_transfer_block = int(evidence.get("first_transfer_block") or 0)
    scan_to = max(int(cfg["to_block"]), first_transfer_block + args.extra_blocks)
    tokens = sorted({row["token"] for row in matches if row.get("token")})

    incoming = []
    outgoing = []
    approvals = []
    for token in tokens:
        incoming.extend(scan_transfer_logs(client, token, 2, spender, upgrade_block, scan_to, args.chunk_size))
        outgoing.extend(scan_transfer_logs(client, token, 1, spender, upgrade_block, scan_to, args.chunk_size))
        approvals.extend(scan_post_upgrade_approvals(client, token, spender, upgrade_block, scan_to, args.chunk_size))

    matched_senders = [checksum_or_none(txs[row["tx_hash"]].get("from")) for row in matches if row.get("tx_hash") in txs]
    owner_initiated = sum(
        1
        for row in matches
        if row.get("owner") and checksum_or_none((txs.get(row["tx_hash"]) or {}).get("from")) == row.get("owner")
    )
    successful = sum(1 for receipt in receipts.values() if receipt.get("status") == "0x1")
    failed = sum(1 for receipt in receipts.values() if receipt.get("status") == "0x0")
    upgrade_ts = fetch_block_timestamp(client, upgrade_block) if upgrade_block else None
    first_ts = fetch_block_timestamp(client, first_transfer_block) if first_transfer_block else None

    admin_at_upgrade = decode_storage_address(client.call("eth_getStorageAt", [spender, EIP1967_ADMIN_SLOT, hex(upgrade_block)]))
    admin_latest = decode_storage_address(client.call("eth_getStorageAt", [spender, EIP1967_ADMIN_SLOT, "latest"]))
    impl_at_upgrade = decode_storage_address(client.call("eth_getStorageAt", [spender, EIP1967_IMPLEMENTATION_SLOT, hex(upgrade_block)]))
    impl_latest = decode_storage_address(client.call("eth_getStorageAt", [spender, EIP1967_IMPLEMENTATION_SLOT, "latest"]))
    sender_counter = Counter(sender.lower() for sender in matched_senders if sender)
    dominant_sender = sender_counter.most_common(1)[0][0] if sender_counter else None

    token_metadata = summary.get("token_metadata") or {}
    result = {
        "config": {
            "chain_id": cfg.get("chain_id"),
            "from_block": cfg.get("from_block"),
            "to_block": cfg.get("to_block"),
            "output_dir": str(out_dir),
        },
        "case": {
            **evidence,
            "spender": spender,
            "successful_matched_txs": successful,
            "failed_matched_txs": failed,
            "owner_initiated_transfer_from_calls": owner_initiated,
            "non_owner_transfer_from_calls": len(matches) - owner_initiated,
            "non_owner_transfer_from_percent": pct(len(matches) - owner_initiated, len(matches)),
            "unique_tx_senders": len({sender.lower() for sender in matched_senders if sender}),
            "dominant_tx_sender": to_checksum_address(dominant_sender) if dominant_sender else None,
            "admin_at_upgrade": admin_at_upgrade,
            "admin_latest": admin_latest,
            "implementation_at_upgrade": impl_at_upgrade,
            "implementation_latest": impl_latest,
            "upgrade_to_first_transfer_seconds": (
                first_ts - upgrade_ts
                if first_ts is not None and upgrade_ts is not None
                else None
            ),
        },
        "matched_amounts": token_amounts(matches, token_metadata),
        "incoming_amounts": token_amounts(incoming, token_metadata),
        "outgoing_amounts": token_amounts(outgoing, token_metadata),
        "account_code": {
            "spender": account_code_summary(client, spender),
            "upgrade_tx_sender": account_code_summary(client, evidence.get("upgrade_tx_sender")),
            "dominant_tx_sender": account_code_summary(client, to_checksum_address(dominant_sender) if dominant_sender else None),
            "admin_latest": account_code_summary(client, admin_latest),
            "implementation_at_upgrade": account_code_summary(client, impl_at_upgrade),
            "implementation_latest": account_code_summary(client, impl_latest),
        },
        "flow_window": {
            "from_block": upgrade_block,
            "to_block": scan_to,
            "incoming_transfer_count": len(incoming),
            "outgoing_transfer_count": len(outgoing),
            "post_upgrade_approval_count": len(approvals),
            "unique_incoming_senders": len({row["from"].lower() for row in incoming if row.get("from")}),
            "unique_outgoing_recipients": len({row["to"].lower() for row in outgoing if row.get("to")}),
            "top_outgoing_recipients": [
                {"address": addr, "count": count, "share_percent": pct(count, len(outgoing))}
                for addr, count in Counter(row["to"].lower() for row in outgoing if row.get("to")).most_common(10)
            ],
            "top_incoming_senders": [
                {"address": addr, "count": count, "share_percent": pct(count, len(incoming))}
                for addr, count in Counter(row["from"].lower() for row in incoming if row.get("from")).most_common(10)
            ],
        },
        "sample_outgoing_transfers": outgoing[:50],
        "sample_post_upgrade_approvals": approvals[:50],
    }

    out_json = verify_dir / f"level5_case_study_{key}.json"
    out_md = verify_dir / f"level5_case_study_{key}.md"
    write_json(out_json, result)
    out_md.write_text(build_markdown(result), encoding="utf-8")
    print(json.dumps({
        "json": str(out_json),
        "markdown": str(out_md),
        "spender": spender,
        "matched_transfer_from_calls": len(matches),
        "non_owner_transfer_from_calls": result["case"]["non_owner_transfer_from_calls"],
        "incoming_transfer_count": len(incoming),
        "outgoing_transfer_count": len(outgoing),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
