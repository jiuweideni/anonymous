from pathlib import Path
from typing import Any

from eth_abi import decode

from .utils import append_jsonl, hex_to_int, load_json, normalize_address, read_jsonl, topic_to_address


def _base_log(log: dict[str, Any]) -> dict[str, Any]:
    return {
        "chain_id": None,
        "block_number": hex_to_int(log.get("blockNumber")),
        "tx_hash": log.get("transactionHash"),
        "log_index": hex_to_int(log.get("logIndex")),
        "contract": normalize_address(log.get("address")),
    }


def normalize_entrypoint_userop(log: dict[str, Any], chain_id: int) -> dict[str, Any]:
    topics = log.get("topics", [])
    data = bytes.fromhex((log.get("data") or "0x")[2:])
    nonce, success, actual_gas_cost, actual_gas_used = decode(
        ["uint256", "bool", "uint256", "uint256"],
        data,
    )
    row = _base_log(log)
    row.update({
        "chain_id": chain_id,
        "event_type": "erc4337_user_operation",
        "user_op_hash": topics[1] if len(topics) > 1 else None,
        "smart_account": topic_to_address(topics[2]) if len(topics) > 2 else None,
        "paymaster": topic_to_address(topics[3]) if len(topics) > 3 else None,
        "nonce": int(nonce),
        "success": bool(success),
        "actual_gas_cost": int(actual_gas_cost),
        "actual_gas_used": int(actual_gas_used),
    })
    return row


def normalize_approval(log: dict[str, Any], chain_id: int, source: str) -> dict[str, Any]:
    topics = log.get("topics", [])
    data = bytes.fromhex((log.get("data") or "0x")[2:])
    (value,) = decode(["uint256"], data)
    row = _base_log(log)
    row.update({
        "chain_id": chain_id,
        "event_type": source,
        "token": normalize_address(log.get("address")),
        "owner": topic_to_address(topics[1]) if len(topics) > 1 else None,
        "spender": topic_to_address(topics[2]) if len(topics) > 2 else None,
        "value": int(value),
    })
    return row


def normalize_upgrade(log: dict[str, Any], chain_id: int) -> dict[str, Any]:
    topics = log.get("topics", [])
    row = _base_log(log)
    row.update({
        "chain_id": chain_id,
        "event_type": "implementation_upgrade",
        "proxy": normalize_address(log.get("address")),
        "implementation": topic_to_address(topics[1]) if len(topics) > 1 else None,
    })
    return row


def normalize(config_path: str) -> dict[str, int]:
    cfg = load_json(config_path)
    out_dir = Path(cfg.get("output_dir", "data"))
    raw_dir = out_dir / "raw_logs"
    normalized_path = out_dir / "normalized" / "events.jsonl"
    if normalized_path.exists():
        normalized_path.unlink()

    chain_id = int(cfg["chain_id"])
    rows: list[dict[str, Any]] = []
    counts = {
        "erc4337_user_operation": 0,
        "erc20_approval": 0,
        "permit2_approval": 0,
        "implementation_upgrade": 0,
    }

    for log in read_jsonl(raw_dir / "entrypoint_userops.jsonl"):
        rows.append(normalize_entrypoint_userop(log, chain_id))
        counts["erc4337_user_operation"] += 1

    for log in read_jsonl(raw_dir / "erc20_approvals.jsonl"):
        rows.append(normalize_approval(log, chain_id, "erc20_approval"))
        counts["erc20_approval"] += 1

    for log in read_jsonl(raw_dir / "permit2_approvals.jsonl"):
        rows.append(normalize_approval(log, chain_id, "permit2_approval"))
        counts["permit2_approval"] += 1

    for log in read_jsonl(raw_dir / "upgrades.jsonl"):
        rows.append(normalize_upgrade(log, chain_id))
        counts["implementation_upgrade"] += 1

    rows.sort(key=lambda x: (x["block_number"], x["log_index"]))
    append_jsonl(normalized_path, rows)
    return counts
