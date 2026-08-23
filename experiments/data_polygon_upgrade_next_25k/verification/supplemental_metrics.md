# Supplemental Metrics

This report is computed only from existing local artifacts. It does not query an RPC endpoint or change the detector output.

## Exposure
- Historical approval events: 126
- Non-zero approval events: 126 (100.0%)
- Zero-value revocation events: 0 (0.0%)
- Unlimited approval events: 87 (69.0476%)
- Unique token-owner-spender states: 86
- Latest non-zero states: 86 (100.0%)

## Approval Age
- Matched approval events with upgrade block: 126
- Median blocks before upgrade: 80235
- P90 blocks before upgrade: 163950
- P99 blocks before upgrade: 187196.75
- Max blocks before upgrade: 191571

## Concentration
- Top spender share: 100.0%
- Top 3 spender share: 100.0%

| Rank | Spender | Approval events | Share |
| --- | --- | ---: | ---: |
| 1 | `0xb3a7...9f5e` | 126 | 100.0% |

## Validation Funnel
- Candidate upgraded spenders with historical approvals: 1
- Implementation-change verified spenders: 1
- Spenders with post-upgrade transfer activity: 1
- Trace-positive spenders: 1
- Trace-positive rate among candidates: 100.0%
- Trace-confirmed transaction rate among traced transactions: 33.3333%
- Trace-confirmed transferFrom calls: 1
- Trace-confirmed transaction count: 1

## Trace-Positive Spenders
| Spender | Approval events | Traced txs | Matched txs | transferFrom matches |
| --- | ---: | ---: | ---: | ---: |
| `0xB3A7...9F5e` | 126 | 3 | 1 | 1 |

## Trace-Positive vs Trace-Negative Groups
| Group | Spenders | Approval events | Latest non-zero states | Post-upgrade txs | Traced txs | Matched txs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| trace-positive | 1 | 126 | 86 | 3 | 3 | 1 |
| trace-negative | 0 | 0 | 0 | 0 | 0 | 0 |
