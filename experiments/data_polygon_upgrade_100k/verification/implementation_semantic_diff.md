# Implementation Semantic Diff

- chain: 137
- output_dir: `data_polygon_upgrade_100k`
- analyzed spenders: 6
- Sourcify source matches: 0 / 12

| Spender | Matches | Code changed | Size delta | Added ERC20 selectors | External call delta | Risk signals |
| --- | ---: | --- | ---: | --- | --- | --- |
| `0xEab9...7268` | 70 | True | -21 | `--` | 0 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector, storage_write_count_increased |
| `0xb2A1...a3c9` | 78 | True | 2456 | `--` | CALL:+1, CALLCODE:+1 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector, external_CALL_count_increased, storage_write_count_increased |
| `0x1E6C...C522` | 4 | True | -46 | `--` | CALL:-3, DELEGATECALL:+1 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector, DELEGATECALL_count_increased |
| `0x2d91...aF61` | 6 | True | 1249 | `--` | STATICCALL:+1 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector, storage_write_count_increased |
| `0xC517...C7Aa` | 3 | True | -27 | `--` | CALLCODE:-1 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector |
| `0x93F8...f4fd` | 12 | True | 1249 | `--` | STATICCALL:+1 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector, storage_write_count_increased |

## Notes

The bytecode analysis extracts PUSH4 constants as candidate function selectors and counts authorization-relevant opcodes. Selector presence is conservative evidence: it indicates that a selector appears in bytecode, not by itself that the selector is reachable on every execution path.

Sourcify did not return source metadata for the analyzed implementation addresses, so this report remains bytecode-level rather than source-level.
