# Top Spender Verification Summary

## Target

- Spender / upgraded proxy: `0x8cA97F41d2C81AF050656e8AD0Cf543820a24504`
- Candidate approvals found so far: 1230
- Approvals before first observed upgrade: 1230
- Approvals after or at first observed upgrade: 0
- Unique owners before upgrade: 881
- Unique tokens before upgrade: 2

## Upgrade Evidence

- First observed upgrade block: 90797649
- Upgrade transaction: `0x78f97f7141249941e1bffd67e4ac4a27f661131fc4adc944923694f3498bf3d0`
- Previous EIP-1967 implementation: `0x0865B4cEbf1Ebc435f24F9F513Ff9013707B121C`
- Implementation from `Upgraded(address)` event: `0xf701f91d6A6908FCc641F51236CcC62045366818`
- Latest EIP-1967 implementation slot: `0xf701f91d6A6908FCc641F51236CcC62045366818`
- Current contract code exists: yes
- Previous implementation code hash: `0xcde336d469eb6eede42d77996ad55ad1342171e9cb26e7e228c7f9f590e93024`
- New implementation code hash: `0x3b52fbeff617a724eb774466821a84525f83e0f2912f09523fa1e6451fe76494`

This confirms the target is an upgradeable/proxy-style contract and that its implementation actually changed at the observed upgrade block.

## Authorization Evidence

Top tokens before upgrade:

1. `0xeB51D9A39AD5EEF215dC0Bf39a8821ff804A0F01`: 951 approvals
2. `0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063`: 279 approvals

Top owners before upgrade include:

1. `0x9b65eda0204fcaF0A102bDdf5D2A19809e598df1`: 8 approvals
2. `0xE58aeB7Cf4926227a15Cd24107317cFc891A2328`: 6 approvals
3. `0x751203f4F67e6B0C0A2C7A90495306A1c2955ee2`: 5 approvals
4. `0xDdbF5777f0536CeD39B5a08d73e94231d49e0BFb`: 5 approvals

## Allowance Verification

Sample size: 30 unique `(token, owner, spender)` pairs.

- Nonzero allowance at first upgrade block: 30 / 30
- Nonzero current allowance: 30 / 30
- Historical `eth_call` at block 90797649 succeeded for all sampled pairs.

This confirms that sampled approvals were not merely historical logs. They remained active when the spender upgraded, and they remain active at the latest block queried.

## Post-Upgrade Usage Scan

For the top 100 owners and top 2 candidate tokens, a post-upgrade transfer scan was executed from block 90797649 to block 90887373.

- Post-upgrade `Transfer` events from approved owners: 194
- Unique transfer transactions: 136
- Unique owners with post-upgrade transfers: 38
- Top-level transactions directly sent to the upgraded spender: 0

Interpretation:

- This shows that many approved owners continued to move the same assets after the spender upgrade.
- It does not by itself prove that the upgraded spender used the old allowance, because ERC-20 `Transfer` logs do not record the caller.
- To prove actual allowance use, the next step requires transaction traces or another source that identifies whether the upgraded spender called `transferFrom`.

## Trace Validation

Transaction traces were executed with `debug_traceTransaction` and a call tracer on a trace-capable Polygon RPC endpoint.

Top spender trace result:

- Candidate post-upgrade transactions traced: 136
- Failed traces: 0
- Confirmed calls where the upgraded spender invoked token `transferFrom` for a pre-upgrade approved owner: 0

Interpretation: the top spender remains a strong active-drift case, but the traced post-upgrade transfer set does not show allowance consumption by this spender.

## Interpretation

This is a strong candidate for upgrade-induced authorization semantic drift:

1. Users granted token allowances to the spender before the upgrade.
2. The spender later emitted `Upgraded(address)`.
3. The spender's EIP-1967 implementation slot matches the upgraded implementation.
4. Sampled allowances were still nonzero at upgrade time.
5. Sampled allowances are still nonzero now.

This is not yet a confirmed exploit. It is now a strong authorization semantic drift case: active user allowances survived a real implementation change. To turn it into an exploit-style case, the next step should check whether post-upgrade transactions used the old allowances.

## Second Confirmed Candidate

A second upgraded spender was also validated:

- Spender: `0xb2A1D9fE94681713C6C1cDc7c9E3F9F743ada3c9`
- Candidate approvals before first observed upgrade: 259
- Unique owners before upgrade: 259
- Unique tokens before upgrade: 1
- First observed upgrade block: 90793214
- First observed upgrade tx: `0xfe7e4e8ccda18ecb69528df0264f76530ae994b3564c651c65ef08d42d5f291c`
- Sampled allowance checks: 20 / 20 nonzero at upgrade block; 20 / 20 nonzero currently

This supports that the phenomenon is not limited to a single spender.

Post-upgrade usage and trace validation for the second spender:

- Post-upgrade `Transfer` events from approved owners: 108
- Unique post-upgrade transfer transactions: 108
- Top-level transactions directly sent to the upgraded spender: 78
- Candidate post-upgrade transactions traced: 108
- Failed traces: 0
- Confirmed calls where the upgraded spender invoked token `transferFrom` for a pre-upgrade approved owner: 78
- Unique owners in trace-confirmed `transferFrom` calls: 50
- Unique token contracts in trace-confirmed calls: 1

Interpretation: this is a trace-confirmed allowance-use case. The spender had received approvals before its observed upgrade, the sampled allowances remained nonzero across the upgrade, and post-upgrade traces show the upgraded spender calling the approved token's `transferFrom` against pre-upgrade approved owners.

## Next Validation Steps

1. Retrieve verified source or bytecode metadata for:
   - proxy `0x8cA97F41d2C81AF050656e8AD0Cf543820a24504`
   - implementation `0xf701f91d6A6908FCc641F51236CcC62045366818`
2. Compare pre-upgrade and post-upgrade implementation behavior if the previous implementation can be recovered.
3. Retrieve and compare verified source or bytecode-level semantics for the second spender's previous and current implementations.
4. Check whether common approval dashboards would warn that these spenders upgraded after approval.

Full machine-readable verification output:

- `data_polygon_upgrade_100k/verification/candidate_0x8ca97f41d2c81af050656e8ad0cf543820a24504.json`
- `data_polygon_upgrade_100k/verification/trace_allowance_use_0x8ca97f41d2c81af050656e8ad0cf543820a24504.json`
- `data_polygon_upgrade_100k/verification/candidate_0xb2a1d9fe94681713c6c1cdc7c9e3f9f743ada3c9.json`
- `data_polygon_upgrade_100k/verification/post_upgrade_usage_0xb2a1d9fe94681713c6c1cdc7c9e3f9f743ada3c9.json`
- `data_polygon_upgrade_100k/verification/trace_allowance_use_0xb2a1d9fe94681713c6c1cdc7c9e3f9f743ada3c9.json`
