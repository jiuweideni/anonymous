from pathlib import Path

from .utils import load_json


def write_report(config_path: str) -> Path:
    cfg = load_json(config_path)
    out_dir = Path(cfg.get("output_dir", "data"))
    collection = load_json(out_dir / "collection_summary.json") if (out_dir / "collection_summary.json").exists() else {}
    findings = load_json(out_dir / "results" / "findings.json") if (out_dir / "results" / "findings.json").exists() else {}

    lines = [
        "# Account-Abstraction Authorization Lifecycle Report",
        "",
        "## Scope",
        "",
        f"- Chain ID: {cfg.get('chain_id')}",
        f"- Block range: {cfg.get('from_block')} - {cfg.get('to_block')}",
        f"- EntryPoints: {len(cfg.get('entrypoints', []))}",
        f"- Tracked tokens: {len(cfg.get('tracked_tokens', []))}",
        f"- Permit2 contracts: {len(cfg.get('permit2_addresses', []))}",
        "",
        "## Collection",
        "",
        f"- EntryPoint logs: {collection.get('entrypoint_logs', 0)}",
        f"- ERC-20 Approval logs: {collection.get('approval_logs', 0)}",
        f"- Permit2 Approval logs: {collection.get('permit2_approval_logs', 0)}",
        f"- Upgrade logs: {collection.get('upgrade_logs', 0)}",
        "",
        "## Findings",
        "",
        f"- Total findings: {findings.get('finding_count', 0)}",
    ]

    for finding_type, count in sorted((findings.get("finding_types") or {}).items()):
        lines.append(f"- {finding_type}: {count}")

    lines.extend([
        "",
        "## Top Examples",
        "",
    ])
    for item in (findings.get("findings") or [])[:20]:
        lines.append(f"- `{item.get('type')}` `{item.get('severity')}` subject `{item.get('subject')}`")
        lines.append(f"  reason: {item.get('reason')}")

    report_path = out_dir / "results" / "summary.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path
