from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import networkx as nx

from .utils import append_jsonl, load_json, read_jsonl


@dataclass
class CapabilityEdge:
    chain_id: int
    source: str
    target: str
    relation: str
    block_number: int
    tx_hash: str | None
    attributes: dict[str, Any]


def build_edges(events: list[dict[str, Any]]) -> list[CapabilityEdge]:
    edges: list[CapabilityEdge] = []
    for ev in events:
        event_type = ev.get("event_type")
        if event_type == "erc4337_user_operation":
            account = ev.get("smart_account")
            paymaster = ev.get("paymaster")
            if account and paymaster and paymaster != "0x0000000000000000000000000000000000000000":
                edges.append(CapabilityEdge(
                    chain_id=int(ev["chain_id"]),
                    source=paymaster,
                    target=account,
                    relation="sponsored_user_operation",
                    block_number=int(ev["block_number"]),
                    tx_hash=ev.get("tx_hash"),
                    attributes={
                        "success": ev.get("success"),
                        "actual_gas_cost": ev.get("actual_gas_cost"),
                        "actual_gas_used": ev.get("actual_gas_used"),
                        "nonce": ev.get("nonce"),
                    },
                ))
        elif event_type in {"erc20_approval", "permit2_approval"}:
            owner = ev.get("owner")
            spender = ev.get("spender")
            token = ev.get("token")
            if owner and spender and token:
                edges.append(CapabilityEdge(
                    chain_id=int(ev["chain_id"]),
                    source=owner,
                    target=spender,
                    relation=event_type,
                    block_number=int(ev["block_number"]),
                    tx_hash=ev.get("tx_hash"),
                    attributes={
                        "token": token,
                        "value": int(ev.get("value") or 0),
                    },
                ))
        elif event_type == "implementation_upgrade":
            proxy = ev.get("proxy")
            implementation = ev.get("implementation")
            if proxy and implementation:
                edges.append(CapabilityEdge(
                    chain_id=int(ev["chain_id"]),
                    source=proxy,
                    target=implementation,
                    relation="implementation_upgrade",
                    block_number=int(ev["block_number"]),
                    tx_hash=ev.get("tx_hash"),
                    attributes={},
                ))
    return edges


def build_networkx(edges: list[CapabilityEdge]) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    for edge in edges:
        graph.add_node(edge.source)
        graph.add_node(edge.target)
        graph.add_edge(
            edge.source,
            edge.target,
            relation=edge.relation,
            chain_id=edge.chain_id,
            block_number=edge.block_number,
            tx_hash=edge.tx_hash,
            **edge.attributes,
        )
    return graph


def materialize_graph(config_path: str) -> dict[str, int]:
    cfg = load_json(config_path)
    out_dir = Path(cfg.get("output_dir", "data"))
    events = read_jsonl(out_dir / "normalized" / "events.jsonl")
    edges = build_edges(events)
    edge_path = out_dir / "results" / "capability_edges.jsonl"
    if edge_path.exists():
        edge_path.unlink()
    append_jsonl(edge_path, [asdict(edge) for edge in edges])
    graph = build_networkx(edges)
    return {
        "events": len(events),
        "edges": len(edges),
        "nodes": graph.number_of_nodes(),
    }
