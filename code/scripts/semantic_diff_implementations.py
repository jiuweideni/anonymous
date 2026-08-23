#!/usr/bin/env python
"""Compare previous and upgraded implementations for authorization-relevant drift."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import requests
from eth_utils import keccak

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aa_auth_lifecycle.rpc import RpcClient
from aa_auth_lifecycle.utils import load_json


ERC20_SELECTORS = {
    "0x23b872dd": "transferFrom(address,address,uint256)",
    "0xa9059cbb": "transfer(address,uint256)",
    "0x095ea7b3": "approve(address,uint256)",
    "0xdd62ed3e": "allowance(address,address)",
    "0x70a08231": "balanceOf(address)",
}

AUTH_RELEVANT_SELECTORS = {
    **ERC20_SELECTORS,
    "0xb61d27f6": "execute(address,uint256,bytes)",
    "0x1cff79cd": "executeBatch(address[],uint256[],bytes[])",
    "0xac9650d8": "multicall(bytes[])",
    "0x2e1a7d4d": "withdraw(uint256)",
    "0x3ccfd60b": "withdraw()",
    "0x4e71d92d": "claim()",
    "0x8da5cb5b": "owner()",
    "0xf2fde38b": "transferOwnership(address)",
    "0x715018a6": "renounceOwnership()",
    "0x3659cfe6": "upgradeTo(address)",
    "0x4f1ef286": "upgradeToAndCall(address,bytes)",
}

OPCODES = {
    0x31: "BALANCE",
    0x3B: "EXTCODESIZE",
    0x3C: "EXTCODECOPY",
    0x3F: "EXTCODEHASH",
    0x54: "SLOAD",
    0x55: "SSTORE",
    0xF0: "CREATE",
    0xF1: "CALL",
    0xF2: "CALLCODE",
    0xF4: "DELEGATECALL",
    0xF5: "CREATE2",
    0xFA: "STATICCALL",
    0xFD: "REVERT",
    0xFF: "SELFDESTRUCT",
}


def read_trace_summary(out_dir: Path) -> dict[str, Any]:
    path = out_dir / "verification" / "trace_experiment_summary.json"
    if not path.exists():
        raise SystemExit(f"Missing trace summary: {path}")
    return load_json(path)


def code_hash(code: str) -> str | None:
    if not code or code == "0x":
        return None
    return "0x" + keccak(bytes.fromhex(code[2:])).hex()


def bytecode_bytes(code: str) -> bytes:
    if not code or code == "0x":
        return b""
    return bytes.fromhex(code[2:])


def extract_push4_selectors(data: bytes) -> Counter[str]:
    selectors: Counter[str] = Counter()
    i = 0
    while i < len(data):
        opcode = data[i]
        if opcode == 0x63 and i + 4 < len(data):
            selectors["0x" + data[i + 1 : i + 5].hex()] += 1
            i += 5
            continue
        if 0x60 <= opcode <= 0x7F:
            i += 1 + (opcode - 0x5F)
        else:
            i += 1
    return selectors


def count_opcodes(data: bytes) -> Counter[str]:
    counts: Counter[str] = Counter()
    i = 0
    while i < len(data):
        opcode = data[i]
        name = OPCODES.get(opcode)
        if name:
            counts[name] += 1
        if 0x60 <= opcode <= 0x7F:
            i += 1 + (opcode - 0x5F)
        else:
            i += 1
    return counts


def analyze_code(address: str | None, code: str) -> dict[str, Any]:
    data = bytecode_bytes(code)
    selectors = extract_push4_selectors(data)
    opcodes = count_opcodes(data)
    known = {
        selector: {"count": count, "name": AUTH_RELEVANT_SELECTORS.get(selector)}
        for selector, count in selectors.items()
        if selector in AUTH_RELEVANT_SELECTORS
    }
    erc20 = {
        selector: {"count": count, "name": ERC20_SELECTORS[selector]}
        for selector, count in selectors.items()
        if selector in ERC20_SELECTORS
    }
    return {
        "address": address,
        "code_bytes": len(data),
        "code_hash": code_hash(code),
        "push4_selector_count": sum(selectors.values()),
        "unique_push4_selectors": len(selectors),
        "auth_relevant_selectors": known,
        "erc20_selectors": erc20,
        "opcode_counts": {name: opcodes.get(name, 0) for name in sorted(OPCODES.values())},
    }


def diff_analysis(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_selectors = set(before["auth_relevant_selectors"])
    after_selectors = set(after["auth_relevant_selectors"])
    before_erc20 = set(before["erc20_selectors"])
    after_erc20 = set(after["erc20_selectors"])
    opcode_delta = {
        name: int(after["opcode_counts"].get(name, 0)) - int(before["opcode_counts"].get(name, 0))
        for name in sorted(set(before["opcode_counts"]) | set(after["opcode_counts"]))
    }
    return {
        "code_hash_changed": before.get("code_hash") != after.get("code_hash"),
        "code_size_delta_bytes": int(after.get("code_bytes") or 0) - int(before.get("code_bytes") or 0),
        "added_auth_relevant_selectors": sorted(after_selectors - before_selectors),
        "removed_auth_relevant_selectors": sorted(before_selectors - after_selectors),
        "added_erc20_selectors": sorted(after_erc20 - before_erc20),
        "removed_erc20_selectors": sorted(before_erc20 - after_erc20),
        "opcode_delta": opcode_delta,
        "external_call_opcode_delta": {
            name: opcode_delta.get(name, 0)
            for name in ("CALL", "CALLCODE", "DELEGATECALL", "STATICCALL")
        },
        "risk_signals": risk_signals(before, after, opcode_delta, before_erc20, after_erc20),
    }


def risk_signals(
    before: dict[str, Any],
    after: dict[str, Any],
    opcode_delta: dict[str, int],
    before_erc20: set[str],
    after_erc20: set[str],
) -> list[str]:
    signals: list[str] = []
    if before.get("code_hash") != after.get("code_hash"):
        signals.append("implementation_bytecode_changed")
    if "0x23b872dd" in after_erc20:
        signals.append("post_upgrade_bytecode_contains_transferFrom_selector")
    if "0x23b872dd" in after_erc20 and "0x23b872dd" not in before_erc20:
        signals.append("transferFrom_selector_added_after_upgrade")
    if opcode_delta.get("CALL", 0) > 0:
        signals.append("external_CALL_count_increased")
    if opcode_delta.get("DELEGATECALL", 0) > 0:
        signals.append("DELEGATECALL_count_increased")
    if int(after["opcode_counts"].get("SSTORE", 0)) > int(before["opcode_counts"].get("SSTORE", 0)):
        signals.append("storage_write_count_increased")
    return signals


def sourcify_metadata(chain_id: int, address: str, timeout: int = 10) -> dict[str, Any] | None:
    base = "https://repo.sourcify.dev/contracts"
    for match_type in ("full_match", "partial_match"):
        url = f"{base}/{match_type}/{chain_id}/{address}/metadata.json"
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                body = response.json()
                return {
                    "match_type": match_type,
                    "contract_name": body.get("settings", {}).get("compilationTarget", {}),
                    "compiler": body.get("compiler", {}),
                    "source_paths": sorted((body.get("sources") or {}).keys()),
                }
        except Exception:
            continue
    return None


def source_lookup(chain_id: int, addresses: list[str]) -> dict[str, Any]:
    return {address: sourcify_metadata(chain_id, address) for address in addresses if address}


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    source_checked = 0
    source_matched = 0
    for row in result["spenders"]:
        lookup = row.get("source_lookup") or {}
        source_checked += len(lookup)
        source_matched += sum(1 for value in lookup.values() if value)
    lines.append("# Implementation Semantic Diff")
    lines.append("")
    lines.append(f"- chain: {result['config']['chain_id']}")
    lines.append(f"- output_dir: `{result['config']['output_dir']}`")
    lines.append(f"- analyzed spenders: {len(result['spenders'])}")
    if source_checked:
        lines.append(f"- Sourcify source matches: {source_matched} / {source_checked}")
    lines.append("")
    lines.append("| Spender | Matches | Code changed | Size delta | Added ERC20 selectors | External call delta | Risk signals |")
    lines.append("| --- | ---: | --- | ---: | --- | --- | --- |")
    for row in result["spenders"]:
        spender = row["spender"]
        short = f"{spender[:6]}...{spender[-4:]}"
        diff = row["diff"]
        call_delta = diff["external_call_opcode_delta"]
        call_text = ", ".join(f"{k}:{v:+d}" for k, v in call_delta.items() if v)
        if not call_text:
            call_text = "0"
        added = ", ".join(diff["added_erc20_selectors"]) or "--"
        signals = ", ".join(diff["risk_signals"]) or "--"
        lines.append(
            f"| `{short}` | {row['transfer_from_match_count']} | {diff['code_hash_changed']} | "
            f"{diff['code_size_delta_bytes']} | `{added}` | {call_text} | {signals} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("The bytecode analysis extracts PUSH4 constants as candidate function selectors and counts authorization-relevant opcodes. Selector presence is conservative evidence: it indicates that a selector appears in bytecode, not by itself that the selector is reachable on every execution path.")
    if source_checked and source_matched == 0:
        lines.append("")
        lines.append("Sourcify did not return source metadata for the analyzed implementation addresses, so this report remains bytecode-level rather than source-level.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config_polygon_upgrade_100k.json")
    parser.add_argument("--rpc-url", default=None)
    parser.add_argument("--trace-positive-only", action="store_true", default=True)
    parser.add_argument("--include-trace-negative", action="store_false", dest="trace_positive_only")
    parser.add_argument("--source-lookup", action="store_true")
    args = parser.parse_args()

    cfg = load_json(args.config)
    if args.rpc_url:
        cfg["rpc_url"] = args.rpc_url
    out_dir = Path(cfg.get("output_dir", "data"))
    summary = read_trace_summary(out_dir)
    chain_id = int(cfg["chain_id"])
    client = RpcClient(cfg["rpc_url"], timeout=45, retries=4)

    rows: list[dict[str, Any]] = []
    for spender in summary.get("spenders", []):
        if args.trace_positive_only and int(spender.get("transfer_from_match_count") or 0) <= 0:
            continue
        previous_impl = spender.get("previous_implementation")
        upgraded_impl = spender.get("implementation_at_upgrade_block") or spender.get("latest_implementation")
        if not previous_impl or not upgraded_impl:
            continue
        previous_code = client.call("eth_getCode", [previous_impl, "latest"])
        upgraded_code = client.call("eth_getCode", [upgraded_impl, "latest"])
        before = analyze_code(previous_impl, previous_code)
        after = analyze_code(upgraded_impl, upgraded_code)
        item = {
            "spender": spender["spender"],
            "first_upgrade_block": spender.get("first_upgrade_block"),
            "transfer_from_match_count": int(spender.get("transfer_from_match_count") or 0),
            "previous_implementation": previous_impl,
            "upgraded_implementation": upgraded_impl,
            "before": before,
            "after": after,
            "diff": diff_analysis(before, after),
        }
        if args.source_lookup:
            item["source_lookup"] = source_lookup(chain_id, [previous_impl, upgraded_impl])
        rows.append(item)

    result = {
        "config": {
            "chain_id": chain_id,
            "from_block": cfg.get("from_block"),
            "to_block": cfg.get("to_block"),
            "output_dir": cfg.get("output_dir"),
        },
        "spenders": rows,
    }
    verify_dir = out_dir / "verification"
    verify_dir.mkdir(parents=True, exist_ok=True)
    json_path = verify_dir / "implementation_semantic_diff.json"
    md_path = verify_dir / "implementation_semantic_diff.md"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps({"json_path": str(json_path), "markdown_path": str(md_path), "spenders": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
