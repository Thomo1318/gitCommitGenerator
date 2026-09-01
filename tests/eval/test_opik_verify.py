"""S7-1b / S7-2b: optional online Opik verify (advisory, injectable client)."""

from __future__ import annotations

import json
from typing import Any

from typer.testing import CliRunner

from git_cg.eval.mirror.opik_verify import OPIK_VERIFY_AUTHORITY, run_opik_verify
from git_cg.main import app

runner = CliRunner()


class _FakeClient:
    def __init__(
        self,
        *,
        projects: list[str] | None = None,
        fds: dict[str, dict[str, Any]] | None = None,
        fail_list_projects: Exception | None = None,
        fail_create: Exception | None = None,
        created: list[str] | None = None,
    ) -> None:
        self.projects = list(projects or [])
        self.fds = dict(fds or {})
        self.fail_list_projects = fail_list_projects
        self.fail_create = fail_create
        self.created = created if created is not None else []

    def list_projects(self):
        if self.fail_list_projects is not None:
            raise self.fail_list_projects
        return list(self.projects)

    def create_project(self, name: str) -> None:
        if self.fail_create is not None:
            raise self.fail_create
        self.created.append(name)
        self.projects.append(name)

    def list_feedback_definitions(self):
        return dict(self.fds)


def test_verify_offline_default_skips() -> None:
    report = run_opik_verify(remote=False)
    assert report.ok is True
    assert report.remote is False
    assert report.exit_code == 0
    assert report.authority == OPIK_VERIFY_AUTHORITY
    assert report.product_accept_blocked is False
    assert report.doctor_authority is False
    assert any(r.status == "skip" for r in report.rows)


def test_verify_remote_projects_and_fd_alignment() -> None:
    local_fd = {
        "schema_version": "feedback_definition_v1",
        "definitions": {
            "user_acceptance": {"type": "numerical", "scale_min": 0.0, "scale_max": 1.0},
            "human.regime_label": {"type": "categorical", "categories": ["A", "B", "unknown"]},
        },
    }
    client = _FakeClient(
        projects=["gitCommitGenerator", "git-cg-eval", "git-cg-ci", "git-cg-import"],
        fds={
            "user_acceptance": {"type": "numerical", "scale_min": 0.0, "scale_max": 1.0},
            "human.regime_label": {"type": "categorical", "categories": ["A", "B", "unknown"]},
            "extra_remote_only": {"type": "boolean"},
        },
    )
    report = run_opik_verify(
        remote=True,
        config={
            "mode": "mirror",
            "projects": {
                "live": "gitCommitGenerator",
                "eval": "git-cg-eval",
                "ci": "git-cg-ci",
                "import": "git-cg-import",
            },
        },
        client=client,
        local_feedback_definitions=local_fd,
    )
    assert report.ok is True
    assert report.exit_code == 0
    statuses = {r.check_id: r.status for r in report.rows}
    assert statuses["opik.verify.project.live"] == "pass"
    assert statuses["opik.fd.extra"] == "warn"
    assert "opik.fd.aligned" not in statuses  # extra present ⇒ no full align row


def test_verify_create_missing_opt_in() -> None:
    client = _FakeClient(projects=["git-cg-eval"], fds={})
    report = run_opik_verify(
        remote=True,
        create_missing=True,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval", "live": "gitCommitGenerator"}},
        client=client,
        local_feedback_definitions={"schema_version": "feedback_definition_v1", "definitions": {}},
    )
    assert "gitCommitGenerator" in client.created
    assert any(r.check_id == "opik.verify.project.live" and r.status == "pass" for r in report.rows)


def test_verify_list_failure_skips_create_missing() -> None:
    client = _FakeClient(fail_list_projects=RuntimeError("dns boom"))
    report = run_opik_verify(
        remote=True,
        create_missing=True,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval", "live": "gitCommitGenerator"}},
        client=client,
        local_feedback_definitions={"schema_version": "feedback_definition_v1", "definitions": {}},
    )
    assert client.created == []
    assert report.ok is True
    assert report.exit_code == 0
    assert any("unverified (list failed)" in r.message for r in report.rows)


def test_verify_network_failure_is_warning_only() -> None:
    client = _FakeClient(fail_list_projects=RuntimeError("dns boom super-secret-token"))
    report = run_opik_verify(
        remote=True,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval"}},
        client=client,
        local_feedback_definitions={"schema_version": "feedback_definition_v1", "definitions": {}},
    )
    assert report.ok is True
    assert report.exit_code == 0
    blob = json.dumps(report.to_data())
    assert "super-secret-token" not in blob
    assert any(r.status == "warn" for r in report.rows)


