"""S3 Layer-A path law coverage (Issue #231, D13 / N19.3 / N20.5).

Surgical branch coverage for ``git_cg.eval.binding.paths``:

* ``_run_git`` failure modes (OSError, subprocess error, nonzero exit, empty stdout)
* ``resolve_repo_root`` primary/fallback/unresolved paths
* containment resolve failures
* ``trajectories_dir`` / ``eval_tree_root``
* ``atomic_write_json`` cleanup on write failure + best-effort dir fsync

No network. No Opik. No product-accept mutation.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from git_cg.eval.binding import paths as binding_paths


class TestRunGit:
    def test_oserror_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(OSError("git missing")))
        assert binding_paths._run_git(["rev-parse", "--show-toplevel"], tmp_path) is None

    def test_subprocess_error_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*_a, **_k):
            raise subprocess.TimeoutExpired(cmd="git", timeout=1)

        monkeypatch.setattr(subprocess, "run", _boom)
        assert binding_paths._run_git(["status"], tmp_path) is None

    def test_nonzero_returncode_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_a, **_k: SimpleNamespace(returncode=128, stdout="fatal: not a git repository\n"),
        )
        assert binding_paths._run_git(["rev-parse", "--show-toplevel"], tmp_path) is None

    def test_empty_stdout_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_a, **_k: SimpleNamespace(returncode=0, stdout="   \n"),
        )
        assert binding_paths._run_git(["rev-parse", "--show-toplevel"], tmp_path) is None

    def test_success_strips_stdout(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_a, **_k: SimpleNamespace(returncode=0, stdout=f"  {tmp_path}  \n"),
        )
        assert binding_paths._run_git(["rev-parse", "--show-toplevel"], tmp_path) == str(tmp_path)


class TestResolveRepoRoot:
    def test_start_path_resolve_oserror(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        class BoomStart:
            def resolve(self):
                raise OSError("cannot resolve start")

        # resolve_repo_root wraps start in Path(...); intercept that constructor.
        real_path = binding_paths.Path

        def factory(value=None, *args, **kwargs):
            if value is not None and not args and not kwargs and getattr(factory, "_once", True):
                # Only the initial start wrap should boom; later Path uses stay real.
                factory._once = False  # type: ignore[attr-defined]
                return BoomStart()
            return real_path(value, *args, **kwargs) if value is not None else real_path(*args, **kwargs)

        monkeypatch.setattr(binding_paths, "Path", factory)
        with pytest.raises(binding_paths.RepoRootUnresolvedError, match="cannot resolve start path"):
            binding_paths.resolve_repo_root(tmp_path)

    def test_show_toplevel_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        monkeypatch.setattr(
            binding_paths,
            "_run_git",
            lambda args, cwd: str(root) if args == ["rev-parse", "--show-toplevel"] else None,
        )
        assert binding_paths.resolve_repo_root(tmp_path) == root.resolve()

    def test_show_toplevel_resolve_oserror_falls_back_to_absolute(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        monkeypatch.setattr(
            binding_paths,
            "_run_git",
            lambda args, cwd: str(root) if args == ["rev-parse", "--show-toplevel"] else None,
        )

        real_path = binding_paths.Path
        resolve_calls: list[str] = []

        class FallbackPath(type(real_path())):  # type: ignore[misc]
            def __new__(cls, *args, **kwargs):
                return super().__new__(cls, *args, **kwargs)

            def resolve(self, strict: bool = False):  # type: ignore[override]
                resolve_calls.append(str(self))
                if str(self) in {str(root), str(root.absolute())}:
                    raise OSError("resolve blocked")
                return real_path(self).resolve(strict=strict)

            def absolute(self):  # type: ignore[override]
                return real_path(str(self)).absolute()

            def is_dir(self):  # type: ignore[override]
                return real_path(str(self)).is_dir()

        def factory(*args, **kwargs):
            p = real_path(*args, **kwargs)
            # Only wrap the toplevel candidate path.
            if str(p) in {str(root), str(root.resolve()), str(root.absolute())}:
                return FallbackPath(str(p))
            return p

        monkeypatch.setattr(binding_paths, "Path", factory)
        got = binding_paths.resolve_repo_root(tmp_path)
        assert got == root.absolute()
        assert resolve_calls  # ensure resolve branch was hit

    def test_git_dir_dot_git_parent_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = tmp_path / "work"
        git = repo / ".git"
        git.mkdir(parents=True)

        def _run(args, cwd):
            if args == ["rev-parse", "--show-toplevel"]:
                return None
            if args == ["rev-parse", "--git-dir"]:
                return str(git)
            return None

        monkeypatch.setattr(binding_paths, "_run_git", _run)
        assert binding_paths.resolve_repo_root(repo) == repo.resolve()

    def test_git_dir_relative_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = tmp_path / "work"
        (repo / ".git").mkdir(parents=True)

        def _run(args, cwd):
            if args == ["rev-parse", "--show-toplevel"]:
                return None
            if args == ["rev-parse", "--git-dir"]:
                return ".git"
            return None

        monkeypatch.setattr(binding_paths, "_run_git", _run)
        assert binding_paths.resolve_repo_root(repo) == repo.resolve()

    def test_bare_git_dir_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bare = tmp_path / "bare.git"
        bare.mkdir()

        def _run(args, cwd):
            if args == ["rev-parse", "--show-toplevel"]:
                return None
            if args == ["rev-parse", "--git-dir"]:
                return str(bare)
            return None

        monkeypatch.setattr(binding_paths, "_run_git", _run)
        assert binding_paths.resolve_repo_root(tmp_path) == bare.resolve()

    def test_git_dir_resolve_oserror_uses_absolute(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bare = tmp_path / "odd-git-dir"
        bare.mkdir()

        def _run(args, cwd):
            if args == ["rev-parse", "--show-toplevel"]:
                return None
            if args == ["rev-parse", "--git-dir"]:
                return str(bare)
            return None

        monkeypatch.setattr(binding_paths, "_run_git", _run)
        real_path = binding_paths.Path

        class FallbackPath(type(real_path())):  # type: ignore[misc]
            def resolve(self, strict: bool = False):  # type: ignore[override]
                if str(self) in {str(bare), str(bare.absolute())}:
                    raise OSError("resolve blocked")
                return real_path(self).resolve(strict=strict)

            def absolute(self):  # type: ignore[override]
                return real_path(str(self)).absolute()

            def is_dir(self):  # type: ignore[override]
                return True

            @property
            def name(self):  # type: ignore[override]
                return "odd-git-dir"

        def factory(*args, **kwargs):
            p = real_path(*args, **kwargs)
            if str(p) in {str(bare), str(bare.resolve()), str(bare.absolute())}:
                return FallbackPath(str(p))
            return p

        monkeypatch.setattr(binding_paths, "Path", factory)
        got = binding_paths.resolve_repo_root(tmp_path)
        assert got == bare.absolute()

    def test_unresolvable_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(binding_paths, "_run_git", lambda *_a, **_k: None)
        with pytest.raises(binding_paths.RepoRootUnresolvedError, match="repo_root_unresolved"):
            binding_paths.resolve_repo_root(tmp_path)

    def test_toplevel_non_dir_falls_through_to_git_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        not_dir = tmp_path / "not-a-dir.txt"
        not_dir.write_text("x", encoding="utf-8")
        bare = tmp_path / "bare.git"
        bare.mkdir()

        def _run(args, cwd):
            if args == ["rev-parse", "--show-toplevel"]:
                return str(not_dir)
            if args == ["rev-parse", "--git-dir"]:
                return str(bare)
            return None

        monkeypatch.setattr(binding_paths, "_run_git", _run)
        assert binding_paths.resolve_repo_root(tmp_path) == bare.resolve()


class TestTreeHelpersAndContainment:
    def test_eval_tree_root_and_trajectories_dir(self, tmp_path: Path) -> None:
        root = binding_paths.eval_tree_root(tmp_path)
        assert root == tmp_path.resolve() / ".eval"
        traj = binding_paths.trajectories_dir(tmp_path)
        assert traj == tmp_path.resolve() / ".eval" / "trajectories"
        sessions = binding_paths.sessions_dir(tmp_path)
        assert sessions == tmp_path.resolve() / ".eval" / "sessions"

    def test_s6_store_dir_helpers_are_contained(self, tmp_path: Path) -> None:
        """S6 Layer-A stores resolve under .eval/ with containment (no creation)."""
        root = tmp_path.resolve()
        expected = {
            "checkpoints": binding_paths.checkpoints_dir(root),
            "review_queue": binding_paths.review_queue_dir(root),
            "dogfood": binding_paths.dogfood_dir(root),
            "amend_briefs": binding_paths.amend_briefs_dir(root),
            "diagnostics": binding_paths.diagnostics_dir(root),
            "issues": binding_paths.issues_dir(root),
            "replays": binding_paths.replays_dir(root),
            "index": binding_paths.index_dir(root),
            "train_export": binding_paths.train_export_dir(root),
            "antipattern_vault": binding_paths.antipattern_vault_dir(root),
        }
        for name, path in expected.items():
            assert path == root / ".eval" / name
            assert not path.exists()  # helpers do not create
        # No quarantine store primitive (field-level only).
        assert not hasattr(binding_paths, "quarantine_dir")

    def test_contained_target_resolve_oserror(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        root = tmp_path.resolve()
        real_resolve = Path.resolve
        state = {"n": 0}

        def _resolve(self, *a, **k):
            state["n"] += 1
            # First resolve is repo_root; second is existing ancestor for target.
            if state["n"] == 2:
                raise OSError("cannot resolve containment path")
            return real_resolve(self, *a, **k)

        monkeypatch.setattr(binding_paths.Path, "resolve", _resolve)
        with pytest.raises(binding_paths.LayerAPathError, match="cannot resolve containment path"):
            binding_paths._contained(root, Path("sessions") / "x.json")

    def test_contained_tree_root_resolve_oserror(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Force the tree_norm OSError branch after target resolution succeeds."""
        root = tmp_path.resolve()
        real_resolve = Path.resolve
        state = {"n": 0}

        def _resolve(self, *a, **k):
            state["n"] += 1
            # 1: repo_root, 2: existing ancestor for target, 3: tree.parent.resolve()
            if state["n"] >= 3:
                raise OSError("cannot resolve .eval containment root")
            return real_resolve(self, *a, **k)

        monkeypatch.setattr(binding_paths.Path, "resolve", _resolve)
        with pytest.raises(binding_paths.LayerAPathError, match=r"cannot resolve \.eval containment root"):
            binding_paths._contained(root, Path("sessions") / "x.json")

    def test_contained_when_eval_already_exists(self, tmp_path: Path) -> None:
        """Hit tree_norm.exists() True branch (resolve existing .eval root)."""
        root = tmp_path.resolve()
        (root / ".eval").mkdir()
        out = binding_paths._contained(root, Path("sessions") / "x.json")
        assert out == root / ".eval" / "sessions" / "x.json"

    def test_contained_when_tree_parent_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Hit tree.parent.exists() False branch via a synthetic missing parent."""
        root = tmp_path.resolve()
        real_exists = Path.exists

        def _exists(self):
            # Pretend repo root parent does not exist only for the tree.parent check.
            if str(self) == str(root):
                # existing ancestor resolve path still needs root to exist
                return True
            if str(self) == str(root.parent):
                return False
            return real_exists(self)

        monkeypatch.setattr(binding_paths.Path, "exists", _exists)
        out = binding_paths._contained(root, Path("sessions") / "x.json")
        assert str(out).endswith(str(Path(".eval") / "sessions" / "x.json"))


class TestAtomicWriteJson:
    def test_write_success_roundtrip(self, tmp_path: Path) -> None:
        out = tmp_path / ".eval" / "bundles" / "acceptpath" / "sess_x.json"
        written = binding_paths.atomic_write_json(out, {"a": 1, "b": 2})
        assert written == out
        assert json.loads(out.read_text(encoding="utf-8")) == {"a": 1, "b": 2}
        assert list(out.parent.glob("*.tmp")) == []

    def test_write_failure_cleans_temp_and_reraises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        out = tmp_path / ".eval" / "sessions" / "sess_y.json"
        binding_paths._ensure_dir(out.parent)

        def _boom_replace(src, dst):
            raise OSError("replace failed")

        monkeypatch.setattr(os, "replace", _boom_replace)
        with pytest.raises(OSError, match="replace failed"):
            binding_paths.atomic_write_json(out, {"k": "v"})
        assert list(out.parent.glob("*.tmp")) == []
        assert not out.exists()

    def test_parent_fsync_oserror_is_best_effort(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        out = tmp_path / ".eval" / "trajectories" / "traj_z.json"
        real_fsync = os.fsync
        calls = {"n": 0}

        def _fsync(fd):
            calls["n"] += 1
            # First fsync is the file handle; second is the directory fd.
            if calls["n"] >= 2:
                raise OSError("dir fsync unsupported")
            return real_fsync(fd)

        monkeypatch.setattr(os, "fsync", _fsync)
        written = binding_paths.atomic_write_json(out, {"ok": True})
        assert written.exists()
        assert json.loads(written.read_text(encoding="utf-8"))["ok"] is True

    def test_git_dir_dot_git_parent_not_dir_falls_through(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cover parent.is_dir() False then git_dir.is_dir() True (bare-ish)."""
        start = tmp_path / "work"
        start.mkdir()
        # Create a real bare-like git dir named something else first...
        # Simulate rev-parse --git-dir returning a path ending in .git whose parent is a file.
        parent_as_file = tmp_path / "notadir"
        parent_as_file.write_text("x", encoding="utf-8")
        # Instead: git-dir path is `<file>/.git` so parent is a file → is_dir False,
        # then git_dir itself does not exist → is_dir False → unresolved.
        monkeypatch.setattr(
            binding_paths,
            "_run_git",
            lambda args, cwd: None if "show-toplevel" in args else str(parent_as_file / ".git"),
        )
        with pytest.raises(binding_paths.RepoRootUnresolvedError):
            binding_paths.resolve_repo_root(start)

    def test_git_dir_named_git_with_non_dir_parent_but_git_dir_is_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cover .git name + parent not dir, then bare git_dir.is_dir True via rename trick.

        We cannot make Path.parent of `x/.git` be a non-dir while `x/.git` is a dir
        on a real FS. Instead force parent.is_dir False via monkeypatch while the
        git_dir path itself is a real directory (unusual layout fallback).
        """
        start = tmp_path / "work"
        start.mkdir()
        git_dir = tmp_path / "weird.git"
        git_dir.mkdir()
        real_is_dir = Path.is_dir

        def _is_dir(self):
            # Make the synthetic parent check fail only for git_dir.parent when name==.git
            # We return a git-dir that is NOT named .git so first branch is skipped,
            # then is_dir True returns git_dir (already covered). To hit 128->130:
            # return path ending with .git
            return real_is_dir(self)

        # Craft: git_dir path = tmp/repo/.git where tmp/repo is a FILE? Impossible.
        # Monkeypatch parent property check:
        git_path = tmp_path / "repo" / ".git"
        git_path.mkdir(parents=True)

        def _run(args, cwd):
            if "show-toplevel" in args:
                return None
            return str(git_path)

        monkeypatch.setattr(binding_paths, "_run_git", _run)

        real_parent_is_dir = type(git_path).is_dir

        def _is_dir2(self):
            # When checking parent of .git, return False once; when checking git_dir, True
            s = str(self)
            if s == str(git_path.parent):
                return False
            return real_parent_is_dir(self)

        monkeypatch.setattr(binding_paths.Path, "is_dir", _is_dir2)
        # parent not dir → skip return parent; git_dir is dir → return git_dir
        out = binding_paths.resolve_repo_root(start)
        assert out == git_path.resolve()

    def test_git_dir_not_dir_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cover git_dir.is_dir() False → repo_root_unresolved (130->134)."""
        start = tmp_path / "work"
        start.mkdir()
        ghost = tmp_path / "missing-git-dir"
        monkeypatch.setattr(
            binding_paths,
            "_run_git",
            lambda args, cwd: None if "show-toplevel" in args else str(ghost),
        )
        with pytest.raises(binding_paths.RepoRootUnresolvedError, match="repo_root_unresolved"):
            binding_paths.resolve_repo_root(start)


