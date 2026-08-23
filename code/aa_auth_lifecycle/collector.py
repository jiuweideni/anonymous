from pathlib import Path
from typing import Any

from tqdm import tqdm

from .constants import TOPIC_ERC20_APPROVAL, TOPIC_UPGRADED, TOPIC_USER_OPERATION_EVENT
from .rpc import RpcClient
from .utils import append_jsonl, load_json, normalize_address, write_json


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


def _ranges(from_block: int, to_block: int, chunk_size: int):
    start = from_block
    while start <= to_block:
        end = min(start + chunk_size - 1, to_block)
        yield start, end
        start = end + 1


def _is_quota_or_rate_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(pattern in text for pattern in QUOTA_ERROR_PATTERNS)


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return load_json(path)
    except Exception:
        return {}


def _event_paths(raw_dir: Path) -> dict[str, Path]:
    return {
        "entrypoint": raw_dir / "entrypoint_userops.jsonl",
        "approval": raw_dir / "erc20_approvals.jsonl",
        "permit2": raw_dir / "permit2_approvals.jsonl",
        "upgrade": raw_dir / "upgrades.jsonl",
    }


def collect(config_path: str) -> dict[str, Any]:
    cfg = load_json(config_path)
    out_dir = Path(cfg.get("output_dir", "data"))
    raw_dir = out_dir / "raw_logs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    state_path = out_dir / "collection_state.json"
    quota_marker_path = out_dir / "quota_exhausted.json"

    client = RpcClient(cfg["rpc_url"])
    from_block = int(cfg["from_block"])
    to_block = int(cfg["to_block"])
    chunk_size = int(cfg.get("chunk_size", 2000))
    resume = bool(cfg.get("resume_collection", True))

    entrypoints = [normalize_address(x["address"]) for x in cfg.get("entrypoints", [])]
    tokens = [normalize_address(x["address"]) for x in cfg.get("tracked_tokens", [])]
    permit2 = [normalize_address(x["address"]) for x in cfg.get("permit2_addresses", [])]

    state = _load_state(state_path) if resume else {}
    run_from_block = max(from_block, int(state.get("next_block", from_block)))

    summary = {
        "status": "running",
        "from_block": from_block,
        "to_block": to_block,
        "run_from_block": run_from_block,
        "entrypoint_logs": 0,
        "approval_logs": 0,
        "permit2_approval_logs": 0,
        "upgrade_logs": 0,
        "completed_ranges": int(state.get("completed_ranges", 0)),
    }

    paths = _event_paths(raw_dir)
    if not resume:
        for p in paths.values():
            if p.exists():
                p.unlink()
        if quota_marker_path.exists():
            quota_marker_path.unlink()

    if quota_marker_path.exists():
        quota_marker_path.unlink()

    if run_from_block > to_block:
        summary["status"] = "complete"
        summary["message"] = "Collection already complete for configured range."
        write_json(out_dir / "collection_summary.json", summary)
        return summary

    ranges = list(_ranges(run_from_block, to_block, chunk_size))
    for start, end in tqdm(ranges, desc="Collecting logs"):
        try:
            range_logs: dict[str, list[dict[str, Any]]] = {
                "entrypoint": [],
                "approval": [],
                "permit2": [],
                "upgrade": [],
            }
            if entrypoints:
                range_logs["entrypoint"] = client.get_logs(entrypoints, [TOPIC_USER_OPERATION_EVENT], start, end)

            if tokens:
                range_logs["approval"] = client.get_logs(tokens, [TOPIC_ERC20_APPROVAL], start, end)

            if permit2:
                range_logs["permit2"] = client.get_logs(permit2, [TOPIC_ERC20_APPROVAL], start, end)

            if cfg.get("collect_all_upgrades", True):
                range_logs["upgrade"] = client.get_logs(None, [TOPIC_UPGRADED], start, end)
        except Exception as exc:
            if _is_quota_or_rate_error(exc):
                marker = {
                    "status": "quota_or_rate_limited",
                    "failed_range": [start, end],
                    "next_block": start,
                    "error": str(exc),
                }
                write_json(quota_marker_path, marker)
                state.update({
                    "status": "quota_or_rate_limited",
                    "next_block": start,
                    "to_block": to_block,
                    "last_error": str(exc),
                })
                write_json(state_path, state)
                summary.update(marker)
                write_json(out_dir / "collection_summary.json", summary)
                return summary
            raise

        summary["entrypoint_logs"] += append_jsonl(paths["entrypoint"], range_logs["entrypoint"])
        summary["approval_logs"] += append_jsonl(paths["approval"], range_logs["approval"])
        summary["permit2_approval_logs"] += append_jsonl(paths["permit2"], range_logs["permit2"])
        summary["upgrade_logs"] += append_jsonl(paths["upgrade"], range_logs["upgrade"])

        state.update({
            "status": "running",
            "from_block": from_block,
            "to_block": to_block,
            "next_block": end + 1,
            "last_completed_range": [start, end],
            "completed_ranges": int(state.get("completed_ranges", 0)) + 1,
        })
        summary["completed_ranges"] = int(state["completed_ranges"])
        write_json(state_path, state)

    state.update({
        "status": "complete",
        "next_block": to_block + 1,
        "to_block": to_block,
    })
    write_json(state_path, state)
    summary["status"] = "complete"
    write_json(out_dir / "collection_summary.json", summary)
    return summary