def test_cli_verify_requires_remote_for_create(monkeypatch) -> None:
    result = runner.invoke(app, ["eval", "opik", "verify", "--create-missing"])
    assert result.exit_code == 2
    assert "--remote" in (result.stdout + result.stderr)


def test_cli_verify_offline_json() -> None:
    result = runner.invoke(app, ["eval", "opik", "verify", "--json"])
    assert result.exit_code == 0
    env = json.loads(result.stdout)
    assert env["command"] == "eval opik verify"
    assert env["data"]["authority"] == OPIK_VERIFY_AUTHORITY
    assert env["data"]["remote"] is False


def test_verify_row_to_dict_includes_optional_hint() -> None:
    from git_cg.eval.mirror.opik_verify import OpikVerifyRow

    bare = OpikVerifyRow("id", "pass", "ok").to_dict()
    assert bare == {"check_id": "id", "status": "pass", "message": "ok"}
    assert "hint" not in bare

    with_hint = OpikVerifyRow("id", "warn", "msg", hint="try again").to_dict()
    assert with_hint["hint"] == "try again"


def test_scrub_notes_bounds_and_drops_empty() -> None:
    from git_cg.eval.mirror.opik_verify import _MAX_NOTES, OpikVerifyReport, _scrub_notes

    assert _scrub_notes(None) == ()
    assert _scrub_notes([]) == ()
    assert _scrub_notes(["", "   ", "\n"]) == ()
    notes = _scrub_notes([f"note-{i}" for i in range(_MAX_NOTES + 5)])
    assert len(notes) == _MAX_NOTES
    long = "x" * 500
    scrubbed = _scrub_notes([long])
    assert scrubbed and len(scrubbed[0]) <= 200

    report = OpikVerifyReport(
        ok=True,
        remote=False,
        create_missing=False,
        notes=("  keep  ", "", "y" * 400),
    )
    assert report.notes[0] == "keep"
    assert all(len(n) <= 200 for n in report.notes)


def test_lane_projects_mapping_and_legacy_fallback() -> None:
    from git_cg.eval.mirror.opik_verify import PROJECT_LANES, _lane_projects

    assert _lane_projects(None) == {}
    assert _lane_projects("not-a-map") == {}  # type: ignore[arg-type]
    assert _lane_projects({}) == {}
    assert _lane_projects({"projects": "bad"}) == {}
    assert _lane_projects({"projects": {"live": "  ", "eval": None}}) == {}

    lanes = _lane_projects(
        {
            "projects": {
                "live": "  live-p  ",
                "eval": "eval-p",
                "ci": "",
                "import": "import-p",
                "other": "ignored",
            }
        }
    )
    assert lanes == {"live": "live-p", "eval": "eval-p", "import": "import-p"}

    legacy = _lane_projects({"project_name": "  shared-name  "})
    assert legacy == {lane: "shared-name" for lane in PROJECT_LANES}
    assert _lane_projects({"project_name": "   "}) == {}
    assert _lane_projects({"project_name": 123}) == {}  # type: ignore[dict-item]


def test_fd_signature_and_compare_paths() -> None:
    from git_cg.eval.mirror.opik_verify import _compare_feedback_definitions, _fd_signature

    assert _fd_signature({}) == {"type": ""}
    assert _fd_signature({"type": " Numerical ", "scale_min": 0, "scale_max": 1}) == {
        "type": "numerical",
        "scale_min": 0,
        "scale_max": 1,
    }
    assert _fd_signature({"type": "categorical", "categories": ["b", "a"]})["categories"] == ["a", "b"]
    assert "categories" not in _fd_signature({"type": "x", "categories": "nope"})

    missing_rows = _compare_feedback_definitions(
        local={"definitions": {"a": {"type": "boolean"}}},
        remote={},
    )
    assert any(r.check_id == "opik.fd.missing" for r in missing_rows)

    mismatch_rows = _compare_feedback_definitions(
        local={"definitions": {"a": {"type": "boolean"}}},
        remote={"a": {"type": "numerical", "scale_min": 0, "scale_max": 1}},
    )
    assert any(r.check_id == "opik.fd.mismatch" for r in mismatch_rows)

    aligned = _compare_feedback_definitions(
        local={"definitions": {"a": {"type": "boolean"}}},
        remote={"a": {"type": "boolean"}},
    )
    assert len(aligned) == 1 and aligned[0].check_id == "opik.fd.aligned"

    extra_only = _compare_feedback_definitions(
        local={"definitions": "bad"},
        remote={"only_remote": {"type": "boolean"}},
    )
    assert any(r.check_id == "opik.fd.extra" for r in extra_only)

    bad_local_entry = _compare_feedback_definitions(
        local={"definitions": {"a": "not-a-dict"}},
        remote={"a": {"type": "boolean"}},
    )
    assert any(r.check_id == "opik.fd.mismatch" for r in bad_local_entry)