def test_paths_import_does_not_load_binder() -> None:
    """Import-light law: binding.paths must not pull binder/accept-hook.

    Package ``__init__`` is lazy so doctor/CLI Layer-A discovery can import
    paths without caching the accept-path binder composition graph.
    """
    import subprocess
    import sys

    probe = """
import sys
import git_cg.eval.binding.paths  # noqa: F401

forbidden = {
    "git_cg.eval.binding.binder",
    "git_cg.eval.binding.accept_hook",
    "git_cg.eval.binding.message_versions",
    "git_cg.eval.binding.session_thread",
    "git_cg.eval.binding.trajectory",
}
bad = sorted(
    name
    for name in sys.modules
    if name in forbidden or name == "opik" or name.startswith("opik.")
)
if bad:
    raise SystemExit("unexpected modules: " + ", ".join(bad))
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, (
        "importing git_cg.eval.binding.paths must not load binder/accept-hook/opik; "
        f"stderr={completed.stderr!r} stdout={completed.stdout!r}"
    )


def test_binding_package_lazy_public_api_still_resolves() -> None:
    """Lazy package exports must preserve the locked public attribute surface."""
    import importlib

    pkg = importlib.import_module("git_cg.eval.binding")
    capture_enabled = pkg.capture_enabled
    assert callable(capture_enabled)
    assert pkg.BindInput is not None
    assert callable(pkg.bind_final_accept)
    assert callable(pkg.bind_unbound)
    assert callable(pkg.message_sha256_bytes)
    assert "BindInput" in dir(pkg)
