# DriftGuard Prototype Runbook

This runbook records the current experiment workflow without changing any detection logic or existing result semantics.

## Current Dataset

- Config: `configs/config_polygon_upgrade_100k.json`
- Output directory: `../experiments/data_polygon_upgrade_100k`
- Chain: Polygon, chain id `137`
- Discovery window: blocks `90787373` to `90887373`
- Historical approval backscan: `200000` blocks before each upgraded proxy

## Read-Only Status

Use this command to inspect progress and key outputs. It only reads files.

```powershell
python -m aa_auth_lifecycle.cli status --config configs\config_polygon_upgrade_100k.json
```

Important fields:

- `backscan.state`: whether the backscan is complete or resumable.
- `backscan.approval_count`: historical approvals to upgraded spenders.
- `backscan.top_spenders`: largest upgraded spenders by historical approval count.
- `trace.trace_positive_spender_count`: spenders with trace-confirmed allowance use.
- `trace.global_transfer_from_match_count`: matched post-upgrade `transferFrom` calls.

## Main Workflow

The full pipeline is:

```powershell
python -m aa_auth_lifecycle.cli collect --config configs\config_polygon_upgrade_100k.json
python -m aa_auth_lifecycle.cli normalize --config configs\config_polygon_upgrade_100k.json
python -m aa_auth_lifecycle.cli graph --config configs\config_polygon_upgrade_100k.json
python -m aa_auth_lifecycle.cli risks --config configs\config_polygon_upgrade_100k.json
python -m aa_auth_lifecycle.cli backscan --config configs\config_polygon_upgrade_100k.json
```

Backscan is resumable. If a provider quota or rate limit is detected, it writes:

```text
../experiments/data_polygon_upgrade_100k/backscan/quota_exhausted.json
```

## Candidate Validation

For each candidate spender, run:

```powershell
python scripts\verify_impl_change.py --config configs\config_polygon_upgrade_100k.json --spender <spender>
python scripts\verify_post_upgrade_usage.py --config configs\config_polygon_upgrade_100k.json --spender <spender>
python scripts\trace_allowance_use.py --config configs\config_polygon_upgrade_100k.json --spender <spender> --rpc-url <trace-capable-rpc>
```

Trace validation requires an RPC endpoint supporting `debug_traceTransaction` or `trace_transaction`.

## Final Summary

After validation, refresh the aggregate summary:

```powershell
python scripts\summarize_trace_results.py --config configs\config_polygon_upgrade_100k.json --rpc-url https://YOUR_TRACE_CAPABLE_POLYGON_RPC_ENDPOINT
```

Outputs:

- `../experiments/data_polygon_upgrade_100k/verification/trace_experiment_summary.json`
- `../experiments/data_polygon_upgrade_100k/verification/trace_experiment_summary.md`

## Supplemental Metrics

This command derives additional read-only evidence from the existing local artifacts:

```powershell
python scripts\analyze_supplemental_metrics.py --config configs\config_polygon_upgrade_100k.json
```

Outputs:

- `../experiments/data_polygon_upgrade_100k/verification/supplemental_metrics.json`
- `../experiments/data_polygon_upgrade_100k/verification/supplemental_metrics.md`

It reports approval value composition, latest token-owner-spender states, approval-to-upgrade age, spender concentration, and the validation funnel.

## Active Allowance State Validation

This command verifies whether candidate approval states are still active at the upgrade block and at the latest block:

```powershell
python scripts\validate_allowance_state.py --config configs\config_polygon_upgrade_100k.json --rpc-url https://YOUR_POLYGON_RPC_ENDPOINT --per-spender-limit 50
```

Outputs:

- `../experiments/data_polygon_upgrade_100k/verification/allowance_state_validation.json`
- `../experiments/data_polygon_upgrade_100k/verification/allowance_state_validation.md`

Use a per-spender limit for large windows to bound RPC calls. The script keeps the detection rule unchanged and only validates state through ERC-20 `allowance(owner, spender)` calls.

## Implementation Semantic Diff

This command compares previous and upgraded implementation bytecode for trace-positive spenders:

```powershell
python scripts\semantic_diff_implementations.py --config configs\config_polygon_upgrade_100k.json --rpc-url https://YOUR_POLYGON_RPC_ENDPOINT --source-lookup
```

Outputs:

- `../experiments/data_polygon_upgrade_100k/verification/implementation_semantic_diff.json`
- `../experiments/data_polygon_upgrade_100k/verification/implementation_semantic_diff.md`

The script extracts `PUSH4` selectors, highlights ERC-20 and authorization-relevant selectors, counts external-call and storage opcodes, and optionally checks Sourcify source metadata. If no verified source is available, the result is reported as bytecode-level evidence.

## Exploit Evidence Builder

This command upgrades the result interpretation from lifecycle risk to exploit-likelihood evidence. It does not change backscan, trace, or semantic-diff outputs.

```powershell
python scripts\exploit_evidence_builder.py --config configs\config_polygon_upgrade_100k.json --rpc-url https://YOUR_POLYGON_RPC_ENDPOINT
```

Outputs:

- `../experiments/data_polygon_upgrade_100k/verification/exploit_evidence.json`
- `../experiments/data_polygon_upgrade_100k/verification/exploit_evidence.md`

The script grades trace-positive spenders on a five-level scale:

- Level 1: historical approvals target an upgraded spender.
- Level 2: sampled allowance states remain active at upgrade/latest block.
- Level 3: implementation bytecode changed and upgraded bytecode contains `transferFrom` capability.
- Level 4: trace-confirmed `transferFrom` is not initiated by the token owner.
- Level 5: non-owner transfers affect multiple owners and concentrate by recipient, sender, or spender.

Level 5 means exploit-likely on-chain evidence. It is not treated as externally confirmed maliciousness unless additional off-chain incident reports, victim complaints, labels, or a complete attacker-fund-flow proof are added.

## Data Hygiene

If overlapping backscan processes accidentally write duplicate approval logs, deduplicate by the on-chain log key:

```powershell
python scripts\deduplicate_jsonl.py ..\experiments\data_polygon_upgrade_100k\backscan\upgrade_spender_approvals.jsonl --key tx_hash log_index
python scripts\deduplicate_jsonl.py ..\experiments\data_polygon_upgrade_100k\backscan\upgrade_spender_approvals.raw.jsonl --key transactionHash logIndex
```

This is a cleanup step for duplicated logs only; it does not change the detection rule.
