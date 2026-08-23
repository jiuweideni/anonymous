# Supplemental Metrics

This report is computed only from existing local artifacts. It does not query an RPC endpoint or change the detector output.

## Exposure
- Historical approval events: 103
- Non-zero approval events: 71 (68.932%)
- Zero-value revocation events: 32 (31.068%)
- Unlimited approval events: 3 (2.9126%)
- Unique token-owner-spender states: 36
- Latest non-zero states: 25 (69.4444%)

## Approval Age
- Matched approval events with upgrade block: 103
- Median blocks before upgrade: 57787
- P90 blocks before upgrade: 148255
- P99 blocks before upgrade: 196343
- Max blocks before upgrade: 196400

## Concentration
- Top spender share: 40.7767%
- Top 3 spender share: 87.3786%

| Rank | Spender | Approval events | Share |
| --- | --- | ---: | ---: |
| 1 | `0xfb41...da67` | 42 | 40.7767% |
| 2 | `0x71e9...4582` | 32 | 31.068% |
| 3 | `0x28a9...c163` | 16 | 15.534% |
| 4 | `0x371f...b849` | 6 | 5.8252% |
| 5 | `0xf8ff...d4ac` | 3 | 2.9126% |
| 6 | `0xec2b...c759` | 2 | 1.9417% |
| 7 | `0x1a82...597e` | 1 | 0.9709% |
| 8 | `0xecf9...328a` | 1 | 0.9709% |

## Validation Funnel
- Candidate upgraded spenders with historical approvals: 8
- Implementation-change verified spenders: 7
- Spenders with post-upgrade transfer activity: 6
- Trace-positive spenders: 6
- Trace-positive rate among candidates: 75.0%
- Trace-confirmed transaction rate among traced transactions: 89.4737%
- Trace-confirmed transferFrom calls: 34
- Trace-confirmed transaction count: 34

## Trace-Positive Spenders
| Spender | Approval events | Traced txs | Matched txs | transferFrom matches |
| --- | ---: | ---: | ---: | ---: |
| `0xF8fF...D4Ac` | 3 | 24 | 24 | 24 |
| `0x71e9...4582` | 32 | 3 | 3 | 3 |
| `0xEc2b...C759` | 2 | 3 | 3 | 3 |
| `0xfB41...DA67` | 42 | 4 | 2 | 2 |
| `0x28a9...c163` | 16 | 2 | 1 | 1 |
| `0x371F...B849` | 6 | 2 | 1 | 1 |

## Trace-Positive vs Trace-Negative Groups
| Group | Spenders | Approval events | Latest non-zero states | Post-upgrade txs | Traced txs | Matched txs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| trace-positive | 6 | 101 | 23 | 38 | 38 | 34 |
| trace-negative | 2 | 2 | 2 | 0 | 0 | 0 |
