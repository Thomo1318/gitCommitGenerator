"""Acceptpath GC (`git-cg eval gc`).

Locks:
* Required ``--acceptpath`` and ``--older-than``; no default duration.
* Valid-looking ``sess_<32-hex>.json`` names are reuse identity and need ``--force``.
* Legacy ``sess_*.json`` names and ``.bind.lock`` are unmanaged even with ``--force``.
* Normal mode deletes only stale non-authoritative debris.
* JSON mode emits one ``cli_output_envelope_v1``.
* CLI import stays binder/Opik-free.
* Bind never auto-evicts acceptpath; operators run ``eval gc --acceptpath --older-than``.

No network. No Opik. Refs: #257.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from git_cg.eval.gc import GcError, gc_acceptpath, parse_duration
from git_cg.main import app

runner = CliRunner()

SESSION = "sess_" + ("ab" * 16)
AUTHORITATIVE = f"{SESSION}.json"
LEGACY_SESSION = "sess_legacy_not_hex.json"
DEBRIS_INDEX = "index.json"
UNMANAGED_LOCK = ".bind.lock"
DEBRIS_ORPHAN = ".orphan.tmp"
UNADOPTABLE = "not-a-session.json"


def _acceptpath(tmp_path: Path) -> Path:
    path = tmp_path / ".eval" / "bundles" / "acceptpath"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _age(path: Path, *, seconds: float) -> None:
    stamped = time.time() - seconds
    os.utime(path, (stamped, stamped))


def _write(path: Path, body: str = "{}") -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_parse_duration_requires_positive_unit() -> None:
    assert parse_duration("30s") == 30
    assert parse_duration("15m") == 900
    assert parse_duration("2h") == 7200
    assert parse_duration("7d") == 604800
    with pytest.raises(GcError) as exc:
        parse_duration("0s")
    assert exc.value.exit_code == 2
    with pytest.raises(GcError):
        parse_duration("7")
    with pytest.raises(GcError):
        parse_duration("7w")


def test_gc_respects_reuse_identity(tmp_path: Path) -> None:
    bundles = _acceptpath(tmp_path)
    session = _write(bundles / AUTHORITATIVE, '{"bound": true}')
    index = _write(bundles / DEBRIS_INDEX)
    lock = _write(bundles / UNMANAGED_LOCK, "lock")
    orphan = _write(bundles / DEBRIS_ORPHAN, "tmp")
    other = _write(bundles / UNADOPTABLE, "{}")
    for path in (session, index, lock, orphan, other):
        _age(path, seconds=10_000)

    result = gc_acceptpath(tmp_path, older_than="1s", force=False, dry_run=False)
    assert session.is_file()
    assert AUTHORITATIVE in {item.path for item in result.preserved}
    assert not index.exists()
    assert lock.is_file()
    assert not orphan.exists()
    assert not other.exists()
    deleted = {item.path for item in result.deleted}
    assert DEBRIS_INDEX in deleted
    assert UNADOPTABLE in deleted
    assert UNMANAGED_LOCK not in deleted


def test_gc_requires_force_for_authoritative_bundles(tmp_path: Path) -> None:
    bundles = _acceptpath(tmp_path)
    session = _write(bundles / AUTHORITATIVE, "not-json")
    lock = _write(bundles / UNMANAGED_LOCK, "lock")
    legacy = _write(bundles / LEGACY_SESSION, "{}")
    _age(session, seconds=10_000)
    _age(lock, seconds=10_000)
    _age(legacy, seconds=10_000)
    dry = gc_acceptpath(tmp_path, older_than="1s", force=False, dry_run=True)
    assert session.is_file()
    assert AUTHORITATIVE in {item.path for item in dry.preserved}
    assert AUTHORITATIVE not in {item.path for item in dry.selected}
    assert dry.deleted == ()

    forced = gc_acceptpath(tmp_path, older_than="1s", force=True, dry_run=False)
    assert AUTHORITATIVE in {item.path for item in forced.deleted}
    assert not session.exists()
    assert lock.is_file()
    assert legacy.is_file()
    skipped = {item.path: item.reason for item in forced.skipped}
    assert skipped[UNMANAGED_LOCK] == "unmanaged"
    assert skipped[LEGACY_SESSION] == "unmanaged"


def test_gc_selection_deletion_behaviour(tmp_path: Path) -> None:
    bundles = _acceptpath(tmp_path)
    fresh = _write(bundles / DEBRIS_INDEX, '{"fresh": true}')
    stale = _write(bundles / DEBRIS_ORPHAN, "old")
    _age(fresh, seconds=1)
    _age(stale, seconds=10_000)

    dry = gc_acceptpath(tmp_path, older_than="60s", dry_run=True)
    selected = {item.path for item in dry.selected}
    assert stale.name in selected
    assert fresh.name not in selected
    assert dry.deleted == ()
    assert stale.is_file()
    assert fresh.is_file()

    deleted = gc_acceptpath(tmp_path, older_than="60s", dry_run=False)
    assert stale.name in {item.path for item in deleted.deleted}
    assert not stale.exists()
    assert fresh.is_file()


def test_gc_is_idempotent_and_operator_controlled(tmp_path: Path) -> None:
    """Explicit GC deletes stale debris once; a second pass is a no-op.

    Bind never auto-evicts: retention stays operator-controlled via
    ``eval gc --acceptpath --older-than``.
    """
    bundles = _acceptpath(tmp_path)
    session = _write(bundles / AUTHORITATIVE, '{"bound": true}')
    index = _write(bundles / DEBRIS_INDEX, '{"v": 2}')
    lock = _write(bundles / UNMANAGED_LOCK, "lock")
    for candidate in (session, index, lock):
        _age(candidate, seconds=10_000)

    first = gc_acceptpath(tmp_path, older_than="1s")
    assert session.is_file()
    assert not index.exists()
    assert lock.is_file()
    deleted = {item.path for item in first.deleted}
    assert DEBRIS_INDEX in deleted
    assert UNMANAGED_LOCK not in deleted
    assert AUTHORITATIVE not in deleted

    second = gc_acceptpath(tmp_path, older_than="1s")
    assert session.is_file()
    assert second.deleted == ()
    assert second.selected == ()
    assert AUTHORITATIVE in {item.path for item in second.preserved}


def test_eval_gc_requires_acceptpath_and_older_than(isolated_eval_repo: Path) -> None:
    missing_scope = runner.invoke(app, ["eval", "gc", "--json", "--older-than", "1s"])
    env = json.loads(missing_scope.stdout)
    assert missing_scope.exit_code == 2
    assert env["command"] == "eval gc"
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "EVAL_USAGE"

    missing_age = runner.invoke(
        app,
        ["eval", "gc", "--json", "--acceptpath", "--root", str(isolated_eval_repo)],
    )
    env = json.loads(missing_age.stdout)
    assert missing_age.exit_code == 2
    assert env["errors"][0]["code"] == "EVAL_USAGE"


def test_eval_gc_rejects_invalid_duration(isolated_eval_repo: Path) -> None:
    result = runner.invoke(
        app,
        [
            "eval",
            "gc",
            "--json",
            "--acceptpath",
            "--older-than",
            "7w",
            "--root",
            str(isolated_eval_repo),
        ],
    )
    env = json.loads(result.stdout)
    assert result.exit_code == 2
    assert env["ok"] is False
    assert env["command"] == "eval gc"
    assert env["errors"][0]["code"] == "EVAL_USAGE"


def test_eval_gc_json_envelope(isolated_eval_repo: Path) -> None:
    bundles = _acceptpath(isolated_eval_repo)
    session = _write(bundles / AUTHORITATIVE, "{}")
    index = _write(bundles / DEBRIS_INDEX)
    _age(session, seconds=10_000)
    _age(index, seconds=10_000)

    result = runner.invoke(
        app,
        [
            "eval",
            "gc",
            "--json",
            "--acceptpath",
            "--older-than",
            "1s",
            "--root",
            str(isolated_eval_repo),
        ],
    )
    env = json.loads(result.stdout)
    assert result.exit_code == 0
    assert env["schema_version"] == "cli_output_envelope_v1"
    assert env["command"] == "eval gc"
    assert env["ok"] is True
    data = env["data"]
    assert data["acceptpath"] is True
    assert data["older_than"] == "1s"
    assert data["force"] is False
    assert AUTHORITATIVE in data["preserved"]
    assert DEBRIS_INDEX in data["deleted"]
    assert session.is_file()
    assert not index.exists()


def test_gc_skips_non_regular_and_unmanaged(tmp_path: Path) -> None:
    bundles = _acceptpath(tmp_path)
    index = _write(bundles / DEBRIS_INDEX)
    notes = _write(bundles / "notes.txt", "leave")
    lock = _write(bundles / UNMANAGED_LOCK, "lock")
    legacy = _write(bundles / LEGACY_SESSION, "{}")
    nested = bundles / "subdir"
    nested.mkdir()
    link = bundles / "link.json"
    link.symlink_to(index)
    _age(index, seconds=10_000)
    _age(notes, seconds=10_000)
    _age(lock, seconds=10_000)
    _age(legacy, seconds=10_000)

    result = gc_acceptpath(tmp_path, older_than="1s")
    skipped = {item.path: item.reason for item in result.skipped}
    assert not index.exists()
    assert notes.is_file()
    assert lock.is_file()
    assert legacy.is_file()
    assert nested.is_dir()
    assert link.is_symlink()
    assert skipped["notes.txt"] == "unmanaged"
    assert skipped[UNMANAGED_LOCK] == "unmanaged"
    assert skipped[LEGACY_SESSION] == "unmanaged"
    assert skipped["link.json"] == "non_regular"
    assert skipped["subdir"] == "non_regular"


def test_gc_missing_acceptpath_is_empty(tmp_path: Path) -> None:
    result = gc_acceptpath(tmp_path, older_than="1s")
    assert result.selected == ()
    assert result.deleted == ()
    assert result.preserved == ()
    assert result.skipped == ()


def test_gc_list_failure_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundles = _acceptpath(tmp_path)

    def _boom(self: Path):
        raise OSError("cannot list")

    monkeypatch.setattr(Path, "iterdir", _boom)
    with pytest.raises(GcError) as exc:
        gc_acceptpath(tmp_path, older_than="1s")
    assert bundles.is_dir()
    assert exc.value.code == "EVAL_STORE_INTEGRITY"
    assert exc.value.exit_code == 4


def test_gc_unlink_failure_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundles = _acceptpath(tmp_path)
    index = _write(bundles / DEBRIS_INDEX)
    _age(index, seconds=10_000)
    real_unlink = Path.unlink

    def _boom(self: Path, *args: object, **kwargs: object):
        if self.name == DEBRIS_INDEX:
            raise OSError("permission denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _boom)
    result = gc_acceptpath(tmp_path, older_than="1s")
    assert index.is_file()
    assert DEBRIS_INDEX not in {item.path for item in result.deleted}
    assert any(item.reason.startswith("unlink_failed:") for item in result.skipped)


def test_gc_unsafe_unlink_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import gc as gc_mod

    bundles = _acceptpath(tmp_path)
    index = _write(bundles / DEBRIS_INDEX)
    _age(index, seconds=10_000)
    monkeypatch.setattr(gc_mod, "_safe_to_unlink", lambda *_a, **_k: False)
    result = gc_acceptpath(tmp_path, older_than="1s")
    assert index.is_file()
    assert any(item.path == DEBRIS_INDEX and item.reason == "unsafe_unlink" for item in result.skipped)


def test_gc_path_error_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.binding.paths as binding_paths

    def fail(_root: Path) -> Path:
        raise binding_paths.LayerAPathError("escaped")

    monkeypatch.setattr(binding_paths, "acceptpath_bundles_dir", fail)
    with pytest.raises(GcError) as exc:
        gc_acceptpath(tmp_path, older_than="1s")
    assert exc.value.code == "EVAL_STORE_INTEGRITY"
    assert exc.value.exit_code == 4


def test_eval_gc_human_output(isolated_eval_repo: Path) -> None:
    bundles = _acceptpath(isolated_eval_repo)
    session = _write(bundles / AUTHORITATIVE, "{}")
    index = _write(bundles / DEBRIS_INDEX)
    _age(session, seconds=10_000)
    _age(index, seconds=10_000)
    result = runner.invoke(
        app,
        [
            "eval",
            "gc",
            "--acceptpath",
            "--older-than",
            "1s",
            "--root",
            str(isolated_eval_repo),
        ],
    )
    assert result.exit_code == 0
    assert "eval gc: acceptpath older_than=1s" in result.stdout
    assert "deleted=1" in result.stdout
    assert "preserved=1" in result.stdout
    assert "  deleted:" not in result.stdout
    assert "  preserved:" not in result.stdout
    assert "  would_delete:" not in result.stdout
    assert session.is_file()
    assert not index.exists()


def test_eval_gc_human_usage_and_duration_errors(isolated_eval_repo: Path) -> None:
    missing_scope = runner.invoke(app, ["eval", "gc", "--older-than", "1s"])
    assert missing_scope.exit_code == 2
    scope_text = f"{missing_scope.stdout}{missing_scope.stderr}"
    assert "eval gc requires --acceptpath" in scope_text

    invalid = runner.invoke(
        app,
        [
            "eval",
            "gc",
            "--acceptpath",
            "--older-than",
            "7w",
            "--root",
            str(isolated_eval_repo),
        ],
    )
    assert invalid.exit_code == 2
    duration_text = f"{invalid.stdout}{invalid.stderr}"
    assert "invalid --older-than" in duration_text


def test_eval_gc_human_dry_run(isolated_eval_repo: Path) -> None:
    bundles = _acceptpath(isolated_eval_repo)
    index = _write(bundles / DEBRIS_INDEX)
    _age(index, seconds=10_000)
    result = runner.invoke(
        app,
        [
            "eval",
            "gc",
            "--acceptpath",
            "--older-than",
            "1s",
            "--dry-run",
            "--root",
            str(isolated_eval_repo),
        ],
    )
    assert result.exit_code == 0
    assert "deleted=0" in result.stdout
    assert "  would_delete: index.json" in result.stdout
    assert "  deleted:" not in result.stdout
    assert index.is_file()


def test_gc_classifies_escaped_child_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundles = _acceptpath(tmp_path)
    child = _write(bundles / "escaped.json")
    _age(child, seconds=10_000)
    real_resolve = Path.resolve

    def resolve(self: Path, *args: object, **kwargs: object) -> Path:
        if self == child:
            return tmp_path / "outside" / child.name
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    result = gc_acceptpath(tmp_path, older_than="1s")
    assert any(item.path == child.name and item.reason == "escaped_path" for item in result.skipped)
    assert child.is_file()


def test_gc_classifies_unresolvable_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundles = _acceptpath(tmp_path)
    child = _write(bundles / "unresolvable.json")
    _age(child, seconds=10_000)
    real_resolve = Path.resolve

    def resolve(self: Path, *args: object, **kwargs: object) -> Path:
        if self == child:
            raise OSError("resolve failed")
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    result = gc_acceptpath(tmp_path, older_than="1s")
    assert any(item.path == child.name and item.reason == "unresolvable" for item in result.skipped)
    assert child.is_file()


def test_gc_classifies_unreadable_mtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundles = _acceptpath(tmp_path)
    child = _write(bundles / "unreadable.json")
    _age(child, seconds=10_000)
    real_stat = Path.stat

    class _UnreadableMtime:
        def __init__(self, inner: object) -> None:
            self._inner = inner

        def __getattr__(self, name: str) -> object:
            return getattr(self._inner, name)

        @property
        def st_mtime(self) -> float:
            raise OSError("mtime unavailable")

    def stat(self: Path, *args: object, **kwargs: object):
        result = real_stat(self, *args, **kwargs)
        if self == child:
            return _UnreadableMtime(result)
        return result

    monkeypatch.setattr(Path, "stat", stat)
    result = gc_acceptpath(tmp_path, older_than="1s")
    assert any(item.path == child.name and item.reason == "unreadable_mtime" for item in result.skipped)
    assert child.is_file()


def test_eval_gc_human_error_includes_hint(isolated_eval_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import gc as gc_mod

    def fail(*args: object, **kwargs: object):
        raise gc_mod.GcError(
            "cannot inspect acceptpath",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
            hint="check the repository metadata",
        )

    monkeypatch.setattr(gc_mod, "gc_acceptpath", fail)
    result = runner.invoke(
        app,
        ["eval", "gc", "--acceptpath", "--older-than", "1s", "--root", str(isolated_eval_repo)],
    )
    text = f"{result.stdout}{result.stderr}"
    assert result.exit_code == 4
    assert "eval gc: cannot inspect acceptpath (hint: check the repository metadata)" in text


def test_eval_gc_human_repo_unresolvable(isolated_eval_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.binding.paths as binding_paths

    def fail(start: Path | None = None) -> Path:
        raise binding_paths.RepoRootUnresolvedError("repository unavailable")

    monkeypatch.setattr(binding_paths, "resolve_repo_root", fail)
    result = runner.invoke(app, ["eval", "gc", "--acceptpath", "--older-than", "1s"])
    text = f"{result.stdout}{result.stderr}"
    assert result.exit_code == 1
    assert "eval gc: repo root unresolvable: repository unavailable" in text


def test_eval_gc_store_integrity_not_repo_unresolvable(
    isolated_eval_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import git_cg.eval.binding.paths as binding_paths

    def fail(_root: Path) -> Path:
        raise binding_paths.LayerAPathError("escaped")

    monkeypatch.setattr(binding_paths, "acceptpath_bundles_dir", fail)
    result = runner.invoke(
        app,
        ["eval", "gc", "--json", "--acceptpath", "--older-than", "1s", "--root", str(isolated_eval_repo)],
    )
    assert result.exit_code == 4
    env = json.loads(result.stdout)
    codes = [err.get("code") for err in env.get("errors", [])]
    assert "EVAL_STORE_INTEGRITY" in codes
    assert "EVAL_REPO_UNRESOLVABLE" not in codes
