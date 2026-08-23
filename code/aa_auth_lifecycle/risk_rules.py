from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .constants import UINT256_MAX
from .utils import load_json, read_jsonl, write_json


def _finding(
    finding_type: str,
    severity: str,
    subject: str,
    evidence: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "type": finding_type,
        "severity": severity,
        "subject": subject,
        "reason": reason,
        "evidence": evidence,
    }


def detect_unlimited_approvals(events: list[dict[str, Any]], large_threshold: int) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("event_type") not in {"erc20_approval", "permit2_approval"}:
            continue
        value = int(ev.get("value") or 0)
        if value == UINT256_MAX:
            findings.append(_finding(
                "unlimited_approval",
                "high",
                ev.get("owner") or "",
                {
                    "spender": ev.get("spender"),
                    "token": ev.get("token"),
                    "block_number": ev.get("block_number"),
                    "tx_hash": ev.get("tx_hash"),
                    "event_type": ev.get("event_type"),
                },
                "Owner grants uint256 max allowance to a spender.",
            ))
        elif value >= large_threshold:
            findings.append(_finding(
                "large_approval",
                "medium",
                ev.get("owner") or "",
                {
                    "spender": ev.get("spender"),
                    "token": ev.get("token"),
                    "value": value,
                    "block_number": ev.get("block_number"),
                    "tx_hash": ev.get("tx_hash"),
                    "event_type": ev.get("event_type"),
                },
                "Owner grants an allowance larger than the configured threshold.",
            ))
    return findings


def detect_paymaster_concentration(events: list[dict[str, Any]], min_count: int) -> list[dict[str, Any]]:
    by_paymaster = Counter()
    accounts_by_paymaster: dict[str, set[str]] = defaultdict(set)
    for ev in events:
        if ev.get("event_type") != "erc4337_user_operation":
            continue
        paymaster = ev.get("paymaster")
        account = ev.get("smart_account")
        if not paymaster or paymaster == "0x0000000000000000000000000000000000000000":
            continue
        by_paymaster[paymaster] += 1
        if account:
            accounts_by_paymaster[paymaster].add(account)

    findings = []
    for paymaster, count in by_paymaster.items():
        if count >= min_count:
            findings.append(_finding(
                "paymaster_concentration",
                "medium",
                paymaster,
                {
                    "user_operation_count": count,
                    "unique_smart_accounts": len(accounts_by_paymaster[paymaster]),
                },
                "A paymaster sponsors many UserOperations in the analysis window.",
            ))
    return findings


def detect_smart_account_spenders(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    smart_accounts = {
        ev.get("smart_account")
        for ev in events
        if ev.get("event_type") == "erc4337_user_operation" and ev.get("smart_account")
    }
    findings = []
    for ev in events:
        if ev.get("event_type") not in {"erc20_approval", "permit2_approval"}:
            continue
        owner = ev.get("owner")
        if owner in smart_accounts and int(ev.get("value") or 0) > 0:
            findings.append(_finding(
                "smart_account_token_authorization",
                "info",
                owner,
                {
                    "spender": ev.get("spender"),
                    "token": ev.get("token"),
                    "value": int(ev.get("value") or 0),
                    "block_number": ev.get("block_number"),
                    "tx_hash": ev.get("tx_hash"),
                    "event_type": ev.get("event_type"),
                },
                "A known smart account grants token spending capability.",
            ))
    return findings


def detect_upgrade_induced_authorization_drift(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    approvals = [
        ev for ev in events
        if ev.get("event_type") in {"erc20_approval", "permit2_approval"}
        and int(ev.get("value") or 0) > 0
    ]
    upgrades_by_proxy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in events:
        if ev.get("event_type") == "implementation_upgrade" and ev.get("proxy"):
            upgrades_by_proxy[ev["proxy"]].append(ev)

    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, int, str]] = set()
    for approval in approvals:
        approval_block = int(approval.get("block_number") or 0)
        owner = approval.get("owner")
        spender = approval.get("spender")
        candidates = [
            ("owner_upgrade_after_authorization", owner, "The authorizing account upgraded after granting token capability."),
            ("spender_upgrade_after_authorization", spender, "The authorized spender upgraded after receiving token capability."),
        ]
        for drift_type, proxy, reason in candidates:
            if not proxy:
                continue
            for upgrade in upgrades_by_proxy.get(proxy, []):
                upgrade_block = int(upgrade.get("block_number") or 0)
                if upgrade_block <= approval_block:
                    continue
                key = (
                    drift_type,
                    approval.get("tx_hash") or "",
                    approval_block,
                    upgrade_block,
                    proxy,
                )
                if key in seen:
                    continue
                seen.add(key)
                findings.append(_finding(
                    drift_type,
                    "high" if drift_type == "spender_upgrade_after_authorization" else "medium",
                    proxy,
                    {
                        "approval": {
                            "owner": owner,
                            "spender": spender,
                            "token": approval.get("token"),
                            "value": int(approval.get("value") or 0),
                            "block_number": approval_block,
                            "tx_hash": approval.get("tx_hash"),
                            "event_type": approval.get("event_type"),
                        },
                        "upgrade": {
                            "proxy": proxy,
                            "implementation": upgrade.get("implementation"),
                            "block_number": upgrade_block,
                            "tx_hash": upgrade.get("tx_hash"),
                        },
                    },
                    reason,
                ))
    return findings


def analyze_risks(config_path: str) -> dict[str, Any]:
    cfg = load_json(config_path)
    out_dir = Path(cfg.get("output_dir", "data"))
    thresholds = cfg.get("risk_thresholds", {})
    large_threshold = int(thresholds.get("large_approval_amount", "1000000000000000000000000"))
    paymaster_min_count = int(thresholds.get("paymaster_userop_min_count", 100))

    events = read_jsonl(out_dir / "normalized" / "events.jsonl")
    findings = []
    findings.extend(detect_unlimited_approvals(events, large_threshold))
    findings.extend(detect_paymaster_concentration(events, paymaster_min_count))
    findings.extend(detect_smart_account_spenders(events))
    findings.extend(detect_upgrade_induced_authorization_drift(events))

    summary = {
        "event_count": len(events),
        "finding_count": len(findings),
        "finding_types": dict(Counter(f["type"] for f in findings)),
        "findings": findings,
    }
    write_json(out_dir / "results" / "findings.json", summary)
    return summary
