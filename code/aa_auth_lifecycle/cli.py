import argparse
import json

from .collector import collect
from .backscan import backscan_upgrade_approvals
from .graph import materialize_graph
from .normalizer import normalize
from .reporter import write_report
from .risk_rules import analyze_risks
from .status import experiment_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze account-abstraction authorization lifecycle risks."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("collect", "normalize", "graph", "risks", "analyze", "report", "backscan", "status"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", default="config.json")

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "collect":
        result = collect(args.config)
    elif args.command == "normalize":
        result = normalize(args.config)
    elif args.command == "graph":
        result = materialize_graph(args.config)
    elif args.command == "risks":
        result = analyze_risks(args.config)
    elif args.command == "analyze":
        result = {
            "normalized": normalize(args.config),
            "graph": materialize_graph(args.config),
            "risks": analyze_risks(args.config),
        }
    elif args.command == "report":
        result = {"report": str(write_report(args.config))}
    elif args.command == "backscan":
        result = backscan_upgrade_approvals(args.config)
    elif args.command == "status":
        result = experiment_status(args.config)
    else:
        raise ValueError(args.command)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
