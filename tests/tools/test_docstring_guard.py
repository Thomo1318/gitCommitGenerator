"""Tests for tools/docstring_guard.py (placement + write-if-green)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GUARD_PATH = REPO / "tools" / "docstring_guard.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("docstring_guard", GUARD_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


guard = _load_guard()


SAMPLE = """\
def public_fn(x: int) -> int:
    return x


def _helper(x: int) -> int:
    return x + 1


class Box:
    def _method(self) -> str:
        return "ok"


class Proto:
    def hook(self) -> None: ...


def _multi(
    a: int,
    b: int,
) -> int:
    return a + b
"""


def test_analyze_private_only_defaults(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text(SAMPLE, encoding="utf-8")
    missing = guard.analyze_source(path.read_text(encoding="utf-8"), path=path)
    names = {m.name for m in missing}
    assert "_helper" in names
    assert "_method" in names
    assert "_multi" in names
    assert "public_fn" not in names
    assert "hook" not in names  # public method and same-line ellipsis path


def test_same_line_ellipsis_skipped(tmp_path: Path) -> None:
    path = tmp_path / "proto.py"
    path.write_text("class P:\n    def hook(self) -> None: ...\n", encoding="utf-8")
    missing = guard.analyze_source(
        path.read_text(encoding="utf-8"),
        path=path,
        private_only=False,
        include_public=True,
    )
    # Public class P is also missing a docstring when include_public=True.
    by_qual = {m.qualname: m for m in missing}
    assert set(by_qual) == {"P", "P.hook"}
    assert by_qual["P.hook"].status == "skip_same_line_ellipsis"
    assert by_qual["P"].status == "ok_to_insert"


def test_multiline_protocol_ok_to_insert(tmp_path: Path) -> None:
    src = """\
class P:
    def hook(
        self,
        x: int,
    ) -> None:
        ...
"""
    path = tmp_path / "proto2.py"
    path.write_text(src, encoding="utf-8")
    missing = guard.analyze_source(
        path.read_text(encoding="utf-8"),
        path=path,
        private_only=False,
        include_public=True,
    )
    # Public class P remains in scope under include_public=True.
    by_qual = {m.qualname: m for m in missing}
    assert set(by_qual) == {"P", "P.hook"}
    assert by_qual["P.hook"].status == "ok_to_insert"
    assert by_qual["P.hook"].insert_lineno is not None
    assert by_qual["P"].status == "ok_to_insert"


def test_apply_write_if_green(tmp_path: Path) -> None:
    path = tmp_path / "mod.py"
    path.write_text("def _h() -> int:\n    return 1\n", encoding="utf-8")
    result = guard.apply_one(
        path,
        qualname=None,
        symbol="_h",
        text="Return the sentinel one.",
        private_only=True,
        include_public=False,
        dry_run=False,
    )
    assert result.ok, result.detail
    text = path.read_text(encoding="utf-8")
    assert '"""Return the sentinel one."""' in text
    guard.validate_source(text, filename=str(path))


def test_apply_dry_run_does_not_write(tmp_path: Path) -> None:
    path = tmp_path / "mod.py"
    original = "def _h() -> int:\n    return 1\n"
    path.write_text(original, encoding="utf-8")
    result = guard.apply_one(
        path,
        qualname="_h",
        symbol=None,
        text="Dry run line.",
        private_only=True,
        include_public=False,
        dry_run=True,
    )
    assert result.ok
    assert path.read_text(encoding="utf-8") == original


def test_refuse_stub_and_google_only() -> None:
    with pytest.raises(ValueError, match="coverage stub"):
        guard._format_docstring("TODO", "    ")
    google_only = "Args:" + "\n" + "    x: int"
    with pytest.raises(ValueError, match="Google section"):
        guard._format_docstring(google_only, "    ")
    both = "a " + '"""' + "b" + '"""' + " c " + "'''" + "d" + "'''"
    with pytest.raises(ValueError, match="both triple"):
        guard._format_docstring(both, "    ")


def test_manifest_apply(tmp_path: Path) -> None:
    path = tmp_path / "m.py"
    path.write_text("def _a() -> None:\n    return None\n", encoding="utf-8")
    manifest = tmp_path / "m.json"
    # Use absolute path so REPO_ROOT join is not required
    manifest.write_text(
        json.dumps([{"path": str(path), "symbol": "_a", "text": "No-op private helper."}]),
        encoding="utf-8",
    )
    results = guard.apply_manifest(manifest, private_only=True, include_public=False, dry_run=False)
    assert len(results) == 1
    assert results[0].ok, results[0].detail
    assert "No-op private helper." in path.read_text(encoding="utf-8")


def test_cli_check_json(tmp_path: Path) -> None:
    path = tmp_path / "c.py"
    path.write_text("def _z() -> int:\n    return 0\n", encoding="utf-8")
    code = guard.main(["check", "--json", str(path)])
    assert code == 0


def test_insert_does_not_break_multiline_signature(tmp_path: Path) -> None:
    src = """\
def _multi(
    a: int,
    b: int,
) -> int:
    return a + b
"""
    path = tmp_path / "multi.py"
    path.write_text(src, encoding="utf-8")
    result = guard.apply_one(
        path,
        qualname="_multi",
        symbol=None,
        text="Add two integers.",
        private_only=True,
        include_public=False,
        dry_run=False,
    )
    assert result.ok, result.detail
    text = path.read_text(encoding="utf-8")
    # Docstring must land after the header closes, not among params.
    assert 'b: int,\n) -> int:\n    """Add two integers."""\n    return' in text
    guard.validate_source(text, filename=str(path))