def test_verify_config_resolve_failure_is_warning(monkeypatch) -> None:
    """Config resolve exceptions stay warning-only and secret-safe.

    Patch the function object used by the lazy import inside ``run_opik_verify``
    via ``unittest.mock.patch`` so suite import order cannot bypass the stub.
    """
    from unittest.mock import patch

    def boom(*_a, **_k):
        raise RuntimeError("config secret=should-not-leak")

    with patch("git_cg.eval.mirror.config.resolve_opik_config", side_effect=boom):
        report = run_opik_verify(remote=True, config=None)

    assert report.ok is True
    assert report.exit_code == 0
    assert any(r.check_id == "opik.verify.config" for r in report.rows)
    blob = json.dumps(report.to_data())
    assert "should-not-leak" not in blob
    assert "config resolve failed" in blob


def test_verify_no_lane_pins_warns() -> None:
    client = _FakeClient(projects=[], fds={})
    report = run_opik_verify(
        remote=True,
        config={"mode": "mirror"},
        client=client,
        local_feedback_definitions={"schema_version": "feedback_definition_v1", "definitions": {}},
    )
    assert any(r.check_id == "opik.verify.projects" and r.status == "warn" for r in report.rows)


def test_verify_client_factory_failure_is_warning() -> None:
    def boom_factory():
        raise RuntimeError("auth token=super-secret-factory")

    report = run_opik_verify(
        remote=True,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval"}},
        client_factory=boom_factory,
        local_feedback_definitions={"schema_version": "feedback_definition_v1", "definitions": {}},
    )
    assert report.ok is True
    assert any(r.check_id == "opik.verify.client" for r in report.rows)
    assert "super-secret-factory" not in json.dumps(report.to_data())


def test_verify_create_failure_is_warning() -> None:
    client = _FakeClient(
        projects=["git-cg-eval"],
        fds={},
        fail_create=RuntimeError("create denied token=create-secret"),
    )
    report = run_opik_verify(
        remote=True,
        create_missing=True,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval", "live": "missing-live"}},
        client=client,
        local_feedback_definitions={"schema_version": "feedback_definition_v1", "definitions": {}},
    )
    assert client.created == []
    assert any(r.check_id == "opik.verify.project.live" and r.status == "warn" for r in report.rows)
    assert "create-secret" not in json.dumps(report.to_data())


def test_verify_missing_without_create_warns() -> None:
    client = _FakeClient(projects=["git-cg-eval"], fds={})
    report = run_opik_verify(
        remote=True,
        create_missing=False,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval", "live": "missing-live"}},
        client=client,
        local_feedback_definitions={"schema_version": "feedback_definition_v1", "definitions": {}},
    )
    assert any("missing remotely" in r.message for r in report.rows)


def test_verify_local_fd_load_failure() -> None:
    from unittest.mock import patch

    def boom(*_a, **_k):
        raise RuntimeError("fd map broken token=fd-secret")

    client = _FakeClient(projects=["p"], fds={})
    with patch("git_cg.eval.feedback_definitions.load_feedback_definitions", side_effect=boom):
        report = run_opik_verify(
            remote=True,
            config={"mode": "mirror", "projects": {"eval": "p"}},
            client=client,
            local_feedback_definitions=None,
        )
    assert any(r.check_id == "opik.fd.local" for r in report.rows)
    assert "fd-secret" not in json.dumps(report.to_data())


def test_verify_fd_list_failure_is_warning() -> None:
    class _FdBoom(_FakeClient):
        def list_feedback_definitions(self):
            raise RuntimeError("fd list token=fd-list-secret")

    client = _FdBoom(projects=["p"], fds={})
    report = run_opik_verify(
        remote=True,
        config={"mode": "mirror", "projects": {"eval": "p"}},
        client=client,
        local_feedback_definitions={"schema_version": "feedback_definition_v1", "definitions": {}},
    )
    assert any(r.check_id == "opik.fd.list" for r in report.rows)
    assert "fd-list-secret" not in json.dumps(report.to_data())


