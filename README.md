# DriftGuard Artifact

This artifact contains the code and result data for the DriftGuard measurement
pipeline.

## Layout

- `code/`: Python source code, validation scripts, dependency file, runbook, and
  anonymized experiment configurations.
- `experiments/`: result artifacts for the four Polygon windows reported in the
  paper.

The artifact does not include API keys. Configuration files use placeholder RPC
URLs and should be edited only for fresh collection or validation runs.

## Quick Verification

From the artifact root:

```powershell
cd code
python -m pip install -r requirements.txt
python -m aa_auth_lifecycle.cli status --config configs\config_polygon_upgrade_100k.json
python -m aa_auth_lifecycle.cli status --config configs\config_polygon_upgrade_next_25k.json
python -m aa_auth_lifecycle.cli status --config configs\config_polygon_upgrade_next_100k_c.json
python -m aa_auth_lifecycle.cli status --config configs\config_polygon_upgrade_next_1m_d.json
```

These commands do not contact an RPC endpoint. They read the copied artifacts in
`../experiments` and report the discovery, backscan, and trace-summary counts.

## Reproducing Collection

The anonymized configs in `code/configs/` correspond to the paper windows. To
rerun collection or validation, replace `https://YOUR_POLYGON_RPC_ENDPOINT` with
a Polygon-compatible JSON-RPC endpoint. Trace validation requires support for
`debug_traceTransaction` or `trace_transaction`.

For a fresh run, set `output_dir` to a new local directory before running:

```powershell
python -m aa_auth_lifecycle.cli collect --config <config>
python -m aa_auth_lifecycle.cli normalize --config <config>
python -m aa_auth_lifecycle.cli graph --config <config>
python -m aa_auth_lifecycle.cli risks --config <config>
python -m aa_auth_lifecycle.cli backscan --config <config>
```

See `code/README.md` and `code/RUNBOOK.md` for validation and summarization
commands.

## Result Directories

- `experiments/data_polygon_upgrade_100k`: main 100,001-block Polygon window.
- `experiments/data_polygon_upgrade_next_25k`: 25,000-block follow-up window.
- `experiments/data_polygon_upgrade_next_100k_c`: later 100,000-block follow-up
  window.
- `experiments/data_polygon_upgrade_next_1m_d`: 369,894-block extension window.

## Privacy and Safety Notes

The data is derived from public Polygon mainnet records. The artifact reports
evidence labels and measurement outputs, not exploit instructions or external
maliciousness attribution.
