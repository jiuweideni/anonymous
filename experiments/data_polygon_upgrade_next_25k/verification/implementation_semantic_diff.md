# Implementation Semantic Diff

- chain: 137
- output_dir: `data_polygon_upgrade_next_25k`
- analyzed spenders: 1
- Sourcify source matches: 0 / 2

| Spender | Matches | Code changed | Size delta | Added ERC20 selectors | External call delta | Risk signals |
| --- | ---: | --- | ---: | --- | --- | --- |
| `0xB3A7...9F5e` | 1 | True | 902 | `--` | 0 | implementation_bytecode_changed, post_upgrade_bytecode_contains_transferFrom_selector, storage_write_count_increased |

## Notes

The bytecode analysis extracts PUSH4 constants as candidate function selectors and counts authorization-relevant opcodes. Selector presence is conservative evidence: it indicates that a selector appears in bytecode, not by itself that the selector is reachable on every execution path.

Sourcify did not return source metadata for the analyzed implementation addresses, so this report remains bytecode-level rather than source-level.