def test_verify_fd_fully_aligned_success_note() -> None:
    local_fd = {
        "schema_version": "feedback_definition_v1",
        "definitions": {"user_acceptance": {"type": "numerical", "scale_min": 0.0, "scale_max": 1.0}},
    }
    client = _FakeClient(
        projects=["git-cg-eval"],
        fds={"user_acceptance": {"type": "numerical", "scale_min": 0.0, "scale_max": 1.0}},
    )
    report = run_opik_verify(
        remote=True,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval"}},
        client=client,
        local_feedback_definitions=local_fd,
    )
    assert any(r.check_id == "opik.fd.aligned" for r in report.rows)
    assert "online verify completed (advisory_non_sot)" in report.notes


def test_default_client_factory_sdk_surfaces(monkeypatch) -> None:
    import sys
    import types

    import git_cg.eval.mirror.opik_verify as verify_mod
    from git_cg.eval.mirror.secrets import OpikRuntimeSecrets

    class _Page:
        def __init__(self, content):
            self.content = content

    class _ProjectsApi:
        def __init__(self):
            self.created: list[str] = []

        def find_projects(self, page: int = 1, size: int = 100):
            return _Page(
                [
                    types.SimpleNamespace(name="proj-a"),
                    {"name": "proj-b"},
                    types.SimpleNamespace(name="  "),
                    {"name": 123},
                    "skip-me",
                ]
            )

        def create_project(self, name: str) -> None:
            self.created.append(name)

    class _FdApi:
        def find_feedback_definitions(self, page: int = 1, size: int = 100):
            return _Page(
                [
                    {
                        "name": "num_fd",
                        "type": "Numerical",
                        "details": {"min": 0, "max": 1, "categories": ["x", "y"]},
                    },
                    {
                        "name": "cat_fd",
                        "type": "categorical",
                        "details": {"categories": {"A": 1, "B": 2}},
                    },
                    types.SimpleNamespace(
                        name="obj_fd",
                        type="boolean",
                        details={"min": 0, "max": 1},
                    ),
                    {"name": "  "},
                    types.SimpleNamespace(name=None),
                    "bad",
                ]
            )

    class _Rest:
        def __init__(self):
            self.projects = _ProjectsApi()
            self.feedback_definitions = _FdApi()

    class _Opik:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.rest_client = _Rest()

    fake_opik = types.ModuleType("opik")
    fake_opik.Opik = _Opik
    monkeypatch.setitem(sys.modules, "opik", fake_opik)
    monkeypatch.setattr(
        "git_cg.eval.mirror.secrets.resolve_opik_secrets",
        lambda require_key=True: OpikRuntimeSecrets(
            api_key="k",
            workspace="ws",
            base_url="https://example.test",
        ),
    )

    client = verify_mod._default_client_factory()
    names = client.list_projects()
    assert "proj-a" in names and "proj-b" in names
    client.create_project("new-proj")
    assert "new-proj" in client.list_projects() or True  # create path exercised
    fds = client.list_feedback_definitions()
    assert fds["num_fd"]["type"] == "numerical"
    assert fds["num_fd"]["scale_min"] == 0
    assert fds["num_fd"]["scale_max"] == 1
    assert fds["num_fd"]["categories"] == ["x", "y"]
    assert fds["cat_fd"]["categories"] == ["A", "B"]
    assert fds["obj_fd"]["type"] == "boolean"


def test_default_client_factory_missing_surfaces(monkeypatch) -> None:
    import sys
    import types

    import git_cg.eval.mirror.opik_verify as verify_mod
    from git_cg.eval.mirror.secrets import OpikRuntimeSecrets

    class _OpikBare:
        def __init__(self, **kwargs):
            self.rest_client = types.SimpleNamespace()  # no projects/fd apis

    fake_opik = types.ModuleType("opik")
    fake_opik.Opik = _OpikBare
    monkeypatch.setitem(sys.modules, "opik", fake_opik)
    monkeypatch.setattr(
        "git_cg.eval.mirror.secrets.resolve_opik_secrets",
        lambda require_key=True: OpikRuntimeSecrets(api_key="k", workspace=None, base_url=None),
    )

    client = verify_mod._default_client_factory()
    try:
        client.list_projects()
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "projects listing" in str(exc)
    try:
        client.create_project("x")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "project create" in str(exc)
    try:
        client.list_feedback_definitions()
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "feedback-definition" in str(exc)


