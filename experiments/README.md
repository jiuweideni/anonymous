# Experiment Results

This directory contains a lightweight artifact snapshot for the positive
experiment results reported in the paper. It keeps the evidence needed to audit
the reported findings while excluding large raw and intermediate pipeline files
that can be regenerated from the code and configurations.

Included result directories:

- `data_polygon_upgrade_100k`: main 100,001-block Polygon experiment.
- `data_polygon_upgrade_next_25k`: 25k follow-up window.
- `data_polygon_upgrade_next_100k_c`: later 100k-c follow-up window.
- `data_polygon_upgrade_next_1m_d`: 369,894-block extension window.

Each directory keeps:

- `collection_summary.json`, `collection_state.json`, and backscan state files
  for window and completion metadata.
- `raw_logs/upgrades.jsonl` for observed proxy-upgrade events.
- `backscan/upgrade_drift_candidates.json` and
  `backscan/upgrade_spender_approvals.jsonl` for candidate spenders and their
  historical approval evidence.
- `verification/` JSON and Markdown outputs for allowance-state validation,
  implementation-change checks, post-upgrade usage scans, trace-confirmed
  allowance use, semantic-diff summaries, supplemental metrics, and
  exploit-evidence grading.

Excluded large regenerable files:

- `raw_logs/entrypoint_userops.jsonl`
- empty `raw_logs/erc20_approvals.jsonl` and `raw_logs/permit2_approvals.jsonl`
- `normalized/events.jsonl`
- `results/capability_edges.jsonl`
- raw RPC approval mirrors such as `*.raw.jsonl`
- trace-resume state files such as `trace_allowance_use_*.state.json`

The analysis code, scripts, and anonymized configurations are stored separately
under `../code`. The original `aa_auth_lifecycle` working directory is
unchanged.
