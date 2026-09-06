"""Lazy public exports on ``git_cg.eval.binding``.

The package is import-light: ``__getattr__`` resolves locked public names on
first access, caches them on the module, and raises ``AttributeError`` for
unknown names. Import failures from real submodules propagate; there is no
missing-module fallback.

No network. No Opik. No product-accept mutation.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from types import ModuleType

import pytest

_EXPORT_MODULES = {
    "AcceptBindResult": "git_cg.eval.binding.accept_hook",
    "bind_accept_path": "git_cg.eval.binding.accept_hook",
    "BindInput": "git_cg.eval.binding.binder",
    "BindResult": "git_cg.eval.binding.binder",
    "bind_final_accept": "git_cg.eval.binding.binder",
    "bind_unbound": "git_cg.eval.binding.binder",
    "message_sha256_bytes": "git_cg.eval.binding.binder",
    "build_message_versions": "git_cg.eval.binding.message_versions",
    "capture_enabled": "git_cg.eval.binding.profiles",
    "build_session_twin": "git_cg.eval.binding.session_thread",
    "write_session_twin": "git_cg.eval.binding.session_thread",
    "DECLARED_STAGES": "git_cg.eval.binding.trajectory",
    "build_trajectory_evidence": "git_cg.eval.binding.trajectory",
}


def _drop_lazy_exports(pkg: ModuleType) -> None:
    """Remove cached public names so the next attribute lookup runs ``__getattr__``."""
    for name in pkg.__all__:
        pkg.__dict__.pop(name, None)


@pytest.fixture
def binding_pkg() -> Iterator[ModuleType]:
    pkg = importlib.import_module("git_cg.eval.binding")
    _drop_lazy_exports(pkg)
    yield pkg
    _drop_lazy_exports(pkg)


def test_all_public_exports_resolve_to_submodule_symbols(binding_pkg: ModuleType) -> None:
    assert set(binding_pkg.__all__) == set(_EXPORT_MODULES)
    for name, module_name in _EXPORT_MODULES.items():
        owner = importlib.import_module(module_name)
        resolved = getattr(binding_pkg, name)
        assert resolved is getattr(owner, name)
        assert binding_pkg.__dict__[name] is resolved


def test_unknown_attribute_raises_attribute_error(binding_pkg: ModuleType) -> None:
    """Unknown names fail closed; no silent fallback and no invented export."""
    with pytest.raises(AttributeError, match="has no attribute 'not_a_public_export'"):
        _ = binding_pkg.not_a_public_export


def test_dir_includes_globals_and_public_exports(binding_pkg: ModuleType) -> None:
    names = dir(binding_pkg)
    for public_name in binding_pkg.__all__:
        assert public_name in names
    assert "__getattr__" in names
    assert "__dir__" in names
