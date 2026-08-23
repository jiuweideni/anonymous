# Supplemental Metrics

This report is computed only from existing local artifacts. It does not query an RPC endpoint or change the detector output.

## Exposure
- Historical approval events: 24288
- Non-zero approval events: 23378 (96.2533%)
- Zero-value revocation events: 910 (3.7467%)
- Unlimited approval events: 1011 (4.1625%)
- Unique token-owner-spender states: 7818
- Latest non-zero states: 7039 (90.0358%)

## Approval Age
- Matched approval events with upgrade block: 24288
- Median blocks before upgrade: 98066.50
- P90 blocks before upgrade: 186232.50
- P99 blocks before upgrade: 197744.52
- Max blocks before upgrade: 199770

## Concentration
- Top spender share: 93.4453%
- Top 3 spender share: 99.5759%

| Rank | Spender | Approval events | Share |
| --- | --- | ---: | ---: |
| 1 | `0xeab9...7268` | 22696 | 93.4453% |
| 2 | `0x8ca9...4504` | 1230 | 5.0642% |
| 3 | `0xb2a1...a3c9` | 259 | 1.0664% |
| 4 | `0xb68a...2811` | 36 | 0.1482% |
| 5 | `0x1e6c...c522` | 23 | 0.0947% |
| 6 | `0x9199...1c21` | 14 | 0.0576% |
| 7 | `0x2d91...af61` | 9 | 0.0371% |
| 8 | `0xc517...c7aa` | 8 | 0.0329% |
| 9 | `0x93f8...f4fd` | 8 | 0.0329% |
| 10 | `0x9b08...57a1` | 3 | 0.0124% |

## Validation Funnel
- Candidate upgraded spenders with historical approvals: 11
- Implementation-change verified spenders: 9
- Spenders with post-upgrade transfer activity: 7
- Trace-positive spenders: 6
- Trace-positive rate among candidates: 54.5455%
- Trace-confirmed transaction rate among traced transactions: 42.246%
- Trace-confirmed transferFrom calls: 173
- Trace-confirmed transaction count: 158

## Trace-Positive Spenders
| Spender | Approval events | Traced txs | Matched txs | transferFrom matches |
| --- | ---: | ---: | ---: | ---: |
| `0xb2A1...a3c9` | 259 | 108 | 78 | 78 |
| `0xEab9...7268` | 22696 | 99 | 70 | 70 |
| `0x93F8...f4fd` | 8 | 4 | 2 | 12 |
| `0x2d91...aF61` | 9 | 4 | 1 | 6 |
| `0x1E6C...C522` | 23 | 20 | 4 | 4 |
| `0xC517...C7Aa` | 8 | 3 | 3 | 3 |

## Trace-Positive vs Trace-Negative Groups
| Group | Spenders | Approval events | Latest non-zero states | Post-upgrade txs | Traced txs | Matched txs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| trace-positive | 6 | 23003 | 6770 | 238 | 238 | 158 |
| trace-negative | 5 | 1285 | 269 | 136 | 136 | 0 |