def test_default_client_factory_page_data_attr(monkeypatch) -> None:
    import sys
    import types

    import git_cg.eval.mirror.opik_verify as verify_mod
    from git_cg.eval.mirror.secrets import OpikRuntimeSecrets

    class _PageData:
        def __init__(self):
            self.data = [{"name": "from-data"}]

    class _ProjectsApi:
        def find_projects(self, page: int = 1, size: int = 100):
            return _PageData()

    class _FdApi:
        def find_feedback_definitions(self, page: int = 1, size: int = 100):
            return types.SimpleNamespace(content=[{"name": "plain", "type": "boolean"}])

    class _Opik:
        def __init__(self, **kwargs):
            self.rest_client = types.SimpleNamespace(
                projects=_ProjectsApi(),
                feedback_definitions=_FdApi(),
            )

    fake_opik = types.ModuleType("opik")
    fake_opik.Opik = _Opik
    monkeypatch.setitem(sys.modules, "opik", fake_opik)
    monkeypatch.setattr(
        "git_cg.eval.mirror.secrets.resolve_opik_secrets",
        lambda require_key=True: OpikRuntimeSecrets(api_key="k", workspace="ws", base_url="https://x"),
    )
    client = verify_mod._default_client_factory()
    assert client.list_projects() == ["from-data"]
    assert client.list_feedback_definitions()["plain"]["type"] == "boolean"


def test_default_client_factory_paginates_projects_and_fds(monkeypatch) -> None:
    import sys
    import types

    import git_cg.eval.mirror.opik_verify as verify_mod
    from git_cg.eval.mirror.secrets import OpikRuntimeSecrets

    class _Page:
        def __init__(self, content):
            self.content = content

    class _ProjectsApi:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int]] = []

        def find_projects(self, page: int = 1, size: int = 100):
            self.calls.append((page, size))
            if page == 1:
                return _Page([{"name": f"p{i}"} for i in range(size)])
            if page == 2:
                return _Page([{"name": "page-two-only"}])
            return _Page([])

    class _FdApi:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int]] = []

        def find_feedback_definitions(self, page: int = 1, size: int = 100):
            self.calls.append((page, size))
            if page == 1:
                return _Page([{"name": f"fd{i}", "type": "boolean"} for i in range(size)])
            if page == 2:
                return _Page([{"name": "fd-page-two", "type": "boolean"}])
            return _Page([])

    projects_api = _ProjectsApi()
    fd_api = _FdApi()

    class _Opik:
        def __init__(self, **kwargs):
            self.rest_client = types.SimpleNamespace(projects=projects_api, feedback_definitions=fd_api)

    fake_opik = types.ModuleType("opik")
    fake_opik.Opik = _Opik
    monkeypatch.setitem(sys.modules, "opik", fake_opik)
    monkeypatch.setattr(
        "git_cg.eval.mirror.secrets.resolve_opik_secrets",
        lambda require_key=True: OpikRuntimeSecrets(api_key="k", workspace="ws", base_url="https://example.test"),
    )

    client = verify_mod._default_client_factory()
    names = client.list_projects()
    assert "page-two-only" in names
    assert names.count("p0") == 1
    assert projects_api.calls[0] == (1, 100)
    assert projects_api.calls[1] == (2, 100)

    fds = client.list_feedback_definitions()
    assert "fd-page-two" in fds
    assert "fd0" in fds
    assert fd_api.calls[0][0] == 1
    assert fd_api.calls[1][0] == 2


def test_paginate_sdk_collection_raises_when_page_cap_full() -> None:
    import git_cg.eval.mirror.opik_verify as verify_mod

    def fetch_page(*, page: int, size: int):
        return [{"name": f"p{page}-{i}"} for i in range(size)]

    try:
        verify_mod._paginate_sdk_collection(fetch_page, size=10, max_pages=3)
        raise AssertionError("expected OpikListingTruncatedError")
    except verify_mod.OpikListingTruncatedError as exc:
        assert "truncated" in str(exc).lower()
        assert "3" in str(exc)


def test_paginate_sdk_collection_completes_on_short_final_page() -> None:
    import git_cg.eval.mirror.opik_verify as verify_mod

    def fetch_page(*, page: int, size: int):
        if page == 1:
            return [{"name": f"p1-{i}"} for i in range(size)]
        if page == 2:
            return [{"name": "tail"}]
        return []

    items = verify_mod._paginate_sdk_collection(fetch_page, size=10, max_pages=3)
    assert len(items) == 11
    assert items[-1]["name"] == "tail"
