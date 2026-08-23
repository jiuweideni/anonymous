import json
from pathlib import Path
from typing import Any, Iterable

from eth_utils import to_checksum_address


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def append_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with p.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalize_address(address: str | None) -> str | None:
    if not address:
        return None
    address = address.lower()
    if address == "0x0000000000000000000000000000000000000000":
        return address
    try:
        return to_checksum_address(address)
    except Exception:
        return address


def topic_to_address(topic: str) -> str:
    return normalize_address("0x" + topic[-40:]) or "0x0000000000000000000000000000000000000000"


def address_to_topic(address: str) -> str:
    normalized = (normalize_address(address) or address).lower()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    return "0x" + normalized.rjust(64, "0")


def hex_to_int(value: str | int | None) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    return int(value, 16)
