# DriftGuard Code

This directory contains the code snapshot for DriftGuard, the measurement
pipeline used in the paper.

It intentionally contains code and run documentation only. The experiment result
artifacts reported in the paper are stored separately in `../experiments`.

## Contents

- `aa_auth_lifecycle/`: Python package implementing collection,
  normalization, graph construction, backscan logic, risk rules, reporting, and
  RPC helpers.
- `scripts/`: analysis and validation scripts for allowance-state checks,
  post-upgrade usage scans, transaction-trace validation, implementation diff,
  supplemental metrics, and exploit-evidence grading.
- `config.example.json` and `sample_config.json`: configuration templates.
- `configs/`: anonymized configurations for the four Polygon windows reported
  in the paper.
- `requirements.txt`: Python dependencies.
- `RUNBOOK.md`: command-oriented notes used during the experiments.

No raw experiment outputs, sampled chain logs, or cached Python bytecode are
included in this directory.

## Environment

Use Python 3.12 or a recent Python 3 release.

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

The pipeline requires access to Polygon-compatible JSON-RPC endpoints. Some
validation steps require trace-capable RPC methods such as
`debug_traceTransaction`; not all public or hosted endpoints expose them.

## Quick Start

From the artifact root:

```powershell
cd code
python -m pip install -r requirements.txt
```

Create a local config from the template:

```powershell
Copy-Item config.example.json config.local.json
```

Edit `config.local.json`:

- set `rpc_url` to your JSON-RPC endpoint;
- set `chain_id` to `137` for Polygon;
- set `from_block` and `to_block`;
- set `output_dir` to a new local output directory, for example
  `data_local_run`;
- keep `collect_all_upgrades` enabled if you want to discover all
  `Upgraded(address)` events in the window.

Run the core pipeline:

```powershell
python -m aa_auth_lifecycle.cli collect --config config.local.json
python -m aa_auth_lifecycle.cli normalize --config config.local.json
python -m aa_auth_lifecycle.cli graph --config config.local.json
python -m aa_auth_lifecycle.cli risks --config config.local.json
python -m aa_auth_lifecycle.cli backscan --config config.local.json
```

The backscan is resumable. If the RPC provider rate-limits or fails, rerun the
same `backscan` command after the endpoint is available again.

Check current progress and outputs:

```powershell
python -m aa_auth_lifecycle.cli status --config config.local.json
```

## Validation Scripts

After candidate spenders are found, validation scripts can be run per spender.

Implementation slot and bytecode-hash check:

```powershell
python scripts\verify_impl_change.py --config config.local.json --spender <spender>
```

Post-upgrade transfer scan:

```powershell
python scripts\verify_post_upgrade_usage.py --config config.local.json --spender <spender>
```

Trace-confirmed allowance use. This requires a trace-capable RPC endpoint:

```powershell
python scripts\trace_allowance_use.py --config config.local.json --spender <spender> --rpc-url <trace-capable-rpc-url>
```

Aggregate trace results:

```powershell
python scripts\summarize_trace_results.py --config config.local.json --rpc-url <rpc-url>
```

Supplemental approval-exposure metrics:

```powershell
python scripts\analyze_supplemental_metrics.py --config config.local.json
```

Active allowance-state validation:

```powershell
python scripts\validate_allowance_state.py --config config.local.json --rpc-url <rpc-url> --per-spender-limit 50
```

Bytecode-level semantic diff:

```powershell
python scripts\semantic_diff_implementations.py --config config.local.json --rpc-url <rpc-url> --source-lookup
```

Exploit-evidence grading:

```powershell
python scripts\exploit_evidence_builder.py --config config.local.json --rpc-url <rpc-url>
```

## Relationship to Paper Results

The paper reports four positive experiment windows whose result artifacts are
kept in `../experiments`:

- `data_polygon_upgrade_100k`
- `data_polygon_upgrade_next_25k`
- `data_polygon_upgrade_next_100k_c`
- `data_polygon_upgrade_next_1m_d`

The scripts in this directory produced or summarized those artifacts, but this
directory is not meant to duplicate the result data.

The corresponding anonymized configs are in `configs/`. Their `rpc_url` values
are placeholders. Replace them with a Polygon-compatible endpoint before
rerunning collection or validation. For example:

```powershell
python -m aa_auth_lifecycle.cli status --config configs\config_polygon_upgrade_100k.json
```

To inspect the copied paper-result artifacts without rerunning collection, use
the status command with a config whose `output_dir` points at the corresponding
directory under `../experiments`. For example:

```json
{
  "rpc_url": "https://YOUR_RPC_ENDPOINT",
  "chain_id": 137,
  "from_block": 90787373,
  "to_block": 90887373,
  "chunk_size": 2000,
  "output_dir": "..\\experiments\\data_polygon_upgrade_100k",
  "collect_all_upgrades": true,
  "entrypoints": [
    {
      "name": "EntryPoint_v0_6",
      "address": "0x5ff137d4b0fdcd49dca30c7cf57e578a026d2789"
    },
    {
      "name": "EntryPoint_v0_7",
      "address": "0x0000000071727de22e5e9d8baf0edac6f37da032"
    }
  ],
  "permit2_addresses": [],
  "tracked_tokens": [],
  "risk_thresholds": {
    "approval_unlimited_ratio": "0.5",
    "large_approval_amount": "1000000000000000000000000",
    "paymaster_userop_min_count": 100
  }
}
```

Save that as `config.paper_100k.json`, then run:

```powershell
python -m aa_auth_lifecycle.cli status --config config.paper_100k.json
```

## Notes

- Do not place API keys in committed configs.
- Use `config.example.json` or `sample_config.json` as templates for local runs.
- Long-running scans are resumable through state files written inside each
  experiment data directory.
