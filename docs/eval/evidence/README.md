# Eval maintainer evidence

Operator/maintainer-only artifacts that are **not** CI merge gates and never
product-accept authority.

## S6-G02(b) dogfood bench

| File | Role |
|:---|:---|
| `s6-g02b-bench_async_off.json` | hyperfine `--export-json` for dogfood mode `off` |
| `s6-g02b-bench_async_on.json` | hyperfine `--export-json` for dogfood mode `async` |
| `s6-g02b-dogfood-bench-summary.txt` | `python -m git_cg.eval.dogfood.bench OFF ON` one-line report |
| `s6-g02b-dogfood-bench-meta.json` | Capture metadata + claim linkage |

Reproduce (default recipe; longer):

```bash
just dogfood-bench 20
```

Summariser argument order is **OFF then ON**.
