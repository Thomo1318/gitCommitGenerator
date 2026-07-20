"""Unit tests for resolve_model_name model inventory fallback."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import openai

from git_cg.main import resolve_model_name


class _Model:
    def __init__(self, model_id: str) -> None:
        self.id = model_id


class _ModelsAPI:
    def __init__(self, ids: list[str] | None = None, *, error: Exception | None = None) -> None:
        self._ids = ids or []
        self._error = error

    def list(self):
        if self._error is not None:
            raise self._error
        return SimpleNamespace(data=[_Model(i) for i in self._ids])


class _Client:
    def __init__(self, ids: list[str] | None = None, *, error: Exception | None = None) -> None:
        self.models = _ModelsAPI(ids, error=error)


class _InstructorLike:
    """Mimic instructor wrapper exposing raw client as ``.client``."""

    def __init__(self, ids: list[str]) -> None:
        self.client = _Client(ids)
        # No top-level models attribute on purpose.


def test_preferred_hit_returns_preferred():
    assert resolve_model_name(_Client(["a", "b"]), preferred="b") == "b"


def test_preferred_miss_falls_back_to_first_available(capsys):
    chosen = resolve_model_name(_Client(["a", "b"]), preferred="missing")
    assert chosen == "a"
    captured = capsys.readouterr()
    output = captured.out + captured.err
    # rich prints to stdout typically
    assert "missing" in output


def test_empty_preferred_uses_first_available():
    assert resolve_model_name(_Client(["x", "y"]), preferred="") == "x"
    assert resolve_model_name(_Client(["x", "y"]), preferred="   ") == "x"


def test_empty_inventory_keeps_preferred():
    assert resolve_model_name(_Client([]), preferred="configured") == "configured"


def test_empty_inventory_and_empty_preferred_defaults():
    assert resolve_model_name(_Client([]), preferred="") == "default"


def test_list_failure_keeps_preferred():
    client = _Client(error=openai.APIConnectionError(request=httpx.Request("GET", "http://x")))
    assert resolve_model_name(client, preferred="pref") == "pref"


def test_list_failure_empty_preferred_defaults():
    client = _Client(error=AttributeError("no models"))
    assert resolve_model_name(client, preferred="") == "default"


def test_instructor_wrapper_uses_nested_client():
    assert resolve_model_name(_InstructorLike(["nested-a", "nested-b"]), preferred="nested-b") == "nested-b"
    assert resolve_model_name(_InstructorLike(["nested-a"]), preferred="gone") == "nested-a"
