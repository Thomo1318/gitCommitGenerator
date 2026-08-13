# Checked-in golden bundles

Materialized `ape_bundle_v1` dumps for review and pin-stability checks.

```bash
uv run python -m git_cg.eval.corpus.materialize
```

Identity is still proven by runtime re-encode equality tests. Checked-in files
are golden snapshots of encoder output bound to current S0 pins.
