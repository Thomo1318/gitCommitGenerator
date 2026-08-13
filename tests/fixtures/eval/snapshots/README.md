# Snapshots

S1 builds `dataset_snapshot_v1` at test/runtime via
`git_cg.eval.corpus.snapshots.build_core_snapshot()`.

Checked-in golden snapshot hashes are optional. Determinism is proven by
re-encode equality tests rather than brittle timestamped files.
