# Level-5 Case Study

- Spender: `0xb2A1D9fE94681713C6C1cDc7c9E3F9F743ada3c9`
- Evidence label: exploit-likely (Level 5)
- Upgrade block: 90793214
- First matched transfer block: 90798701
- Upgrade-to-first-transfer gap: 5487 blocks; 8231 seconds
- Upgrade tx sender: `0x575774F852F1F7752E23d34ff4977B956e2C143b`
- Dominant matched tx sender: `0x67e6062fB0888189d7cC7cEF451b531c5E03d212`
- EIP-1967 admin at upgrade/latest: `None` / `None`
- Implementation at upgrade/latest: `0x5066C59c487804118C6e651c0A4Ef912804da1B1` / `0xbCfd503b2eB5Ec786BBCc540D972A9f4a2Eeec9D`

## Matched Allowance Use

- Matched transferFrom calls: 78
- Successful matched txs: 78
- Non-owner calls: 78 (100.0%)
- Unique owners: 50
- Unique tx senders: 1
- Unique recipients: 1
- Recipient is spender: 78

## Concentration

| Type | Address | Count | Share |
|---|---|---:|---:|
| tx sender | `0x67e6...d212` | 78 | 100.0% |
| recipient | `0xb2a1...a3c9` | 78 | 100.0% |

## Account Code Summary

| Account | Address | Contract | Code bytes |
|---|---|---:|---:|
| spender | `0xb2A1...a3c9` | True | 130 |
| upgrade_tx_sender | `0x5757...143b` | False | 0 |
| dominant_tx_sender | `0x67e6...d212` | False | 0 |
| implementation_at_upgrade | `0x5066...a1B1` | True | 16462 |
| implementation_latest | `0xbCfd...ec9D` | True | 17542 |

## Token Flow Window

- Scan range: 90793214--90898701
- Incoming transfers to spender: 8998
- Outgoing transfers from spender: 8998
- Post-upgrade approvals to spender on matched tokens: 193

### Top incoming senders

| Address | Count | Share |
|---|---:|---:|
| `0x0375...26c2` | 728 | 8.0907% |
| `0x4243...6394` | 500 | 5.5568% |
| `0xbec9...9b92` | 123 | 1.367% |
| `0x3640...6838` | 122 | 1.3559% |
| `0x6dd5...1f31` | 91 | 1.0113% |
| `0x9ed7...33ac` | 88 | 0.978% |
| `0x1e3c...ed15` | 83 | 0.9224% |
| `0x8181...1704` | 81 | 0.9002% |
| `0x1866...70c6` | 80 | 0.8891% |
| `0xedd1...42a9` | 77 | 0.8557% |

### Top outgoing recipients

| Address | Count | Share |
|---|---:|---:|
| `0x5577...3aea` | 8998 | 100.0% |

## Amounts

### matched_amounts
- `0x3c49...3359` USDC: 26573.99

### incoming_amounts
- `0x3c49...3359` USDC: 3726357.94

### outgoing_amounts
- `0x3c49...3359` USDC: 3726357.94
