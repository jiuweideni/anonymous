from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .utils import load_json, read_jsonl


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return load_json(path)


def _file_info(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "bytes": stat.st_size,
        "modified": stat.st_mtime,
    }


def _approval_summary(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    if not rows:
        return {
            "approval_count": 0,
            "spender_count": 0,
            "owner_count": 0,
            "token_count": 0,
            "top_spenders": [],
        }

    spenders = Counter(row.get("spender") for row in rows if row.get("spender"))
    owners = {row.get("owner") for row in rows if row.get("owner")}
    tokens = {row.get("token") for row in rows if row.get("token")}
    return {
        "approval_count": len(rows),
        "spender_count": len(spenders),
        "owner_count": len(owners),
        "token_count": len(tokens),
        "top_spenders": [
            {"spender": spender, "approvals": count}
            for spender, count in spenders.most_common(20)
        ],
    }


def experiment_status(config_path: str) -> dict[str, Any]:
    cfg = load_json(config_path)
    out_dir = Path(cfg.get("output_dir", "data"))
    backscan_dir = out_dir / "backscan"
    verification_dir = out_dir / "verification"
    summary_path = verification_dir / "trace_experiment_summary.json"
    approval_path = backscan_dir / "upgrade_spender_approvals.jsonl"
    quota_marker_path = backscan_dir / "quota_exhausted.json"

    trace_summary = _load_json_if_exists(summary_path) or {}
    status = {
        "config": {
            "path": config_path,
            "chain_id": cfg.get("chain_id"),
            "from_block": cfg.get("from_block"),
            "to_block": cfg.get("to_block"),
            "output_dir": str(out_dir),
            "backscan_history_blocks": (cfg.get("backscan") or {}).get("history_blocks"),
            "backscan_all_tokens": (cfg.get("backscan") or {}).get("all_tokens"),
        },
        "files": {
            "collection_summary": _file_info(out_dir / "collection_summary.json"),
            "normalized_events": _file_info(out_dir / "normalized" / "events.jsonl"),
            "backscan_state": _file_info(backscan_dir / "backscan_state.json"),
            "backscan_approvals": _file_info(approval_path),
            "trace_summary_json": _file_info(summary_path),
            "trace_summary_markdown": _file_info(verification_dir / "trace_experiment_summary.md"),
        },
        "backscan": {
            "state": _load_json_if_exists(backscan_dir / "backscan_state.json"),
            "quota_marker": _load_json_if_exists(quota_marker_path),
            **_approval_summary(approval_path),
        },
        "trace": {
            "summary_available": bool(trace_summary),
            "trace_positive_spender_count": trace_summary.get("trace_positive_spender_count"),
            "global_transfer_from_match_count": trace_summary.get("global_transfer_from_match_count"),
            "global_matched_tx_count": trace_summary.get("global_matched_tx_count"),
        },
        "next_outputs": {
            "summary_json": str(summary_path),
            "summary_markdown": str(verification_dir / "trace_experiment_summary.md"),
        },
    }
    return status
