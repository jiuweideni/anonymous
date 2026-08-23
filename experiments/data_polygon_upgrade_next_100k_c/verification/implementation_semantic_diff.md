# Implementation Semantic Diff

- chain: 137
- output_dir: `data_polygon_upgrade_next_100k_c`
- analyzed spenders: 6
- Sourcify source matches: 0 / 11

| Spender | Matches | Code changed | Size delta | Added ERC20 selectors | External call delta | Risk signals |
| --- | ---: | --- | ---: | --- | --- | --- |
| `0xfB41...DA67` | 2 | True | 412 | `--` | 0 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector |
| `0x71e9...4582` | 3 | True | 25 | `--` | 0 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector |
| `0x28a9...c163` | 1 | True | 0 | `--` | 0 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector |
| `0x371F...B849` | 1 | False | 0 | `--` | 0 | post_upgrade_bytecode_contains_transferFrom_selector |
| `0xF8fF...D4Ac` | 24 | True | 767 | `--` | CALLCODE:-1 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector, storage_write_count_increased |
| `0xEc2b...C759` | 3 | True | 3040 | `--` | CALL:+1, STATICCALL:-1 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector, external_CALL_count_increased, storage_write_count_increased |

## Notes

The bytecode analysis extracts PUSH4 constants as candidate function selectors and counts authorization-relevant opcodes. Selector presence is conservative evidence: it indicates that a selector appears in bytecode, not by itself that the selector is reachable on every execution path.

Sourcify did not return source metadata for the analyzed implementation addresses, so this report remains bytecode-level rather than source-level.
