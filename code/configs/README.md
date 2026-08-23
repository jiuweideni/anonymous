# Experiment Configurations

These anonymized configurations correspond to the Polygon windows reported in
the paper. The `rpc_url` fields are placeholders; replace them with a
Polygon-compatible JSON-RPC endpoint before rerunning collection or validation.

The `output_dir` fields point to the copied result artifacts under
`../experiments`. To run a fresh experiment, change `output_dir` to a new local
directory.

Trace validation requires a provider that supports `debug_traceTransaction` or
`trace_transaction`.
