from collections import Counter
from pathlib import Path
from typing import Any
import time

from tqdm import tqdm

from .constants import TOPIC_ERC20_APPROVAL
from .normalizer import normalize_approval
from .rpc import RpcClient
from .utils import address_to_topic, append_jsonl, load_json, read_jsonl, write_json


QUOTA_ERROR_PATTERNS = (
    "quota",
    "credit",
    "credits",
    "daily request count",
    "daily limit",
    "rate limit",
    "rate exceeded",
    "too many requests",
    "429",
    "capacity",
)


def _is_quota_or_rate_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(pattern in text for pattern in QUOTA_ERROR_PATTERNS)


def _ranges_backward(from_block: int, to_block: int, chunk_size: int):
    end = to_block
    while end >= from_block:
        start = max(from_block, end - chunk_size + 1)
        yield start, end
        end = start - 1


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return load_json(path)
    except Exception:
        return {}


def _load_upgrade_proxies(events_path: Path) -> dict[str, int]:
    proxies: dict[str, int] = {}
    for ev in read_jsonl(events_path):
        if ev.get("event_type") != "implementation_upgrade":
            continue
        proxy = ev.get("proxy")
        block = int(ev.get("block_number") or 0)
        if not proxy or not block:
            continue
        proxies[proxy] = min(block, proxies.get(proxy, block))
    return proxies


def backscan_upgrade_approvals(config_path: str) -> dict[str, Any]:
    cfg = load_json(config_path)
    out_dir = Path(cfg.get("output_dir", "data"))
    backscan_cfg = cfg.get("backscan", {})
    result_dir = out_dir / "backscan"
    raw_path = result_dir / "upgrade_spender_approvals.raw.jsonl"
    normalized_path = result_dir / "upgrade_spender_approvals.jsonl"
    findings_path = result_dir / "upgrade_drift_candidates.json"
    state_path = result_dir / "backscan_state.json"
    quota_marker_path = result_dir / "quota_exhausted.json"
    result_dir.mkdir(parents=True, exist_ok=True)

    events_path = out_dir / "normalized" / "events.jsonl"
    proxies = _load_upgrade_proxies(events_path)
    if not proxies:
        summary = {"status": "empty", "message": "No implementation_upgrade events found."}
        write_json(findings_path, summary)
        return summary

    tokens = [x["address"] for x in cfg.get("tracked_tokens", [])]
    client = RpcClient(cfg["rpc_url"])
    chain_id = int(cfg["chain_id"])
    history_blocks = int(backscan_cfg.get("history_blocks", 200000))
    chunk_size = int(backscan_cfg.get("chunk_size", 5000))
    max_proxies = int(backscan_cfg.get("max_proxies", 0))
    resume = bool(backscan_cfg.get("resume", True))
    all_tokens = bool(backscan_cfg.get("all_tokens", False))
    request_delay_seconds = float(backscan_cfg.get("request_delay_seconds", 0))
    max_requests_per_run = int(backscan_cfg.get("max_requests_per_run", 0))
    address_filter = None if all_tokens else tokens
    request_count = 0

    proxy_items = sorted(proxies.items(), key=lambda item: item[1])
    if max_proxies > 0:
        proxy_items = proxy_items[:max_proxies]

    state = _load_state(state_path) if resume else {}
    start_proxy_index = int(state.get("proxy_index", 0))
    start_next_to_block = state.get("next_to_block")
    if not resume:
        for p in (raw_path, normalized_path, findings_path, quota_marker_path):
            if p.exists():
                p.unlink()
    if quota_marker_path.exists():
        quota_marker_path.unlink()

    summary = {
        "status": "running",
        "proxy_count": len(proxy_items),
        "history_blocks": history_blocks,
        "chunk_size": chunk_size,
        "all_tokens": all_tokens,
        "raw_logs": 0,
        "normalized_approvals": 0,
    }
    candidates: list[dict[str, Any]] = []

    outer = tqdm(
        list(enumerate(proxy_items[start_proxy_index:], start=start_proxy_index)),
        desc="Backscanning upgrade proxies",
    )
    for proxy_index, (proxy, upgrade_block) in outer:
        scan_to = int(start_next_to_block) if start_next_to_block and proxy_index == start_proxy_index else upgrade_block - 1
        scan_from = max(0, upgrade_block - history_blocks)
        spender_topic = address_to_topic(proxy)

        for start, end in _ranges_backward(scan_from, scan_to, chunk_size):
            try:
                logs = client.get_logs(address_filter, [TOPIC_ERC20_APPROVAL, None, spender_topic], start, end)
                if request_delay_seconds > 0:
                    time.sleep(request_delay_seconds)
            except Exception as exc:
                if _is_quota_or_rate_error(exc):
                    marker = {
                        "status": "quota_or_rate_limited",
                        "proxy": proxy,
                        "proxy_index": proxy_index,
                        "failed_range": [start, end],
                        "next_to_block": end,
                        "error": str(exc),
                    }
                    write_json(quota_marker_path, marker)
                    write_json(state_path, marker)
                    summary.update(marker)
                    return summary
                raise

            summary["raw_logs"] += append_jsonl(raw_path, logs)
            normalized = [normalize_approval(log, chain_id, "historical_approval_to_upgraded_spender") for log in logs]
            summary["normalized_approvals"] += append_jsonl(normalized_path, normalized)
            request_count += 1
            for approval in normalized:
                candidates.append({
                    "type": "historical_approval_to_upgraded_spender",
                    "severity": "high",
                    "spender": proxy,
                    "upgrade_block": upgrade_block,
                    "approval": approval,
                })

            write_json(state_path, {
                "status": "running",
                "proxy_index": proxy_index,
                "proxy": proxy,
                "next_to_block": start - 1,
                "last_completed_range": [start, end],
            })
            if max_requests_per_run > 0 and request_count >= max_requests_per_run:
                summary.update({
                    "status": "paused",
                    "reason": "max_requests_per_run",
                    "proxy": proxy,
                    "proxy_index": proxy_index,
                    "next_to_block": start - 1,
                    "requests_this_run": request_count,
                })
                write_json(state_path, summary)
                return summary

        start_next_to_block = None
        write_json(state_path, {
            "status": "running",
            "proxy_index": proxy_index + 1,
            "next_to_block": None,
        })

    existing_candidates = []
    if normalized_path.exists():
        for approval in read_jsonl(normalized_path):
            spender = approval.get("spender")
            if spender in proxies and int(approval.get("block_number") or 0) < proxies[spender]:
                existing_candidates.append({
                    "type": "historical_approval_to_upgraded_spender",
                    "severity": "high",
                    "spender": spender,
                    "upgrade_block": proxies[spender],
                    "approval": approval,
                })

    by_spender = Counter(item["spender"] for item in existing_candidates)
    result = {
        "status": "complete",
        "proxy_count": len(proxy_items),
        "history_blocks": history_blocks,
        "all_tokens": all_tokens,
        "candidate_count": len(existing_candidates),
        "spender_count": len(by_spender),
        "top_spenders": by_spender.most_common(20),
        "candidates": existing_candidates[:5000],
    }
    write_json(findings_path, result)
    write_json(state_path, {"status": "complete", "proxy_index": len(proxy_items)})
    return result
