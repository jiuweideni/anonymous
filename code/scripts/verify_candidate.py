import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from eth_utils import keccak, to_checksum_address

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aa_auth_lifecycle.rpc import RpcClient
from aa_auth_lifecycle.utils import address_to_topic, load_json


EIP1967_IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
ALLOWANCE_SELECTOR = "0xdd62ed3e"


def read_jsonl(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def encode_address_word(address: str) -> str:
    return address.lower().replace("0x", "").rjust(64, "0")


def decode_uint256(hex_value: str) -> int:
    if not hex_value or hex_value == "0x":
        return 0
    return int(hex_value, 16)


def decode_address_from_storage(hex_value: str) -> str | None:
    if not hex_value or hex_value == "0x":
        return None
    raw = hex_value.lower().replace("0x", "").rjust(64, "0")
    addr = "0x" + raw[-40:]
    if int(addr, 16) == 0:
        return None
    return to_checksum_address(addr)


def eth_call_allowance(client: RpcClient, token: str, owner: str, spender: str, block_tag: str = "latest") -> int:
    calldata = ALLOWANCE_SELECTOR + encode_address_word(owner) + encode_address_word(spender)
    result = client.call("eth_call", [{"to": token, "data": calldata}, block_tag])
    return decode_uint256(result)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config_polygon_upgrade_100k.json")
    parser.add_argument("--spender", default=None)
    parser.add_argument("--sample-size", type=int, default=30)
    args = parser.parse_args()

    cfg = load_json(args.config)
    out_dir = Path(cfg.get("output_dir", "data"))
    events = read_jsonl(out_dir / "normalized" / "events.jsonl")
    approvals = read_jsonl(out_dir / "backscan" / "upgrade_spender_approvals.jsonl")

    if not approvals:
        raise SystemExit("No backscan approval candidates found.")

    spender = args.spender
    if not spender:
        spender = Counter(row["spender"] for row in approvals).most_common(1)[0][0]
    spender = to_checksum_address(spender)

    spender_approvals = [row for row in approvals if to_checksum_address(row["spender"]) == spender]
    upgrades = [
        row for row in events
        if row.get("event_type") == "implementation_upgrade"
        and row.get("proxy")
        and to_checksum_address(row["proxy"]) == spender
    ]
    upgrades.sort(key=lambda row: (row["block_number"], row["log_index"]))
    if not upgrades:
        raise SystemExit(f"No upgrade event found for spender {spender}.")

    first_upgrade = upgrades[0]
    first_upgrade_block = int(first_upgrade["block_number"])
    before_upgrade = [row for row in spender_approvals if int(row["block_number"]) < first_upgrade_block]
    after_or_at_upgrade = [row for row in spender_approvals if int(row["block_number"]) >= first_upgrade_block]

    client = RpcClient(cfg["rpc_url"])
    code = client.call("eth_getCode", [spender, "latest"])
    impl_raw = client.call("eth_getStorageAt", [spender, EIP1967_IMPLEMENTATION_SLOT, "latest"])
    current_impl = decode_address_from_storage(impl_raw)

    token_counts = Counter(row["token"] for row in before_upgrade)
    owner_counts = Counter(row["owner"] for row in before_upgrade)

    sampled = []
    seen_pairs = set()
    for row in sorted(before_upgrade, key=lambda item: int(item.get("value") or 0), reverse=True):
        key = (row["token"], row["owner"], row["spender"])
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        sampled.append(row)
        if len(sampled) >= args.sample_size:
            break

    allowance_checks = []
    for row in sampled:
        token = to_checksum_address(row["token"])
        owner = to_checksum_address(row["owner"])
        value = int(row.get("value") or 0)
        current_allowance = eth_call_allowance(client, token, owner, spender, "latest")
        historical_allowance = None
        historical_error = None
        try:
            historical_allowance = eth_call_allowance(client, token, owner, spender, hex(first_upgrade_block))
        except Exception as exc:
            historical_error = str(exc)
        allowance_checks.append({
            "token": token,
            "owner": owner,
            "approval_block": row["block_number"],
            "approval_tx": row["tx_hash"],
            "approval_value": value,
            "allowance_at_upgrade_block": historical_allowance,
            "allowance_at_upgrade_error": historical_error,
            "current_allowance": current_allowance,
            "currently_nonzero": current_allowance > 0,
        })

    result = {
        "spender": spender,
        "candidate_approval_count": len(spender_approvals),
        "candidate_approvals_before_first_upgrade": len(before_upgrade),
        "candidate_approvals_after_or_at_first_upgrade": len(after_or_at_upgrade),
        "unique_owners_before_upgrade": len({row["owner"] for row in before_upgrade}),
        "unique_tokens_before_upgrade": len({row["token"] for row in before_upgrade}),
        "top_tokens_before_upgrade": token_counts.most_common(10),
        "top_owners_before_upgrade": owner_counts.most_common(10),
        "first_upgrade": {
            "block_number": first_upgrade["block_number"],
            "tx_hash": first_upgrade["tx_hash"],
            "proxy": first_upgrade["proxy"],
            "implementation_from_event": first_upgrade.get("implementation"),
        },
        "upgrade_event_count_in_window": len(upgrades),
        "is_contract_now": bool(code and code != "0x"),
        "code_size_hex_chars": max(0, len(code) - 2),
        "eip1967_implementation_latest": current_impl,
        "allowance_sample_size": len(allowance_checks),
        "nonzero_current_allowance_count": sum(1 for row in allowance_checks if row["currently_nonzero"]),
        "allowance_checks": allowance_checks,
    }

    verify_dir = out_dir / "verification"
    verify_dir.mkdir(parents=True, exist_ok=True)
    out_path = verify_dir / f"candidate_{spender.lower()}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
