import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from eth_abi import decode
from eth_utils import to_checksum_address
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aa_auth_lifecycle.constants import TOPIC_ERC20_TRANSFER
from aa_auth_lifecycle.rpc import RpcClient
from aa_auth_lifecycle.utils import address_to_topic, hex_to_int, load_json, topic_to_address


def read_jsonl(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def normalize_transfer(log):
    data = bytes.fromhex((log.get("data") or "0x")[2:])
    (value,) = decode(["uint256"], data)
    topics = log.get("topics", [])
    return {
        "block_number": hex_to_int(log.get("blockNumber")),
        "tx_hash": log.get("transactionHash"),
        "log_index": hex_to_int(log.get("logIndex")),
        "token": to_checksum_address(log["address"]),
        "from": topic_to_address(topics[1]),
        "to": topic_to_address(topics[2]),
        "value": int(value),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config_polygon_upgrade_100k.json")
    parser.add_argument("--spender", required=True)
    parser.add_argument("--owner-chunk-size", type=int, default=100)
    parser.add_argument("--block-chunk-size", type=int, default=5000)
    parser.add_argument("--max-token-count", type=int, default=5)
    parser.add_argument("--max-owner-count", type=int, default=1000)
    args = parser.parse_args()

    cfg = load_json(args.config)
    out_dir = Path(cfg.get("output_dir", "data"))
    spender = to_checksum_address(args.spender)
    approvals = [
        row for row in read_jsonl(out_dir / "backscan" / "upgrade_spender_approvals.jsonl")
        if to_checksum_address(row["spender"]) == spender
    ]
    events = read_jsonl(out_dir / "normalized" / "events.jsonl")
    upgrades = [
        row for row in events
        if row.get("event_type") == "implementation_upgrade"
        and row.get("proxy")
        and to_checksum_address(row["proxy"]) == spender
    ]
    if not approvals:
        raise SystemExit("No approvals found for spender.")
    if not upgrades:
        raise SystemExit("No upgrade event found for spender.")

    first_upgrade = min(upgrades, key=lambda row: (row["block_number"], row["log_index"]))
    start_block = int(first_upgrade["block_number"])
    to_block = int(cfg["to_block"])

    token_counts = Counter(to_checksum_address(row["token"]) for row in approvals)
    owner_counts = Counter(to_checksum_address(row["owner"]) for row in approvals)
    tokens = [token for token, _ in token_counts.most_common(args.max_token_count)]
    owners = [owner for owner, _ in owner_counts.most_common(args.max_owner_count)]
    owner_topics = [address_to_topic(owner) for owner in owners]

    client = RpcClient(cfg["rpc_url"])
    transfer_rows = []
    tx_cache = {}
    direct_to_spender = []

    block_ranges = []
    cur = start_block
    while cur <= to_block:
        end = min(to_block, cur + args.block_chunk_size - 1)
        block_ranges.append((cur, end))
        cur = end + 1

    for token in tqdm(tokens, desc="Scanning tokens"):
        for owner_topic_chunk in chunked(owner_topics, args.owner_chunk_size):
            for start, end in block_ranges:
                logs = client.get_logs(
                    token,
                    [TOPIC_ERC20_TRANSFER, owner_topic_chunk, None],
                    start,
                    end,
                )
                for log in logs:
                    row = normalize_transfer(log)
                    transfer_rows.append(row)
                    tx_hash = row["tx_hash"]
                    if tx_hash not in tx_cache:
                        tx_cache[tx_hash] = client.call("eth_getTransactionByHash", [tx_hash])
                    tx = tx_cache[tx_hash] or {}
                    tx_to = tx.get("to")
                    if tx_to and to_checksum_address(tx_to) == spender:
                        direct_to_spender.append({**row, "transaction_to": to_checksum_address(tx_to)})

    by_token = Counter(row["token"] for row in transfer_rows)
    by_owner = Counter(row["from"] for row in transfer_rows)
    result = {
        "spender": spender,
        "first_upgrade_block": start_block,
        "scan_to_block": to_block,
        "approval_count_for_spender": len(approvals),
        "owner_count_considered": len(owners),
        "token_count_considered": len(tokens),
        "tokens_considered": tokens,
        "post_upgrade_transfer_from_approved_owner_count": len(transfer_rows),
        "unique_transfer_txs": len({row["tx_hash"] for row in transfer_rows}),
        "unique_transfer_owners": len({row["from"] for row in transfer_rows}),
        "top_transfer_tokens": by_token.most_common(10),
        "top_transfer_owners": by_owner.most_common(10),
        "direct_top_level_calls_to_spender_count": len(direct_to_spender),
        "direct_top_level_calls_to_spender": direct_to_spender[:200],
        "sample_transfers": transfer_rows[:200],
    }

    verify_dir = out_dir / "verification"
    verify_dir.mkdir(parents=True, exist_ok=True)
    out_path = verify_dir / f"post_upgrade_usage_{spender.lower()}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
