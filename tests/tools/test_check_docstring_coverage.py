"""Tests for tools/check_docstring_coverage.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "check_docstring_coverage.py"
BINDING = REPO / "src" / "git_cg" / "eval" / "binding"


def _load():
    spec = importlib.util.spec_from_file_location("check_docstring_coverage", TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


cov = _load()


PUBLIC_OK = '''\
"""Public module docstring."""

class Box:
    """A documented public class."""

    def paint(self) -> None:
        """Paint the box."""

    def __str__(self) -> str:
        return "box"

    def _private(self) -> None:
        return None

def public_fn() -> int:
    """Return one."""
    return 1

async def public_async() -> int:
    """Return one asynchronously."""
    return 1

def _helper() -> int:
    return 2

class _Hidden:
    def leak(self) -> None:
        return None
'''

PUBLIC_GAPPED = '''\
"""Public module docstring."""

class Box:
    """A documented public class."""

    def paint(self) -> None:
        return None

def public_fn() -> int:
    return 1
'''


def _write(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return path


def test_counts_public_and_excludes_private_dunder_and_nested() -> None:
    source = (
        PUBLIC_OK
        + "\n"
        + '''\
def outer() -> None:
    """Outer public function."""
    def nested() -> None:
        return None
    class Nested:
        def method(self) -> None:
            return None
'''
    )
    items = cov.analyze_source(source, module_name="sample")
    names = [item.name for item in items]
    assert names == [
        "sample",
        "sample.Box",
        "sample.Box.paint",
        "sample.public_fn",
        "sample.public_async",
        "sample.outer",
    ]
    assert all(item.documented for item in items)
    assert "sample.Box.__str__" not in names
    assert "sample.Box._private" not in names
    assert "sample._helper" not in names
    assert "sample._Hidden" not in names
    assert "sample._Hidden.leak" not in names
    assert "sample.outer.nested" not in names
    assert "sample.outer.Nested" not in names


def test_blank_docstring_counts_as_missing() -> None:
    source = '''\
""" """

class Box:
    """   """

    def paint(self) -> None:
        """"""
'''
    items = cov.analyze_source(source, module_name="blank")
    assert [item.name for item in items] == ["blank", "blank.Box", "blank.Box.paint"]
    assert all(not item.documented for item in items)


def test_analyze_path_reports_percent_and_missing(tmp_path: Path) -> None:
    _write(tmp_path, "sample.py", PUBLIC_GAPPED)
    report = cov.analyze_path(tmp_path, threshold=80.0)
    assert report.total == 4
    assert report.documented_count == 2
    assert report.percent == 50.0
    assert report.missing == ("sample.Box.paint", "sample.public_fn")
    assert report.meets_threshold() is False


def test_threshold_pass_and_fail(tmp_path: Path) -> None:
    _write(tmp_path, "sample.py", PUBLIC_GAPPED)
    failing = cov.analyze_path(tmp_path, threshold=80.0)
    passing = cov.analyze_path(tmp_path, threshold=50.0)
    assert failing.meets_threshold() is False
    assert passing.meets_threshold() is True


def test_empty_directory_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no Python files"):
        cov.analyze_path(tmp_path)


def test_missing_path_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        cov.analyze_path(tmp_path / "missing")


def test_skips_symlinked_python_files(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _write(outside, "escape.py", PUBLIC_OK)
    scoped = tmp_path / "scoped"
    scoped.mkdir()
    (scoped / "escape.py").symlink_to(outside / "escape.py")
    with pytest.raises(ValueError, match="no Python files"):
        cov.analyze_path(scoped)


def test_does_not_recurse_into_subdirectories(tmp_path: Path) -> None:
    _write(tmp_path, "sample.py", PUBLIC_OK)
    nested = tmp_path / "nested"
    nested.mkdir()
    _write(nested, "inner.py", PUBLIC_GAPPED)
    report = cov.analyze_path(tmp_path)
    assert all(item.name.startswith("sample") for item in report.items)
    assert not any(item.name.startswith("inner") for item in report.items)


def test_main_pass_exit_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "sample.py", PUBLIC_OK)
    code = cov.main([str(tmp_path), "--threshold", "80"])
    captured = capsys.readouterr()
    assert code == 0
    assert "OK:" in captured.out
    assert "missing:" not in captured.out


def test_main_fail_lists_missing_and_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "sample.py", PUBLIC_GAPPED)
    code = cov.main([str(tmp_path), "--threshold", "80"])
    captured = capsys.readouterr()
    assert code == 2
    assert "sample.Box.paint" in captured.out
    assert "sample.public_fn" in captured.out
    assert "below threshold" in captured.err


def test_main_parse_error_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "broken.py", "def broken(:\n    pass\n")
    code = cov.main([str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 1
    assert "cannot parse" in captured.err


def test_main_missing_path_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = cov.main([str(tmp_path / "nope")])
    captured = capsys.readouterr()
    assert code == 1
    assert "does not exist" in captured.err


def test_main_negative_threshold_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "sample.py", PUBLIC_OK)
    code = cov.main([str(tmp_path), "--threshold", "-1"])
    captured = capsys.readouterr()
    assert code == 1
    assert "threshold" in captured.err


def test_cli_subprocess_pass_and_fail(tmp_path: Path) -> None:
    ok = tmp_path / "ok"
    ok.mkdir()
    _write(ok, "sample.py", PUBLIC_OK)
    passing = subprocess.run(
        [sys.executable, str(TOOL), str(ok), "--threshold", "80"],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert passing.returncode == 0, passing.stderr
    assert "OK:" in passing.stdout

    gapped = tmp_path / "gapped"
    gapped.mkdir()
    _write(gapped, "sample.py", PUBLIC_GAPPED)
    failing = subprocess.run(
        [sys.executable, str(TOOL), str(gapped), "--threshold", "80"],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert failing.returncode == 2
    assert "sample.Box.paint" in failing.stdout
    assert "below threshold" in failing.stderr


def test_main_default_path_is_binding(capsys: pytest.CaptureFixture[str]) -> None:
    code = cov.main([])
    captured = capsys.readouterr()
    assert code == 0
    assert "OK:" in captured.out
    assert "src/git_cg/eval/binding" in captured.out


def test_binding_package_meets_default_threshold() -> None:
    report = cov.analyze_path(BINDING, threshold=80.0)
    assert report.total > 0
    assert report.meets_threshold(), report.missing
    assert report.missing == ()
