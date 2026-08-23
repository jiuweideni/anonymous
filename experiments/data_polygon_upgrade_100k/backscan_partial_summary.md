# Polygon Upgrade-Driven Backscan Partial Summary

## Scope

- Chain: Polygon
- Chain ID: 137
- Upgrade discovery block range: 90787373 - 90887373
- Upgrade discovery window: 100001 blocks
- Backscan history per upgraded proxy: 200000 blocks before its earliest observed upgrade
- Approval scope: all ERC-20 contracts emitting `Approval(address,address,uint256)`
- Backscan target: spender equals upgraded proxy

## Upgrade Discovery

- Normalized events: 203437
- ERC-4337 UserOperationEvent logs: 202650
- Upgraded(address) logs: 787
- Unique upgraded proxies: 777

## Current Backscan Progress

- Current proxy index: 88 / 777
- Current proxy: `0x309B26e0856bbd33FA724d197A3662D7a9e9d729`
- Current next_to_block: 90657239
- Quota marker: not generated
- Status: running/resumable

The process stopped because the command reached the interactive timeout, not because Infura quota was exhausted.

## Current Candidate Results

- Historical approval candidates: 295
- Upgraded spender addresses with historical approvals: 5
- Unique owners: 274
- Unique tokens: 4
- Candidate block range: 90593444 - 90792630

Top upgraded spenders by historical approval count:

1. `0xb2A1D9fE94681713C6C1cDc7c9E3F9F743ada3c9`: 259
2. `0x1E6C9aF6257Bdfa7F6b3d65126eCfb923007C522`: 23
3. `0xC517c54c1368d8dA6c861148bC0fe319B695C7Aa`: 8
4. `0x9b081323d11A2A61f43701A4007a4a98357c57A1`: 3
5. `0xC5b8D67B7fCE30c942835529dFB5D59DCb7D5D09`: 2

Top token contracts by candidate count:

1. `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359`: 259
2. `0x386C4247d0e85e622C8Ac420cdCfa6F5482Fb4Ad`: 31
3. `0x882df4B0fB50a229C3B4124EB18c759911485bFb`: 3
4. `0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB`: 2

## Interpretation

This is the first positive result for the drift direction:

`upgrade event -> historical approval to upgraded proxy`

The earlier 10K-block experiment found no forward drift candidates. The expanded 100K-block upgrade discovery plus all-token historical backscan has already found 295 candidate approvals before scanning all upgraded proxies.

These are still candidates, not confirmed vulnerabilities. The next validation step is to confirm for the top spender:

1. The spender is actually a proxy or upgradeable contract.
2. The spender's upgrade happened after the historical approvals.
3. The approvals were still non-zero at upgrade time.
4. The upgraded implementation changed relevant token-spending behavior or execution path.
5. There is post-upgrade use of the old allowance, ideally via transaction trace.

## Resume Command

To continue scanning from the saved progress:

```powershell
cd code
python -m aa_auth_lifecycle.cli backscan --config config_polygon_upgrade_100k.json
```

To retry automatically every day:

```powershell
cd code
.\scripts\watch_backscan.ps1 -Config config_polygon_upgrade_100k.json -IntervalHours 24
```
