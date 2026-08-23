from __future__ import annotations

import argparse
import json
from pathlib import Path


def deduplicate(path: Path, key_fields: list[str]) -> dict[str, int]:
    tmp_path = path.with_suffix(path.suffix + ".dedup.tmp")
    seen: set[tuple[object, ...]] = set()
    total = 0
    kept = 0

    with path.open("r", encoding="utf-8") as src, tmp_path.open("w", encoding="utf-8", newline="\n") as dst:
        for line in src:
            if not line.strip():
                continue
            total += 1
            row = json.loads(line)
            key = tuple(row.get(field) for field in key_fields)
            if key in seen:
                continue
            seen.add(key)
            dst.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            kept += 1

    tmp_path.replace(path)
    return {"total": total, "kept": kept, "removed": total - kept}


def main() -> None:
    parser = argparse.ArgumentParser(description="Deduplicate JSONL rows by selected fields.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--key", nargs="+", default=["tx_hash", "log_index"])
    args = parser.parse_args()

    result = deduplicate(args.path, args.key)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
