"""Offline bind-path guarantee for acceptpath happy path.

New bind, index write-through, and cache-hit reuse must succeed with
socket connect primitives blocked and without importing Opik, httpx,
or cloud SDKs.

Refs: #257.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

FINAL = (
    "✨ feat(eval): bind offline guarantee\n\n"
    "Refs: #257\n"
    "SemVer-Impact: PATCH\n"
    "Change-Types: test\n"
    "Changelog-Groups: Tests\n"
)
TOKEN = "ae_offline"


def test_bind_happy_path_is_offline_no_network_no_opik_import(tmp_path: Path) -> None:
    probe = textwrap.dedent(
        f"""
        from __future__ import annotations

        import json
        import os
        import socket
        import sys
        from pathlib import Path

        repo = Path({str(tmp_path)!r})
        final = {FINAL!r}
        token = {TOKEN!r}
        attempts: list[str] = []
        forbidden_roots = {{
            "anthropic",
            "azure",
            "boto3",
            "botocore",
            "google",
            "httpcore",
            "httpx",
            "openai",
            "opik",
            "opik_client",
        }}

        def deny(kind: str, *_args, **_kwargs):
            attempts.append(kind)
            raise OSError(f"network blocked ({{kind}})")

        socket.socket.connect = lambda self, *a, **k: deny("connect", *a, **k)
        socket.socket.connect_ex = lambda self, *a, **k: deny("connect_ex", *a, **k)
        socket.create_connection = lambda *a, **k: deny("create_connection", *a, **k)
        socket.getaddrinfo = lambda *a, **k: deny("getaddrinfo", *a, **k)

        os.environ["GIT_CG_EVAL_CAPTURE"] = "on"
        os.environ.pop("GIT_CG_EVAL_PROFILE", None)

        from git_cg.eval.binding import BindInput, bind_final_accept

        def leaked_modules() -> list[str]:
            return sorted(
                name
                for name in sys.modules
                if name.split(".", 1)[0] in forbidden_roots
            )

        leaked = leaked_modules()
        assert not leaked, leaked
        assert not attempts, attempts

        inp = BindInput(final_message=final, accept_event_token=token)
        first = bind_final_accept(inp, repo_root=repo, write=True)
        assert first.bound is True, (first.unbound_reason, first.errors)
        assert first.errors == ()
        assert first.bundle is not None
        session = first.bundle["session_thread_id"]
        assert isinstance(session, str) and session.startswith("sess_")
        assert first.paths_written == (f".eval/bundles/acceptpath/{{session}}.json",)

        acceptpath = repo / ".eval" / "bundles" / "acceptpath"
        index_path = acceptpath / "index.json"
        assert index_path.is_file()
        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert session in index["entries"].values()

        second = bind_final_accept(inp, repo_root=repo, write=True)
        assert second.bound is True, (second.unbound_reason, second.errors)
        assert second.errors == ()
        assert second.bundle is not None
        assert second.bundle["session_thread_id"] == session

        bundles = [path for path in acceptpath.glob("*.json") if path.name != "index.json"]
        assert len(bundles) == 1
        assert bundles[0].name == f"{{session}}.json"

        leaked = leaked_modules()
        assert not leaked, leaked
        assert attempts == []
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, (
        "bind happy path must stay offline with no Opik/httpx/cloud imports; "
        f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
    )
