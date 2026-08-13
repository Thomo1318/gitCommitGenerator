# Snapshots

`dataset_snapshot_v1` objects are built at test/runtime via
`git_cg.eval.corpus.snapshots.build_snapshot()`.

Optional checked-in goldens:

```bash
uv run python -m git_cg.eval.corpus.materialize
```

Produces `*.dataset_snapshot_v1.json` beside this README. Determinism remains
proven by re-encode equality tests rather than brittle timestamped files.
