import argparse
import json
import sys
from pathlib import Path

from eth_utils import keccak, to_checksum_address

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aa_auth_lifecycle.rpc import RpcClient
from aa_auth_lifecycle.utils import load_json


EIP1967_IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"


def decode_address_from_storage(value: str):
    raw = value.lower().replace("0x", "").rjust(64, "0")
    addr = "0x" + raw[-40:]
    if int(addr, 16) == 0:
        return None
    return to_checksum_address(addr)


def code_info(client: RpcClient, address: str | None):
    if not address:
        return None
    code = client.call("eth_getCode", [address, "latest"])
    if not code or code == "0x":
        return {"address": address, "code_hex_chars": 0, "code_hash": None}
    return {
        "address": address,
        "code_hex_chars": max(0, len(code) - 2),
        "code_hash": "0x" + keccak(bytes.fromhex(code[2:])).hex(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config_polygon_upgrade_100k.json")
    parser.add_argument("--proxy", required=True)
    parser.add_argument("--upgrade-block", type=int, required=True)
    args = parser.parse_args()

    cfg = load_json(args.config)
    client = RpcClient(cfg["rpc_url"])
    proxy = to_checksum_address(args.proxy)

    prev_impl = decode_address_from_storage(
        client.call("eth_getStorageAt", [proxy, EIP1967_IMPLEMENTATION_SLOT, hex(args.upgrade_block - 1)])
    )
    impl_at_upgrade = decode_address_from_storage(
        client.call("eth_getStorageAt", [proxy, EIP1967_IMPLEMENTATION_SLOT, hex(args.upgrade_block)])
    )
    latest_impl = decode_address_from_storage(
        client.call("eth_getStorageAt", [proxy, EIP1967_IMPLEMENTATION_SLOT, "latest"])
    )
    result = {
        "proxy": proxy,
        "upgrade_block": args.upgrade_block,
        "previous_implementation": prev_impl,
        "implementation_at_upgrade_block": impl_at_upgrade,
        "latest_implementation": latest_impl,
        "implementation_changed_at_upgrade": prev_impl != impl_at_upgrade,
        "latest_matches_upgrade": latest_impl == impl_at_upgrade,
        "previous_implementation_code": code_info(client, prev_impl),
        "implementation_at_upgrade_code": code_info(client, impl_at_upgrade),
        "latest_implementation_code": code_info(client, latest_impl),
    }
    out_dir = Path(cfg.get("output_dir", "data")) / "verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"impl_change_{proxy.lower()}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
