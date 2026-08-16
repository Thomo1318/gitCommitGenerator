import contextlib
import enum
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, NoReturn

import click
import sentry_sdk
from dotenv import load_dotenv

# Load .env fallback immediately
load_dotenv()

if os.environ.get("GIT_CG_DISABLE_SENTRY", "0") != "1":
    from git_cg.sentry_config import init_sentry

    init_sentry()


# Set opik logging level before importing it
os.environ["OPIK_CONSOLE_LOGGING_LEVEL"] = "INFO"
# Increase logging level to reduce console spam from Opik
os.environ["OPIK_CONSOLE_LOGGING_LEVEL"] = os.environ.get("OPIK_CONSOLE_LOGGING_LEVEL", "error")

# Pre-populate 1Password secrets so they are available in os.environ for Opik and OpenAI
try:
    from git_cg.secrets import _populate_cache

    _populate_cache()
except Exception as e:
    import sys

    print(f"[Debug] Failed to load 1Password secrets: {e}", file=sys.stderr)

import httpx  # noqa: E402
import instructor  # noqa: E402
import openai  # noqa: E402
import opik  # noqa: E402
import typer  # noqa: E402
from openai import OpenAI  # noqa: E402
from opik import opik_context  # noqa: E402
from opik.integrations.openai import track_openai  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402

from git_cg.intent import extract_diff_signals, rank_commit_intents  # noqa: E402
from git_cg.interaction import (  # noqa: E402
    can_open_tty,
    emit_terminal_bell,
    format_gold_findings_status,
    format_issue_reference_status,
    format_ranking_confidence_status,
    format_regeneration_guidance_status,
    prompt_issue_number,
    prompt_issue_reference_type,
    prompt_regeneration_guidance,
    prompt_with_gum,
)
from git_cg.models import CommitPlan, IssueReference, IssueReferenceKind, ModelCommitPlan  # noqa: E402
from git_cg.retries import llm_retry  # noqa: E402
from git_cg.secrets import resolve_secret  # noqa: E402
from git_cg.sop import load_sop  # noqa: E402
from git_cg.telemetry import compute_prompt_hash  # noqa: E402

app = typer.Typer(
    add_completion=False,
    help="GitOps AI Commit Generator and Release Automation",
    invoke_without_command=True,
    no_args_is_help=False,
)
console = Console()

# Thin corpus-helper sub-app (Issue #231, D11). Delegation-only: no binder, no
# accept-path .eval writes, no network. Distinct from the `evals` benchmark cmd.
from git_cg.eval.cli import eval_app  # noqa: E402

app.add_typer(eval_app, name="eval")

# Only generate for an interactive (empty) or template commit. Everything else
# (-m/-F => "message", merge, squash, --amend/-c/-C => "commit") already has a
# message we must NOT overwrite — critical for safe global-hook operation.
GENERATING_SOURCES: set[str | None] = {None, "", "template"}

# Truthy tokens for GIT_CG_SKIP_PREPARE (F80 / P-S12-9 message-only rebuilds).
# Keep aligned with semantic/rank-arbitrate env parsers: 1/true/yes/on.
_SKIP_PREPARE_TRUTHY: frozenset[str] = frozenset({"1", "true", "yes", "on"})


def _is_skip_prepare_enabled() -> bool:
    """Return True when prepare-commit-msg generation must no-op.

    Used for message-only rebuilds (amend --no-edit / controlled rewrites) so the
    prepare-commit-msg hook cannot recursively re-enter git-cg. Ordinary hook
    generation is unchanged unless the operator sets GIT_CG_SKIP_PREPARE.
    """
    raw = os.environ.get("GIT_CG_SKIP_PREPARE", "").strip().lower()
    return raw in _SKIP_PREPARE_TRUTHY


class ReviewStateMutationResult(enum.StrEnum):
    """Possible outcomes when mutating issue-reference state during review."""

    ADDED = "added"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


@dataclass
class ReviewState:
    """A deterministic container for review-related state, holding the CommitPlan and associated review metadata."""

    commit_plan: CommitPlan
    issue_references: list[IssueReference] = field(default_factory=list)
    regeneration_guidance: str | None = None
    active_directives: dict[str, str] = field(default_factory=dict)
    residual_guidance: str | None = None
    gold_findings: list = field(default_factory=list)
    # Issue #195 nice-to-have: display-only ranking confidence on post-gold review.
    ranking_confidence_level: str | None = None
    ranking_confidence_margin: float | None = None
    ranking_confidence_reasons: list[str] = field(default_factory=list)
    ranking_confidence_top_intent_id: str | None = None
    ranking_confidence_runner_up_intent_id: str | None = None

    def render(self) -> str:
        """
        Render the current review state as a commit message string.

        Returns:
            str: The rendered commit plan including any issue references stored in this review state.
        """
        return self.commit_plan.render(issue_references=self.issue_references)

    def get_issue_reference_by_issue_number(self, issue_number: int) -> IssueReference | None:
        """Return the existing issue reference for a given issue number, if present."""
        return next((ref for ref in self.issue_references if ref.issue_number == issue_number), None)

    def add_issue_reference(self, issue_reference: IssueReference) -> ReviewStateMutationResult:
        """
        Store an issue reference in the review state.

        Parameters:
            issue_reference (IssueReference): The issue reference to store.

        Returns:
            ReviewStateMutationResult: `ADDED` if the reference was stored, `DUPLICATE` if an identical reference already exists, `CONFLICT` if a reference for the same issue number exists but has a different verb.
        """
        existing_issue_reference = self.get_issue_reference_by_issue_number(issue_reference.issue_number)
        if existing_issue_reference is not None:
            if existing_issue_reference == issue_reference:
                return ReviewStateMutationResult.DUPLICATE

            return ReviewStateMutationResult.CONFLICT

        self.issue_references.append(issue_reference)
        return ReviewStateMutationResult.ADDED

    def _extract_directives(self, text: str) -> tuple[dict[str, str], str | None]:
        """
        Extract high-confidence deterministic directives from a guidance string.

        This parses terse, high-certainty overrides embedded in freeform guidance and returns any recognised directives and the remaining (residual) guidance text. Currently recognises:
        - `preferred_type`: conventional commit type (e.g. `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`, `init`, `release`)
        - `preferred_scope`: a single token scope (alphanumeric, underscore or hyphen)

        Parameters:
            text (str): Freeform regeneration guidance provided by the user.

        Returns:
            tuple[dict[str, str], str | None]: A tuple of (directives, residual_guidance). `directives` maps directive names to their extracted values. `residual_guidance` is the remaining guidance with recognised directives removed, or `None` if empty.
        """
        directives = {}
        residual = text

        # Extremely basic heuristics for high-confidence overrides
        # E.g., "this is a feat", "make it a fix", "docs only"

        type_match = re.search(
            r"\b(?:this is a|make it a|use type|type is)\s+(feat|feature|fix|docs|style|refactor|perf|test|build|ci|chore|revert|init|release)\b",
            residual,
            re.IGNORECASE,
        )
        if type_match:
            matched_type = type_match.group(1).lower()
            # Normalize synonyms to canonical Conventional Commit types
            if matched_type == "feature":
                matched_type = "feat"
            directives["preferred_type"] = matched_type
            # Remove the match from residual to leave only what wasn't deterministically parsed
            residual = residual[: type_match.start()] + residual[type_match.end() :]

        scope_match = re.search(r"\b(?:use scope)\s+([a-zA-Z0-9_-]+)\b", residual, re.IGNORECASE)
        if scope_match:
            directives["preferred_scope"] = scope_match.group(1).lower()
            residual = residual[: scope_match.start()] + residual[scope_match.end() :]

        residual = " ".join(residual.split()).strip()
        return directives, (residual if residual else None)

    def set_regeneration_guidance(self, guidance: str) -> bool:
        """
        Set regeneration guidance for the review state and parse any embedded directives.

        Normalises the provided guidance, ignores empty input, and if the stored guidance changes updates the review state's regeneration guidance, active directives and residual guidance.

        Parameters:
            guidance (str): User-provided text guiding how subsequent regenerations should frame intent and scope.

        Returns:
            bool: `True` if the stored guidance was changed, `False` otherwise.
        """
        normalized_guidance = " ".join(guidance.split()).strip()
        if not normalized_guidance:
            return False
        if self.regeneration_guidance == normalized_guidance:
            return False
        self.regeneration_guidance = normalized_guidance
        self.active_directives, self.residual_guidance = self._extract_directives(normalized_guidance)
        return True

    def clear_regeneration_guidance(self) -> bool:
        """
        Clear any stored regeneration guidance, parsed directives and residual guidance.

        Returns:
            `True` if guidance was present and was cleared, `False` if no guidance was set.
        """
        if self.regeneration_guidance is None:
            return False
        self.regeneration_guidance = None
        self.active_directives = {}
        self.residual_guidance = None
        return True


@dataclass
class EngineConfig:
    prefix: str
    default_base_url: str


ENGINE_REGISTRY: dict[str, EngineConfig] = {
    "omlx": EngineConfig(prefix="OMLX", default_base_url="http://127.0.0.1:8000/v1"),
    "mtplx": EngineConfig(prefix="MTPLX", default_base_url="http://127.0.0.1:8000/v1"),
    "lmlx": EngineConfig(prefix="LMLX", default_base_url="http://127.0.0.1:8010/v1"),
    "openai": EngineConfig(prefix="OPENAI", default_base_url="https://api.openai.com/v1"),
}

LAST_OPIK_TRACE_ID: str | None = None


def _abort(message: str, *, strict: bool, code: int = 1, report: bool = True) -> NoReturn:
    """
    Print an error message and terminate execution.

    Parameters:
        message (str): The message to display before exiting.
        strict (bool): Whether to exit with the supplied code.
        code (int): The exit code to use when strict mode is enabled.
    """
    import sys

    console.print(message)
    if report:
        if sys.exc_info()[0] is not None:
            sentry_sdk.capture_exception()
        else:
            sentry_sdk.capture_message(message, level="error")
        sentry_sdk.flush(timeout=2.0)
    opik.flush_tracker()
    raise typer.Exit(code=code if strict else 0)


def _apply_issue195_sentry_tags(
    *,
    ranking_confidence_level: str | None = None,
    ranking_choice_path: str | None = None,
    gold_mode: str | None = None,
    gold_self_correction_outcome: str | None = None,
) -> None:
    """Attach Issue #195 / gold-parity Sentry tags on error and abort paths only.

    Tags are closed enums / short codes — never ranked matrices, diffs, or guidance.
    """
    if ranking_confidence_level:
        sentry_sdk.set_tag("ranking_confidence_level", str(ranking_confidence_level))
    if ranking_choice_path:
        sentry_sdk.set_tag("ranking_choice_path", str(ranking_choice_path))
    if gold_mode is not None and gold_mode != "":
        sentry_sdk.set_tag("gold_mode", str(gold_mode))
    if gold_self_correction_outcome:
        # Issue #191: closed outcome on gold-path strict aborts only.
        sentry_sdk.set_tag("gold_self_correction_outcome", str(gold_self_correction_outcome))


def resolve_model_name(
    client: Any,
    *,
    preferred: str,
    verbose: bool = False,
) -> str:
    """
    Resolve a concrete model id from env preference and server inventory.

    Preference order:
    1. Preferred id when inventory is unavailable (keep user config).
    2. Preferred id when present in inventory.
    3. First available inventory id when preferred is empty or missing.
    4. Preferred string if inventory is empty but preferred was set.
    5. ``"default"`` as last resort.
    """
    preferred = (preferred or "").strip()

    available: list[str] = []
    inventory_ok = False
    try:
        # Instructor wrappers may expose the raw OpenAI client as ``.client``.
        listing_client = getattr(client, "client", client)
        models_api = getattr(listing_client, "models", None)
        if models_api is None:
            models_api = getattr(client, "models", None)
        if models_api is None:
            raise AttributeError("client has no models API")

        listed = models_api.list()
        data = getattr(listed, "data", None) or []
        available = [m.id for m in data if getattr(m, "id", None)]
        inventory_ok = True
    except (openai.APIError, httpx.HTTPError, OSError, AttributeError, TypeError, ValueError) as exc:
        if verbose:
            console.log(
                f"[yellow]Model inventory unavailable ({type(exc).__name__}: {exc}); using preferred/default.[/yellow]"
            )
        return preferred or "default"
    except Exception as exc:  # pragma: no cover - unexpected SDK shapes
        if verbose:
            console.log(
                f"[yellow]Unexpected model listing error ({type(exc).__name__}: {exc}); "
                f"using preferred/default.[/yellow]"
            )
        return preferred or "default"

    if preferred and (not inventory_ok or preferred in available):
        return preferred

    if available:
        chosen = available[0]
        if preferred and preferred != chosen:
            console.print(f"[yellow]Configured model {preferred!r} is not loaded; falling back to {chosen!r}.[/yellow]")
        elif verbose and not preferred:
            console.log(f"No model configured; using first available model {chosen!r}.")
        return chosen

    if preferred:
        return preferred

    return "default"


def get_ai_client(engine: str) -> instructor.Instructor:
    """
    Create an Instructor AI client for the given engine; if the engine's base URL points to a local server that is not responsive, attempt to start a compatible local server and wait for it to become ready.

    Parameters:
        engine (str): Engine identifier (case-insensitive) as listed in ENGINE_REGISTRY (e.g. "omlx", "mtplx", "openai").

    Returns:
        instructor.Instructor: A configured Instructor client ready for use.

    Raises:
        ValueError: If the provided engine is not present in ENGINE_REGISTRY.
    """
    engine_lower = engine.lower()

    config = ENGINE_REGISTRY.get(engine_lower)
    if not config:
        raise ValueError(f"Unsupported engine: {engine}. Supported engines: {', '.join(ENGINE_REGISTRY.keys())}")

    api_key = resolve_secret(f"{config.prefix}_API_KEY", "not-needed")
    base_url = resolve_secret(f"{config.prefix}_BASE_URL", config.default_base_url)

    if "localhost" in base_url or "127.0.0.1" in base_url:
        import time
        import urllib.error
        import urllib.parse
        import urllib.request

        models_url = f"{base_url.rstrip('/')}/models"
        server_ready = False

        try:
            req = urllib.request.Request(models_url, method="GET")
            with urllib.request.urlopen(req, timeout=1) as response:
                if response.status == 200:
                    server_ready = True
        except (
            urllib.error.URLError,
            TimeoutError,
        ):
            pass

        if not server_ready:
            console.print(
                f"[yellow]🚀 Local AI server for {engine} is not running. Starting it in the background...[/yellow]"
            )
            parsed = urllib.parse.urlparse(base_url)
            port = parsed.port or 8000

            import shlex

            mtplx_path = shutil.which("mtplx") or "mtplx"
            omlxd_path = shutil.which("omlxd") or "omlxd"
            lmlx_path = shutil.which("lightning-mlx") or "lightning-mlx"

            if engine_lower == "mtplx":
                cmd_args = shlex.split(f"{mtplx_path} quickstart --profile sustained --port {port}")
            elif engine_lower == "lmlx":
                model_arg = (
                    os.environ.get("LMLX_MODEL")
                    or os.environ.get("OMLX_MODEL")
                    or "Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed"
                )
                cmd_args = shlex.split(f"{lmlx_path} serve {model_arg} --port {port}")
            else:
                cmd_args = shlex.split(f"{omlxd_path} --port {port}")

            engine_safe = os.path.basename(engine_lower)
            log_path = f"/tmp/{engine_safe}_server.log"
            with open(log_path, "a", encoding="utf-8") as log_file:
                process = subprocess.Popen(cmd_args, stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)

            console.print(f"[dim]Background logs: {log_path}[/dim]")
            console.print("[yellow]Waiting for AI server to become ready (tailing logs)...[/yellow]")

            with open(log_path, encoding="utf-8") as f:
                f.seek(0, 2)
                for _ in range(60):
                    if process.poll() is not None:
                        _abort(
                            f"\n[bold red]❌ AI server process exited unexpectedly with code {process.returncode}. Check {log_path} for details.[/bold red]",
                            strict=True,
                        )

                    line = f.readline()
                    while line:
                        console.print(f"[dim]  {line.strip()}[/dim]")
                        line = f.readline()

                    try:
                        req = urllib.request.Request(models_url, method="GET")
                        with urllib.request.urlopen(req, timeout=1) as response:
                            if response.status == 200:
                                server_ready = True
                                console.print("\n[green]✅ AI server successfully started and is ready![/green]")
                                break
                    except (
                        urllib.error.URLError,
                        TimeoutError,
                        ConnectionError,
                        OSError,
                    ):
                        pass
                    except Exception as e:
                        console.print(f"[bold red]❌ Unexpected error checking AI server status: {e}[/bold red]")
                        raise

                    time.sleep(1)

            if not server_ready:
                _abort(
                    f"\n[bold red]❌ Timed out waiting for local AI server. Check {log_path} for details.[/bold red]",
                    strict=True,
                )

    openai_client = track_openai(OpenAI(base_url=base_url, api_key=api_key))
    if engine_lower in ["mtplx", "omlx", "lmlx"]:
        # Monkeypatch create to strip <think> blocks before instructor parses it
        original_create = openai_client.chat.completions.create

        def patched_create(*args, **kwargs):
            response = original_create(*args, **kwargs)
            if hasattr(response, "choices") and response.choices:
                content = response.choices[0].message.content
                if content and "</think>" in content:
                    # Keep everything after the </think> tag
                    response.choices[0].message.content = content.split("</think>")[-1].strip()
            return response

        openai_client.chat.completions.create = patched_create

        client = instructor.from_openai(openai_client, mode=instructor.Mode.JSON)
    else:
        client = instructor.from_openai(openai_client)
    return client


def build_generation_messages(
    system_prompt: str,
    diff_output: str,
) -> list[Any]:
    """
    Build the chat messages for commit message generation from a git diff.

    Returns:
        messages (list[Any]): The system prompt followed by a user message containing the diff in a fenced `diff` block.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Here is the diff:\n\n```diff\n{diff_output}\n```"},
    ]
    return messages


@opik.track(
    project_name="gitCommitGenerator",
    ignore_arguments=["client", "diff_output", "system_prompt", "residual_guidance"],
)
@llm_retry
def generate_commit_message(
    client: instructor.Instructor,
    diff_output: str,
    model_name: str,
    system_prompt: str,
    active_directives: dict[str, str] | None = None,
    residual_guidance: str | None = None,
    **kwargs,
) -> CommitPlan:
    """
    Generate a commit plan from the supplied diff and system prompt.

    Parameters:
        active_directives (dict[str, str] | None): Directive values that override the generated commit type or scope.

    Returns:
        CommitPlan: The generated commit plan with applicable directive overrides.
    """
    opik_args = kwargs.get("opik_args") or {}
    tags = opik_args.get("trace", {}).get("tags", [])
    if tags:
        opik_context.update_current_span(tags=tags)

    model_result: ModelCommitPlan = client.chat.completions.create(
        model=model_name,
        response_model=ModelCommitPlan,
        messages=build_generation_messages(system_prompt, diff_output),
        max_retries=2,
        parallel_tool_calls=False,
    )
    commit_result = model_result.to_commit_plan()
    if active_directives:
        from git_cg.models import CommitType

        if "preferred_type" in active_directives:
            commit_result.primary_intent.cc_type = CommitType(active_directives["preferred_type"])
        if "preferred_scope" in active_directives:
            # I-12 / #204 §J: always route through normalize_scope (never assign raw token).
            from git_cg.scope_canon import resolve_scope_normalisation

            _canon, _from = resolve_scope_normalisation(active_directives["preferred_scope"])
            commit_result.primary_intent.scope = _canon
            # Stash closed alias key for D26 write (RF-1); never a path.
            commit_result._scope_normalised_from = _from  # ephemeral D26 breadcrumb
    return commit_result


def detect_primary_language(diff_output: str) -> str | None:
    """
    Detect the primary programming language represented in a diff.

    Parameters:
        diff_output (str): Unified diff text to inspect.

    Returns:
        str | None: The mapped language name for the most common file extension, or the upper-case extension when no mapping is defined. `None` if no file extensions are found.
    """
    pattern = re.compile(r"^diff --git a/.*\.([a-zA-Z0-9]+) b/.*$", re.MULTILINE)
    extensions = pattern.findall(diff_output)
    if not extensions:
        return None

    ignored_exts = {"md", "txt", "json", "yaml", "yml", "csv", "toml", "ini", "lock", "gitignore", "env", "pkl"}
    code_extensions = [ext.lower() for ext in extensions if ext.lower() not in ignored_exts]

    # Fallback to all extensions if only non-code files were modified
    target_extensions = code_extensions if code_extensions else [ext.lower() for ext in extensions]

    # Common mappings
    ext_map = {
        "py": "Python",
        "rs": "Rust",
        "ts": "TypeScript",
        "js": "JavaScript",
        "go": "Go",
        "c": "C",
        "cpp": "C++",
        "java": "Java",
        "rb": "Ruby",
        "php": "PHP",
        "cs": "C#",
        "swift": "Swift",
        "kt": "Kotlin",
        "sh": "Shell",
        "html": "HTML",
        "css": "CSS",
        "tf": "Terraform",
    }

    counter = Counter(target_extensions)
    most_common_ext = counter.most_common(1)[0][0]
    return ext_map.get(most_common_ext, most_common_ext.upper())


@opik.track(project_name="gitCommitGenerator")
def build_system_prompt(
    diff_output: str,
    verbose: bool = False,
    active_directives: dict[str, str] | None = None,
    residual_guidance: str | None = None,
    previous_plan: CommitPlan | None = None,
    ranked_candidates: list | None = None,
    contract=None,
    gold_guidance: str | None = None,
    scoped_history_guidance: str | None = None,
    staged_paths: list[str] | None = None,
    concern_tags: frozenset[str] | set[str] | None = None,
    claim_tags: list[str] | tuple[str, ...] | None = None,
    low_confidence_guidance: str | None = None,
) -> str:
    """
    Compose the system prompt for generating a structured Conventional Commit plan.

    Parameters:
        diff_output (str): Git diff content used for language detection and intent ranking.
        verbose (bool): Whether to enable diagnostic output while building the prompt.
        active_directives (dict[str, str] | None): Locked regeneration overrides, such as a preferred type or scope.
        residual_guidance (str | None): Free-text guidance to apply during regeneration.
        previous_plan (CommitPlan | None): Previously generated plan to include during regeneration.
        ranked_candidates (list | None): Precomputed intent candidates to include instead of ranking the diff.
        contract: Semantic contract whose values must be preserved in the generated plan.
        gold_guidance (str | None): Gold-linter wording/secondary-coverage feedback. Routed
            through a dedicated directive-free channel (Issue #182); never emits OVERRIDE
            or ranking-precedence language and never mutates the contract.
        scoped_history_guidance (str | None): Phase 9 split/rename rationale feedback. Routed
            through Channel 4 (Issue #163); directive-free; never sets preferred_type or
            authority fields.
        staged_paths (list[str] | None): Staged paths for included-change stubs and
            Slice 6 high-risk body checklist injection (D6/D20).
        low_confidence_guidance (str | None): Issue #204 Slice 5 body-skeleton guidance.
            Directive-free wording structure only; never sets preferred_type or mutates
            ranked intent authority.

    Returns:
        str: The complete system prompt, including SOP context, intent candidates, language and localisation requirements, and any regeneration guidance.
    """
    sop_data = load_sop()
    if not sop_data and verbose:
        console.log("[yellow]SOP could not be located; generating without matrix enforcement.[/yellow]")

    gitops_matrix_str = ""
    context_parts = []
    specs = sop_data.get("specifications_and_standards", {})
    workflow = sop_data.get("agentic_commit_workflow", {})
    gitops_matrix = sop_data.get("gitmoji_reference_matrix", [])
    commit_language = sop_data.get("commit_language", "en-US")
    if specs:
        context_parts.append("Specifications and Standards:\n" + json.dumps(specs, indent=2))
    if workflow:
        context_parts.append("Agentic Commit Workflow:\n" + json.dumps(workflow, indent=2))

    if gitops_matrix:
        if ranked_candidates is None:
            if verbose:
                console.log("Analyzing diff signals and ranking intents...")
            signals = extract_diff_signals(diff_output)
            ranked_candidates = rank_commit_intents(signals, gitops_matrix)
        elif verbose:
            console.log("Using shared ranked intent candidates...")

        primary_candidates = ranked_candidates[:3]
        secondary_candidates = []
        seen_groups = {cand.intent_group for cand in primary_candidates}

        for cand in ranked_candidates[3:]:
            if len(secondary_candidates) >= 3:
                break
            if cand.intent_group not in seen_groups and cand.score > 0:
                secondary_candidates.append(cand)
                seen_groups.add(cand.intent_group)

        if len(secondary_candidates) < 3:
            for cand in ranked_candidates[3:]:
                if len(secondary_candidates) >= 3:
                    break
                if cand not in secondary_candidates and cand.score > 0:
                    secondary_candidates.append(cand)

        if active_directives or residual_guidance:
            candidates_str = (
                "INITIAL DETERMINISTIC ANALYSIS:\n"
                "The following intents were initially ranked as the most likely based purely on the diff.\n"
                "These are provided for context, but you must prioritize the explicit Regeneration Guidance below.\n\n"
                "PRIMARY CANDIDATES (Initial Top Matches):\n"
            )
        else:
            candidates_str = (
                "Based on deterministic analysis of the git diff, here is your Smart Menu of commit intents.\n"
                "Select the primary intent from the Primary Candidates. "
                "If the diff contains distinct sub-changes, select secondary intents from the Secondary Candidates.\n\n"
                "PRIMARY CANDIDATES (Top Matches):\n"
            )

        for i, cand in enumerate(primary_candidates, 1):
            candidates_str += f"{i}. {cand.emoji} {cand.cc_type} ({cand.intent_id})\n"
            candidates_str += f"   Description: {cand.description}\n"
            if cand.selection_rule:
                candidates_str += f"   Rule: {cand.selection_rule}\n"
            if cand.evidence:
                candidates_str += f"   Evidence: {', '.join(cand.evidence)}\n"

        if secondary_candidates:
            candidates_str += "\nSECONDARY CANDIDATES (For distinct sub-changes):\n"
            for _i, cand in enumerate(secondary_candidates, 1):
                candidates_str += f"- {cand.emoji} {cand.cc_type} ({cand.intent_id}): {cand.description}\n"

        vocab = [f"{c['emoji']} {c['cc_type']} ({c.get('intent_id', c['cc_type'])})" for c in gitops_matrix]
        candidates_str += (
            "\nIf NONE of the detailed candidates above fit a secondary change, you MUST select an intent_id from this list. "
            "Do NOT invent new intents or emojis:\n"
        )
        candidates_str += ", ".join(vocab) + "\n"

        context_parts.append(candidates_str.strip())

    if contract is not None:
        contract_str = (
            "DETERMINISTIC SEMANTIC CONTRACT (LOCKED BEFORE GENERATION):\n"
            f"- primary_intent_id: {contract.primary_intent_id}\n"
            f"- gitmoji: {contract.gitmoji}\n"
            f"- cc_type: {contract.cc_type}\n"
            f"- semver_impact: {contract.semver_impact}\n"
            f"- changelog_group: {contract.changelog_group}\n"
            "CRITICAL: primary_intent.intent_id, gitmoji, cc_type, semver_impact, and changelog_group "
            "MUST match this contract exactly. Do not invent intent ids. "
            "You may only choose wording (description/body) and optional secondary intents from the matrix vocabulary."
        )
        context_parts.append(contract_str)

    # Issue #182 Slice 2: additive GOLD RUBRIC — wording quality only. Placed after the
    # DETERMINISTIC SEMANTIC CONTRACT block; never edits the CRITICAL field-lock sentences.
    from git_cg.commit_gold import BANNED_BODY_OPENERS

    banned = " / ".join(BANNED_BODY_OPENERS)
    gold_rubric = (
        "GOLD RUBRIC (WORDING QUALITY ONLY — does not change intent/semver/group):\n"
        "- Subject: state the user-visible outcome, not an inventory of files or edits. ≤50 chars, imperative.\n"
        "- Body: explain WHY the change is needed and the behaviour delta; note preserved invariants when relevant.\n"
        f"- Do NOT open the body with: {banned}.\n"
        "- Secondary intents: when the diff touches multiple distinct surfaces, put them in secondary_intents "
        "so the renderer emits exactly one Included changes section. Preserve every distinct "
        "evidence-backed responsibility (especially tests, docs, fixes, implementation); do not "
        "collapse a multi-surface diff into one intent solely because ranking confidence is low.\n"
        "- body_summary must NOT contain an `Included changes:` heading or nested bullets; "
        "those come only from secondary_intents as Hybrid mini-subjects "
        "(`- <emoji> <cc_type>(<scope>): <subject>`).\n"
        "- Never copy bracketed inventory lines (`[role/surface] ...`) into the final message.\n"
        "- This rubric guides wording only. It MUST NOT change intent_id, gitmoji, cc_type, semver_impact, or changelog_group."
    )
    context_parts.append(gold_rubric)

    # Shared staged-path discovery for Slice 4 inventory + Slice 6 checklist.
    # Prefer explicit staged_paths; fall back to diff signal files when omitted.
    presentation_paths = [p for p in (staged_paths or []) if p and str(p).strip()]
    presentation_signals = None
    if not presentation_paths:
        try:
            from git_cg.intent import extract_diff_signals as _extract_diff_signals_for_paths

            presentation_signals = _extract_diff_signals_for_paths(diff_output)
            presentation_paths = list(getattr(presentation_signals, "files", None) or [])
        except Exception:
            presentation_signals = None
            presentation_paths = []

    # Issue #204 Slice 4 — included-change stub inventory (D5/D18). Prompt pressure
    # only; LLM may rephrase. Never mutates ranked intent authority.
    try:
        from git_cg.commit_quality import (
            build_included_change_stubs,
            format_included_change_stub_inventory,
        )

        stub_signals = None if (staged_paths and ranked_candidates is not None) else presentation_signals
        stubs = build_included_change_stubs(
            presentation_paths,
            stub_signals,
            ranked_candidates,
            concern_tags=concern_tags,
            claim_tags=claim_tags,
        )
        inventory = format_included_change_stub_inventory(stubs)
        if inventory:
            context_parts.append(inventory)
    except Exception:
        # Inventory is best-effort presentation aid; never brick prompt build.
        pass

    # Issue #204 Slice 6 — high-risk body checklist (D6/D20). Prompt pressure only.
    # Injected only when staged high-risk product paths are present. Directive-free:
    # never sets preferred_type / rank steers; never treats docs prose as path evidence.
    try:
        from git_cg.commit_quality import format_high_risk_body_checklist

        checklist = format_high_risk_body_checklist(presentation_paths)
        if checklist:
            context_parts.append(checklist)
    except Exception:
        # Checklist is best-effort presentation aid; never brick prompt build.
        pass

    # Issue #204 Slice 5 — low-confidence body skeleton (D7). Prompt pressure only.
    if low_confidence_guidance and str(low_confidence_guidance).strip():
        context_parts.append(str(low_confidence_guidance).strip())

    if context_parts:
        gitops_matrix_str = "\n\n" + "\n\n".join(context_parts)

    system_prompt = (
        "You are a senior software engineer who writes perfect Conventional Commit messages. "
        "Analyze the provided git diff and the ranked intent candidates to generate a structured CommitPlan. "
        "If the diff contains multiple distinct changes, select the best primary intent and list the rest as secondary intents. "
        "Be concise, use the imperative mood for descriptions. "
        "CRITICAL: The primary description MUST NOT exceed 50 characters so the full header stays under 72 characters. "
        "CRITICAL: You must invoke the CommitPlan tool EXACTLY ONCE. Do not output multiple tool calls. Put all secondary intents inside the secondary_intents array. "
        "CRITICAL: Do not output reasoning, XML, pseudo-tool-call tags, or explanatory prose outside the single CommitPlan response. "
        "CRITICAL: intent_id values MUST exist in the SOP matrix / ranked candidates. Unknown intent ids are invalid. "
    )

    primary_lang = detect_primary_language(diff_output)
    if primary_lang:
        system_prompt += f"CRITICAL: The primary programming language detected in this diff is {primary_lang}. Act as an expert in this language and use its specific terminology when describing changes. "

    if commit_language:
        system_prompt += f"CRITICAL LOCALISATION: You MUST write the commit message natural-language prose strictly using the '{commit_language}' language locale. Explicitly preserve internal code identifiers, API names, CLI flags, filenames, and quoted strings in en-US. "

    system_prompt += f"{gitops_matrix_str}"

    # Issue #182 O-P0.2: three-channel assembly. The OVERRIDE + CRITICAL PRECEDENCE
    # ranking-override language is reserved for the user/directive channel only. The
    # previous-plan channel is neutral; the gold channel is directive-free wording feedback.
    user_override_active = bool(active_directives) or bool(residual_guidance)

    if user_override_active:
        # Channel 1 — user/directive (authoritative steers already resolved into contract).
        system_prompt += "\n\nREGENERATION GUIDANCE (EXPLICIT USER OVERRIDE):\n"
        system_prompt += "The developer has reviewed the initial result and provided correction guidance.\n"

        if active_directives:
            system_prompt += "\nDETERMINISTIC OVERRIDES (LOCKED SEMANTICS):\n"
            for key, value in active_directives.items():
                system_prompt += f"- {key}: {value}\n"
            system_prompt += "\nCRITICAL: These directives are LOCKED and MUST be applied exactly as specified. "
            system_prompt += "They override all other intent signals and ranking. "

        if residual_guidance:
            system_prompt += f'\n\nCONTEXTUAL GUIDANCE (FREE-TEXT):\n"{residual_guidance}"\n'
            system_prompt += "Use this contextual guidance to refine framing and emphasis. "

        system_prompt += "\n\nCRITICAL PRECEDENCE RULE: The deterministic overrides and guidance above take absolute precedence over the initial deterministic ranking for intent selection and framing. "
        system_prompt += "Do not treat the guidance text itself as final commit content or trailer text.\n"

    if previous_plan:
        # Channel 2 — previous plan (neutral delta context; no user-override labelling).
        # Emitted independently of the user-override channel so user-guided regeneration
        # retains the structured plan it is meant to update (the plan never inherits the
        # OVERRIDE + CRITICAL PRECEDENCE ranking-override language of channel 1).
        system_prompt += "\n\nPREVIOUS COMMIT PLAN (DELTA CONTEXT):\n"
        system_prompt += "You are regenerating the following commit. Treat this as a structural delta update. Do not rewrite from scratch unless new guidance demands it.\n"
        system_prompt += "```json\n" + previous_plan.model_dump_json(indent=2) + "\n```\n"

    if gold_guidance:
        # Channel 3 — gold feedback (directive-free; wording / secondary coverage only).
        system_prompt += "\n\nGOLD FEEDBACK (WORDING / SECONDARY COVERAGE ONLY):\n"
        system_prompt += f'"{gold_guidance}"\n'
        system_prompt += (
            "Apply this feedback to wording and secondary-intent coverage only. It MUST NOT change "
            "intent_id, gitmoji, cc_type, semver_impact, or changelog_group, and it is not an explicit "
            "user ranking override.\n"
        )

    if scoped_history_guidance:
        # Channel 4 — scoped-history feedback (directive-free; split/rename rationale only).
        system_prompt += "\n\nSCOPED-HISTORY FEEDBACK (SPLIT/RENAME RATIONALE ONLY):\n"
        system_prompt += f'"{scoped_history_guidance}"\n'
        system_prompt += (
            "Apply this feedback to split/rename rationale and wording only. It MUST NOT change "
            "intent_id, gitmoji, cc_type, semver_impact, or changelog_group, MUST NOT set or imply "
            "preferred_type, and it is not an explicit user ranking override.\n"
        )

    return system_prompt


def _write_commit_message(commit_msg_file: str, result_string: str, *, strict: bool, verbose: bool) -> None:
    """
    Write the provided commit message string to the specified file.

    Writes `result_string` as UTF-8 to `commit_msg_file`. If `verbose` is true, logs the destination path. On filesystem errors (`OSError`) the function aborts by calling `_abort(...)` with the provided `strict` behaviour.

    Parameters:
        commit_msg_file (str): Path to the commit message file to write.
        result_string (str): Commit message content to write.
        strict (bool): Passed to `_abort`; controls whether the process exits with a non-zero code.
        verbose (bool): When true, log the path of the written commit message.
    """
    try:
        with open(commit_msg_file, "w", encoding="utf-8") as f:
            f.write(result_string)
        if verbose:
            console.log(f"Commit message written to {commit_msg_file}")
    except OSError as e:
        _abort(f"[bold red]Error writing to {commit_msg_file}:[/bold red] {e}", strict=strict)


def _build_issue_reference(review_state: ReviewState) -> IssueReference | None:
    """
    Prompt the user to select an issue reference type and an issue number, and construct the corresponding IssueReference.

    Parameters:
        review_state (ReviewState): Accepted for orchestration symmetry with the interactive flow; not modified.

    Returns:
        IssueReference or None: An `IssueReference` when the user supplies both a reference type and an issue number, `None` if the user cancels or selects "Back".
    """
    reference_type = prompt_issue_reference_type()
    if reference_type in (None, "Back"):
        return None

    issue_number = prompt_issue_number()
    if issue_number is None:
        return None

    return IssueReference(kind=IssueReferenceKind(reference_type), issue_number=issue_number)


def _build_regeneration_guidance(review_state: ReviewState) -> str | None:
    """
    Prompt for regeneration guidance to influence the next AI generation attempt.

    Uses the review state's current `regeneration_guidance` value as the prompt's initial/default text.

    Parameters:
        review_state (ReviewState): The review state providing the current guidance to pre-populate the prompt.

    Returns:
        str | None: The entered regeneration guidance, or `None` if the prompt was cancelled.
    """
    return prompt_regeneration_guidance(review_state.regeneration_guidance)


def _interactive_review(
    commit_msg_file: str, review_state: ReviewState, *, verbose: bool, strict: bool, gui_editor: bool = False
) -> str:
    """
    Display an interactive review prompt for a generated commit message.

    Parameters:
        commit_msg_file (str): Path to the commit message file to update when review changes are saved.
        review_state (ReviewState): Current review state, including the generated message and any attached issue references.
        verbose (bool): Print status messages when interactive input is unavailable or when review state changes.
        strict (bool): Control how write failures are handled when updating the commit message file.
        gui_editor (bool): Use graphical editor environment variables when opening the message for editing.

    Returns:
        str: The selected action.
    """
    emit_terminal_bell()

    while True:
        result_string = review_state.render()
        status_parts = [
            format_issue_reference_status(review_state.issue_references),
            format_regeneration_guidance_status(review_state.regeneration_guidance),
        ]
        conf_status = format_ranking_confidence_status(
            review_state.ranking_confidence_level,
            review_state.ranking_confidence_margin,
            review_state.ranking_confidence_reasons or None,
            top_intent_id=review_state.ranking_confidence_top_intent_id,
            runner_up_intent_id=review_state.ranking_confidence_runner_up_intent_id,
        )
        if conf_status:
            status_parts.append(conf_status)
        gold_status = format_gold_findings_status(review_state.gold_findings or None)
        if gold_status:
            status_parts.append(gold_status)
        status_text = "\n".join(status_parts)
        action = prompt_with_gum(
            title="git-cg Generated Commit",
            body=result_string,
            status_text=status_text,
        )
        if action is None:
            if verbose:
                console.log(
                    "[yellow]Interactive mode requested but gum or /dev/tty is unavailable (or cancelled). Proceeding non-interactively.[/yellow]"
                )
            return "Commit"

        if action == "Add issue reference":
            issue_reference = _build_issue_reference(review_state)
            if issue_reference is None:
                continue

            mutation_result = review_state.add_issue_reference(issue_reference)
            if mutation_result == ReviewStateMutationResult.ADDED:
                _write_commit_message(commit_msg_file, review_state.render(), strict=strict, verbose=verbose)
            elif mutation_result == ReviewStateMutationResult.DUPLICATE:
                console.print(f"[yellow]{issue_reference} is already attached to this review state.[/yellow]")
            elif mutation_result == ReviewStateMutationResult.CONFLICT:
                console.print(
                    f"[red]Conflict! An issue reference for #{issue_reference.issue_number} already exists with a different verb. Overwriting is not permitted.[/red]"
                )
            continue

        if action == "Add regenerate guidance":
            regeneration_guidance = _build_regeneration_guidance(review_state)
            if regeneration_guidance is None:
                continue

            if review_state.set_regeneration_guidance(regeneration_guidance):
                console.print("[green]Regeneration guidance updated.[/green]")
            else:
                console.print("[yellow]Regeneration guidance is already set to that value.[/yellow]")
            continue

        if action == "Clear regenerate guidance":
            if review_state.clear_regeneration_guidance():
                console.print("[yellow]Regeneration guidance cleared.[/yellow]")
            else:
                console.print("[yellow]No regeneration guidance is currently attached.[/yellow]")
            continue

        if action == "Print plain text":
            console.print(review_state.render())
            continue

        if action == "Edit":
            if gui_editor:
                preferred_editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
            else:
                preferred_editor = os.environ.get("GIT_CG_EDITOR") or os.environ.get("EDITOR")
            click.edit(filename=commit_msg_file, editor=preferred_editor)
        return action


def _interactive_review_dry_run(
    review_state: ReviewState, *, verbose: bool, strict: bool, gui_editor: bool = False
) -> str:
    """
    Present the current review state for interactive dry-run review.

    Parameters:
        review_state (ReviewState): The generated commit plan and associated review state.
        verbose (bool): Whether to enable verbose output during review.
        strict (bool): Whether to apply strict error handling.
        gui_editor (bool): Whether to use GUI editor preferences when editing.

    Returns:
        str: The action selected by the user.
    """
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, suffix=".git-cg-preview.txt"
        ) as temp_file:
            temp_file.write(review_state.render())
            temp_path = temp_file.name
        return _interactive_review(temp_path, review_state, verbose=verbose, strict=strict, gui_editor=gui_editor)
    finally:
        if temp_path:
            with contextlib.suppress(OSError):
                os.unlink(temp_path)


# Interim prompt ceiling until Phase 11 PromptBudget (Issue #161 Slice 4).
# Analysis/rank must never share a hard mid-string slice of this budget.
PROMPT_DIFF_MAX_CHARS = 50_000
_DIFF_FILE_HEADER_RE = re.compile(r"(?m)^diff --git ")


def _staged_diff_command(*, use_rtk: bool) -> list[str]:
    """Build the staged-diff argv, optionally via rtk token compression."""
    excludes = [
        ":(exclude)*.lock",
        ":(exclude)*-lock.json",
        ":(exclude)*-lock.yaml",
        ":(exclude)*.lockb",
        ":(exclude)*zensical*",
        ":(exclude)*auxly*",
    ]
    if use_rtk:
        return ["rtk", "git", "diff", "--cached", "--", ".", *excludes]
    return ["git", "diff", "--cached", "--", ".", *excludes]


def pack_prompt_diff(
    analysis_diff: str,
    *,
    max_chars: int = PROMPT_DIFF_MAX_CHARS,
) -> tuple[str, list[str]]:
    """
    Prepare a size-limited diff for use in an LLM prompt.

    Preserves complete file sections where possible and reports omitted paths in the returned inventory. Large or unstructured diffs may be truncated with an explanatory note.

    Parameters:
        analysis_diff (str): Full staged diff used for analysis and intent ranking.
        max_chars (int): Maximum size of the prompt-bound diff.

    Returns:
        tuple[str, list[str]]: The prompt-bound diff and paths omitted from it.

    Raises:
        ValueError: If `max_chars` is less than or equal to zero.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")

    if len(analysis_diff) <= max_chars:
        return analysis_diff, []

    matches = list(_DIFF_FILE_HEADER_RE.finditer(analysis_diff))
    if not matches:
        # No file headers — keep a conservative prefix with an explicit note.
        # Always honour max_chars, even when the notice is longer than the budget.
        note = "\n\n... [PROMPT DIFF TRUNCATED — no file boundaries found; analysis/rank used full staged diff] ...\n"
        if len(note) >= max_chars:
            return note[:max_chars], ["<unbounded-diff>"]
        kept = analysis_diff[: max(0, max_chars - len(note))].rstrip()
        return (kept + note)[:max_chars], ["<unbounded-diff>"]

    sections: list[tuple[str | None, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(analysis_diff)
        header_line = analysis_diff[start : analysis_diff.find("\n", start)]
        path = None
        parts = header_line.split()
        if len(parts) >= 4 and parts[2].startswith("a/") and parts[3].startswith("b/"):
            path = parts[3][2:]
        sections.append((path, analysis_diff[start:end]))

    prefix = analysis_diff[: matches[0].start()]
    kept_parts: list[str] = [prefix] if prefix else []
    used = len(prefix)
    omitted_paths: list[str] = []

    for path, body in sections:
        # Reserve room for a short omission footer if we drop anything later.
        footer_reserve = 180
        if used + len(body) + footer_reserve <= max_chars:
            kept_parts.append(body)
            used += len(body)
        else:
            omitted_paths.append(path or "<unknown-path>")

    # If the first kept payload is empty because every section exceeded the budget,
    # retain a file-header-safe prefix of the first section so the prompt is not blank.
    kept_body = "".join(kept_parts).strip()
    if not kept_body and sections:
        first_path, first_body = sections[0]
        note = (
            "\n\n... [PROMPT DIFF TRUNCATED at file boundary budget; "
            "single large file partially omitted from prompt only] ...\n"
        )
        omitted = omitted_paths or [first_path or "<unknown-path>"]
        if len(note) >= max_chars:
            return note[:max_chars], omitted
        kept = (prefix + first_body)[: max(0, max_chars - len(note))].rstrip()
        return (kept + note)[:max_chars], omitted

    if not omitted_paths:
        return analysis_diff if len(analysis_diff) <= max_chars else "".join(kept_parts), []

    inventory_lines = ", ".join(omitted_paths[:40])
    more = "" if len(omitted_paths) <= 40 else f" (+{len(omitted_paths) - 40} more)"
    footer = (
        "\n\n... [PROMPT DIFF OMISSION INVENTORY — analysis/rank used full staged diff] ...\n"
        f"Omitted from prompt ({len(omitted_paths)} path(s)): {inventory_lines}{more}\n"
    )
    packed = "".join(kept_parts).rstrip() + footer
    if len(packed) > max_chars:
        # Keep the final string (including any trailing newline) within max_chars.
        packed = packed[:max_chars].rstrip()
        if len(packed) < max_chars:
            packed += "\n"
        packed = packed[:max_chars]
    return packed, omitted_paths


@opik.track(project_name="gitCommitGenerator")
def extract_git_diff(verbose: bool, strict: bool) -> str:
    """
    Extract the staged Git diff for analysis and ranking.

    Always uses standard ``git diff --cached`` so signal extraction, intent
    ranking, and path-class gates receive a real unified diff. RTK must not
    wrap this path: its summarized non-unified output collapses
    ``path_class_gate`` to ``empty`` and corrupts content markers (Issue #212).
    Prompt-size limits remain the job of ``pack_prompt_diff`` only.

    Returns:
        str: The staged diff content.

    Raises:
        typer.Exit: If diff extraction fails or no staged changes are found.
    """
    try:
        if verbose:
            console.log("Extracting staged analysis diff via standard git...")
        # Analysis path is always plain git. Keep RTK off the ranking/signal path.
        diff_output = subprocess.check_output(
            _staged_diff_command(use_rtk=False),
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        _abort(f"[bold red]Error getting git diff:[/bold red] {e.output}", strict=strict)

    if not diff_output.strip():
        console.print("[yellow]No staged changes found. Aborting commit message generation.[/yellow]")
        raise typer.Exit(code=0)

    if verbose:
        console.log(f"Extracted analysis git diff ({len(diff_output)} characters).")

    return diff_output


def _validate_commit_source(
    commit_source: str | None,
    commit_msg_file: str,
    amend_regenerate: bool,
    verbose: bool,
) -> str | None:
    if commit_source and (commit_source == commit_msg_file or commit_source.endswith("COMMIT_EDITMSG")):
        commit_source = None

    if commit_source not in GENERATING_SOURCES:
        if amend_regenerate and commit_source == "commit":
            if verbose:
                console.log("Amend regeneration explicitly enabled; proceeding.")
        else:
            if verbose:
                console.log(
                    f"Commit source '{commit_source}' indicates an existing message (merge/squash/amend/-m). Skipping generation."
                )
            raise typer.Exit(code=0)
    return commit_source


def _detect_branch_issue_reference(verbose: bool) -> list[IssueReference]:
    """
    Detect an issue reference from the current Git branch name.

    Parameters:
        verbose (bool): Whether to log the detected issue reference.

    Returns:
        list[IssueReference]: Issue references containing the first number followed by a hyphen found after a slash or at the start of the branch name.
    """
    issue_references: list[IssueReference] = []
    try:
        branch_name = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
        match = re.search(r"(?:/|^)(\d+)-", branch_name)
        if match:
            issue_number = int(match.group(1))
            issue_references.append(IssueReference(kind=IssueReferenceKind.REFS, issue_number=issue_number))
            if verbose:
                console.log(f"Auto-detected issue #{issue_number} from branch '{branch_name}'.")
    except Exception:
        pass
    return issue_references


def _build_generation_context(
    diff_output: str,
    *,
    enable_semantic: bool | None = None,
    enrichment_facts=None,
    semantic_summary=None,
    risk_assessment=None,
):
    """
    Build the deterministic context used for commit generation.

    Sole rank-pass owner (Issue #195): constructs the authoritative
    ``ranked_intents`` snapshot and its paired ``ranking_confidence`` exactly
    once. Downstream consumers (prompt, contract, TUI, telemetry) must receive
    this pair and must not re-run ranking or confidence on the normal path.

    Parameters:
        diff_output (str): The staged diff to analyse.
        enable_semantic (bool | None): Whether semantic enrichment is enabled.
        enrichment_facts: Optional closed-vocabulary semantic facts used to enrich intent ranking.
        semantic_summary: Optional Phase 7 ``SemanticDiffSummary`` (flag-on only).
        risk_assessment: Optional Phase 7 ``RiskAssessment`` (flag-on only).

    Returns:
        GenerationContext: Diff signals, ranked intents, confidence, constraints, and optional semantic context.
    """
    from git_cg.intent import IntentSelectionConstraints, derive_intent_selection_constraints
    from git_cg.ranking_confidence import compute_ranking_confidence
    from git_cg.regeneration import GenerationContext
    from git_cg.semantic_flags import is_semantic_enabled

    signals = extract_diff_signals(diff_output)
    gitops_matrix = load_sop().get("gitmoji_reference_matrix", [])
    semantic_on = is_semantic_enabled(enable_semantic)
    ranked_candidates = (
        rank_commit_intents(
            signals,
            gitops_matrix,
            enrichment=enrichment_facts if semantic_on else None,
            enable_semantic=semantic_on,
        )
        if gitops_matrix
        else []
    )
    constraints = (
        derive_intent_selection_constraints(signals, gitops_matrix) if gitops_matrix else IntentSelectionConstraints()
    )
    # Confidence is bound to this rank pass only; empty rank → no confidence object.
    ranking_confidence = compute_ranking_confidence(ranked_candidates) if ranked_candidates else None
    # Issue #204 Slice 2/2b: TrailerPriors + DiffClass constraints (D25).
    # Must not feed rank_commit_intents — presentation only.
    # Path recovery: prefer signals.files; constraints_from_paths/_resolve_paths
    # also fall back to signals when the explicit list is empty. Empty remains
    # unknown (not a pure non-product force-NONE envelope).
    from git_cg.commit_quality import constraints_from_paths, derive_trailer_priors

    staged = [p for p in (signals.files or []) if p and str(p).strip()]
    if not staged:
        # Second-chance path harvest from the raw diff when signal files were empty.
        try:
            from git_cg.intent import extract_diff_file_summary

            staged = [p for p in (extract_diff_file_summary(diff_output).paths or []) if p and str(p).strip()]
            if staged and not signals.files:
                signals.files = list(staged)
        except Exception:
            staged = []
    scope_priors = derive_trailer_priors(staged, signals=signals)
    presentation_constraints = constraints_from_paths(staged, signals=signals)
    return GenerationContext(
        diff_signals=signals,
        ranked_intents=ranked_candidates,
        constraints=constraints,
        semantic_summary=semantic_summary if semantic_on else None,
        risk_assessment=risk_assessment if semantic_on else None,
        scope_priors=scope_priors,
        presentation_constraints=presentation_constraints,
        ranking_confidence=ranking_confidence,
    )


def _build_semantic_enrichment_facts(
    *,
    semantic_enabled: bool,
    fingerprint_class_counts: dict | None,
    body_similarity_min: float | None,
    body_similarity_avg: float | None,
    fingerprint_markers: list | None,
    graph_enrichment=None,
):
    """
    Build optional semantic enrichment facts from fingerprint and graph product data.

    Parameters:
        semantic_enabled (bool): Whether semantic enrichment is enabled.
        fingerprint_class_counts (dict | None): Fingerprint counts grouped by class.
        body_similarity_min (float | None): Minimum body similarity score.
        body_similarity_avg (float | None): Average body similarity score.
        fingerprint_markers (list | None): Markers identified during fingerprint comparison.
        graph_enrichment: Optional ``GraphEnrichmentFacts`` from Phase 7 graph product bundle.

    Returns:
        SemanticEnrichmentFacts | None: Enrichment facts when semantic mode is enabled and usable
        fingerprint and/or graph data is available; otherwise, `None`.
    """
    if not semantic_enabled:
        return None

    from git_cg.intent import FingerprintEnrichmentFacts, GraphEnrichmentFacts, SemanticEnrichmentFacts

    has_fp = bool(fingerprint_class_counts) or bool(fingerprint_markers)
    has_sim = body_similarity_min is not None or body_similarity_avg is not None
    graph_facts = graph_enrichment if isinstance(graph_enrichment, GraphEnrichmentFacts) else None
    has_graph = graph_facts is not None and graph_facts.outcome == "ok"
    if not has_fp and not has_sim and not has_graph:
        return None

    fingerprints = None
    if has_fp or has_sim:
        fingerprints = FingerprintEnrichmentFacts(
            class_counts=dict(fingerprint_class_counts) if fingerprint_class_counts else None,
            body_similarity_min=body_similarity_min,
            body_similarity_avg=body_similarity_avg,
            markers=list(fingerprint_markers) if fingerprint_markers else None,
        )

    return SemanticEnrichmentFacts(
        graph=graph_facts,
        fingerprints=fingerprints,
    )


def _presentation_telemetry_from_context(
    gen_context: object | None,
    *,
    commit_plan: object | None = None,
    preferred_scope_raw: str | None = None,
) -> tuple[str, bool, str]:
    """Derive closed D26 presentation telemetry from context/plan (Issue #204 Slice 10).

    Returns:
        (path_class_gate, changelog_antisignal_applied, scope_normalised_from)
    """
    path_class_gate = "none"
    changelog_antisignal_applied = False
    scope_normalised_from = "none"

    cons = getattr(gen_context, "presentation_constraints", None) if gen_context is not None else None
    if cons is not None:
        raw_class = getattr(cons, "diff_class", None)
        if raw_class:
            path_class_gate = str(raw_class)
        changelog_antisignal_applied = bool(getattr(cons, "changelog_antisignal_applied", False))

    # Prefer the raw pre-normalise token when available; else final primary scope.
    probe = preferred_scope_raw
    if not probe and commit_plan is not None:
        primary = getattr(commit_plan, "primary_intent", None)
        probe = getattr(primary, "scope", None) if primary is not None else None
    if probe:
        try:
            from git_cg.scope_canon import resolve_scope_normalisation

            _canon, scope_normalised_from = resolve_scope_normalisation(str(probe))
            del _canon
        except Exception:
            scope_normalised_from = "none"

    return path_class_gate, changelog_antisignal_applied, scope_normalised_from


def _write_telemetry_state_safe(
    review_state: ReviewState | None,
    diff_output: str,
    engine: str,
    model_name: str,
    system_prompt: str,
    repo_name: str,
    thread_id: str,
    verbose: bool,
    graph_schema_version: str = "unknown",
    *,
    semantic_enabled: bool = False,
    parser_latency_ms: float = 0.0,
    graph_build_latency_ms: float = 0.0,
    graph_query_latency_ms: float = 0.0,
    semantic_parser_metrics: dict | None = None,
    body_similarity_min: float | None = None,
    body_similarity_avg: float | None = None,
    fingerprint_files_compared: int = 0,
    fingerprint_latency_ms: float = 0.0,
    fingerprint_class_counts: dict | None = None,
    fingerprint_grammar_version: str = "unknown",
    fingerprint_markers: list | None = None,
    preflight_mode: str = "skipped",
    preflight_groups_count: int = 0,
    preflight_fallback_reason: str = "",
    blast_radius_size: int | None = None,
    affected_flows_count: int | None = None,
    test_coverage_gap: bool | None = None,
    test_gaps_count: int | None = None,
    semantic_context_schema_version: str = "",
    semantic_context_fallback_reasons: list | None = None,
    shadow_workspace_used: bool = False,
    semantic_refresh_graph: str = "skipped",
    shadow_fail_open_reason: str = "none",
    ranking_confidence_level: str | None = None,
    ranking_confidence_margin: float | None = None,
    ranking_confidence_reasons: list | None = None,
    ranking_choice_path: str | None = None,
    ranking_override: bool = False,
    ranking_arbitrate_effective: str | None = None,
    lock_resolution: str = "absent",
    gold_mode: str = "off",
    gold_findings_count: int = 0,
    gold_finding_codes: list | None = None,
    gold_blocked: bool = False,
    gold_regen_attempts: int = 0,
    gold_self_correction_attempts: int = 0,
    gold_self_correction_outcome: str = "not_needed",
    gold_split_recommendation: bool = False,
    scoped_history_fallback_reason: str = "none",
    scoped_history_latency_ms: float = 0.0,
    rename_confidence: str = "none",
    scoped_history_split_high_confidence: bool = False,
    scoped_history_guidance: str | None = None,
    scoped_history_split_rationale: str = "",
    scoped_history_rename_rationale: str = "",
    structural_error_handling: bool = False,
    structural_public_api: bool = False,
    structural_new_command: bool = False,
    presentation_fallback_reason: str = "none",
    blueprint_applied: bool = False,
    hallucination_guard_fired: bool = False,
    path_class_gate: str = "none",
    changelog_antisignal_applied: bool = False,
    scope_normalised_from: str = "none",
    contract_lift_applied: bool = False,
    contract_lift_from_semver: str | None = None,
    contract_locked_semver: str | None = None,
    llm_raw_semver: str | None = None,
    plan_persisted_semver: str | None = None,
    contract_violation: bool = False,
    plan_normaliser_applied: bool = False,
    plan_normaliser_reason: str = "none",
) -> None:
    """
    Persist generation telemetry for the reviewed commit plan without interrupting the main workflow.

    Parameters:
        review_state (ReviewState): Review state containing the generated commit plan and final message.
        diff_output (str): Staged diff used for generation.
        engine (str): AI engine used for generation.
        model_name (str): Model used for generation.
        system_prompt (str): System prompt used for generation.
        repo_name (str): Repository name associated with the generation.
        thread_id (str): Telemetry thread identifier.
        verbose (bool): Whether to log telemetry write failures and success details.
        graph_schema_version (str): Semantic graph schema version.
        semantic_enabled (bool): Whether semantic processing was enabled.
        parser_latency_ms (float): Semantic parser latency in milliseconds.
        graph_build_latency_ms (float): Semantic graph build latency in milliseconds.
        graph_query_latency_ms (float): Semantic graph query latency in milliseconds.
        semantic_parser_metrics (dict | None): Metrics collected during semantic parsing.
        body_similarity_min (float | None): Minimum body similarity measured during fingerprint comparison.
        body_similarity_avg (float | None): Average body similarity measured during fingerprint comparison.
        fingerprint_files_compared (int): Number of files included in fingerprint comparison.
        fingerprint_latency_ms (float): Fingerprint comparison latency in milliseconds.
        fingerprint_class_counts (dict | None): Counts of fingerprint comparison classes.
        fingerprint_grammar_version (str): Fingerprint grammar version used for comparison.
        fingerprint_markers (list | None): Markers produced during fingerprint comparison.
        preflight_mode (str): Preflight grouping mode (`llm` / `heuristic` / `skipped`).
        preflight_groups_count (int): Number of preflight groups when preflight ran.
        preflight_fallback_reason (str): Why preflight skipped or fell back (redacted on write).
        blast_radius_size (int | None): Phase 7 graph blast-radius size when available.
        affected_flows_count (int | None): Phase 7 affected-flows count when available.
        test_coverage_gap (bool | None): Phase 7 coverage-gap flag when available.
        test_gaps_count (int | None): Optional raw test-gap count for analytics/debug.
        semantic_context_schema_version (str): SemanticDiffSummary schema version when built.
        semantic_context_fallback_reasons (list | None): Bounded redacted fallback reasons.
        shadow_workspace_used (bool): Phase 7.5 — whether index-only shadow path engaged.
        semantic_refresh_graph (str): Phase 7.5 — `skipped` · `requested` · `ran`.
        shadow_fail_open_reason (str): Phase 7.5 — closed fail-open category (`none` default).
        ranking_confidence_level (str | None): Issue #195 closed level (`high`/`medium`/`low`).
        ranking_confidence_margin (float | None): Issue #195 top-minus-runner-up margin.
        ranking_confidence_reasons (list | None): Issue #195 closed reason codes only.
        ranking_choice_path (str | None): Issue #195 terminal choice path.
        ranking_override (bool): Issue #195 metadata bool (never 1.0/0.0 here).
        ranking_arbitrate_effective (str | None): Issue #195 gate result enum.
        lock_resolution (str): Issue #195 lock observability code.
        gold_mode (str): Phase 7.25 gold mode for the run.
        gold_findings_count (int): Count of gold findings.
        gold_finding_codes (list | None): Sorted closed gold finding codes only.
        gold_blocked (bool): Whether gold blocked under the resolved mode.
        gold_regen_attempts (int): Bounded gold wording regen attempts (0..2).
        gold_self_correction_attempts (int): Issue #191 self-correction depth (0..2).
        gold_self_correction_outcome (str): Issue #191 closed outcome enum value.
        gold_split_recommendation (bool): Issue #191 P6 ≥3-group split-prefer path fired.
        scoped_history_fallback_reason (str): Phase 9 closed fallback reason.
        scoped_history_latency_ms (float): Phase 9 producer latency in milliseconds.
        rename_confidence (str): Phase 9 rename confidence band (`none`/`low`/`medium`/`high`).
        scoped_history_split_high_confidence (bool): Phase 9 flow-disjoint split evidence.
        scoped_history_guidance (str | None): Phase 9 Channel-4 guidance (redacted on write).
        scoped_history_split_rationale (str): Phase 9 split rationale (redacted on write).
        scoped_history_rename_rationale (str): Phase 9 rename rationale (redacted on write).
        structural_error_handling (bool): Phase 9 structural error-handling marker.
        structural_public_api (bool): Phase 9 structural public-API marker.
        structural_new_command (bool): Phase 9 structural new-command marker.
        presentation_fallback_reason (str): Issue #204 closed presentation fallback reason.
        blueprint_applied (bool): Issue #204 Slice 7 — True when a legal operator blueprint overlay was applied.
        hallucination_guard_fired (bool): Issue #204 Slice 8 — True when hallucination guard rejected unevidenced claims.
        path_class_gate (str): Issue #204 Slice 10 — closed DiffClass label or none.
        changelog_antisignal_applied (bool): Issue #204 Slice 10 — changelog marker exclusion engaged.
        scope_normalised_from (str): Issue #204 Slice 10 — CANONICAL_SCOPE_ALIASES key or none (RF-1).
        contract_lift_applied (bool): Issue #204 Slice 5 — True when post-presentation SemVer was lifted to the locked contract floor.
        contract_lift_from_semver (str | None): Issue #204 Slice 5 — pre-lift SemVer value when a lift occurred.
        contract_locked_semver (str | None): Issue #204 Slice 5.5 — locked contract SemVer.
        llm_raw_semver (str | None): Issue #204 Slice 5.5 — raw LLM SemVer pre-enforce.
        plan_persisted_semver (str | None): Issue #204 Slice 5.5 — final primary SemVer.
        contract_violation (bool): Issue #204 Slice 5.5 — locked vs persisted diverge.
        plan_normaliser_applied (bool): Issue #204 Slice 5.5 — normaliser/lift touched SemVer.
        plan_normaliser_reason (str): Issue #204 Slice 5.5 — closed normaliser reason.
    """
    try:
        import dataclasses

        from git_cg.telemetry import (
            GenerationTelemetry,
            compute_diff_hash,
            run_deterministic_checks,
            write_telemetry_state,
        )

        if review_state is not None:
            score_card = run_deterministic_checks(review_state.commit_plan)
            generated_message = review_state.render()
            commit_plan_json = review_state.commit_plan.model_dump()
            score_card_dict = dataclasses.asdict(score_card)
        else:
            # Pre-LLM abort (e.g. arbitration cancel) — no plan yet; still emit funnel telemetry.
            generated_message = ""
            commit_plan_json = {}
            score_card_dict = {}

        telemetry = GenerationTelemetry(
            trace_id=LAST_OPIK_TRACE_ID,
            diff_hash=compute_diff_hash(diff_output),
            diff_output=diff_output,
            repo_name=repo_name,
            engine=engine,
            model_name=model_name,
            system_prompt_hash=compute_prompt_hash(system_prompt),
            generated_message=generated_message,
            commit_plan_json=commit_plan_json,
            score_card=score_card_dict,
            thread_id=thread_id,
            graph_schema_version=graph_schema_version,
            semantic_enabled=semantic_enabled,
            parser_latency_ms=parser_latency_ms,
            graph_build_latency_ms=graph_build_latency_ms,
            graph_query_latency_ms=graph_query_latency_ms,
            semantic_parser_metrics=semantic_parser_metrics,
            body_similarity_min=body_similarity_min,
            body_similarity_avg=body_similarity_avg,
            fingerprint_files_compared=fingerprint_files_compared,
            fingerprint_latency_ms=fingerprint_latency_ms,
            fingerprint_class_counts=fingerprint_class_counts,
            fingerprint_grammar_version=fingerprint_grammar_version,
            fingerprint_markers=fingerprint_markers,
            preflight_mode=preflight_mode,
            preflight_groups_count=preflight_groups_count,
            preflight_fallback_reason=preflight_fallback_reason,
            blast_radius_size=blast_radius_size,
            affected_flows_count=affected_flows_count,
            test_coverage_gap=test_coverage_gap,
            test_gaps_count=test_gaps_count,
            semantic_context_schema_version=semantic_context_schema_version,
            semantic_context_fallback_reasons=(
                list(semantic_context_fallback_reasons) if isinstance(semantic_context_fallback_reasons, list) else None
            ),
            shadow_workspace_used=bool(shadow_workspace_used),
            semantic_refresh_graph=str(semantic_refresh_graph or "skipped"),
            shadow_fail_open_reason=str(shadow_fail_open_reason or "none"),
            ranking_confidence_level=ranking_confidence_level,
            ranking_confidence_margin=ranking_confidence_margin,
            ranking_confidence_reasons=(
                list(ranking_confidence_reasons) if isinstance(ranking_confidence_reasons, list) else None
            ),
            ranking_choice_path=ranking_choice_path,
            ranking_override=bool(ranking_override),
            ranking_arbitrate_effective=ranking_arbitrate_effective,
            lock_resolution=str(lock_resolution or "absent"),
            gold_mode=str(gold_mode or "off"),
            gold_findings_count=int(gold_findings_count or 0),
            gold_finding_codes=(
                sorted({str(c) for c in gold_finding_codes if c is not None})
                if isinstance(gold_finding_codes, list)
                else None
            ),
            gold_blocked=bool(gold_blocked),
            gold_regen_attempts=int(gold_regen_attempts or 0),
            gold_self_correction_attempts=int(gold_self_correction_attempts or 0),
            gold_self_correction_outcome=str(gold_self_correction_outcome or "not_needed"),
            gold_split_recommendation=bool(gold_split_recommendation),
            scoped_history_fallback_reason=str(scoped_history_fallback_reason or "none"),
            scoped_history_latency_ms=float(scoped_history_latency_ms or 0.0),
            rename_confidence=str(rename_confidence or "none"),
            scoped_history_split_high_confidence=bool(scoped_history_split_high_confidence),
            scoped_history_guidance=scoped_history_guidance if isinstance(scoped_history_guidance, str) else None,
            scoped_history_split_rationale=str(scoped_history_split_rationale or ""),
            scoped_history_rename_rationale=str(scoped_history_rename_rationale or ""),
            structural_error_handling=bool(structural_error_handling),
            structural_public_api=bool(structural_public_api),
            structural_new_command=bool(structural_new_command),
            presentation_fallback_reason=str(presentation_fallback_reason or "none"),
            blueprint_applied=bool(blueprint_applied),
            hallucination_guard_fired=bool(hallucination_guard_fired),
            path_class_gate=str(path_class_gate or "none"),
            changelog_antisignal_applied=bool(changelog_antisignal_applied),
            scope_normalised_from=str(scope_normalised_from or "none"),
            contract_lift_applied=bool(contract_lift_applied),
            contract_lift_from_semver=(
                str(contract_lift_from_semver) if contract_lift_from_semver is not None else None
            ),
            contract_locked_semver=(str(contract_locked_semver) if contract_locked_semver is not None else None),
            llm_raw_semver=str(llm_raw_semver) if llm_raw_semver is not None else None,
            plan_persisted_semver=(str(plan_persisted_semver) if plan_persisted_semver is not None else None),
            contract_violation=bool(contract_violation),
            plan_normaliser_applied=bool(plan_normaliser_applied),
            plan_normaliser_reason=str(plan_normaliser_reason or "none"),
        )
        try:
            git_dir = subprocess.check_output(["git", "rev-parse", "--git-dir"], text=True).strip()
            write_telemetry_state(git_dir, telemetry)
            if verbose:
                console.log(f"Opik telemetry state written to {git_dir}/GIT_CG_OPIK_STATE.json")
        except Exception as inner_e:
            if verbose:
                console.log(f"[yellow]Failed to resolve git dir or write state: {inner_e}[/yellow]")
    except Exception as e:
        if verbose:
            console.log(f"[yellow]Failed to write telemetry state: {e}[/yellow]")


def _merge_graph_fallback_reasons(existing: list | None, *extra_groups: list | str | None) -> list[str]:
    """Append, de-dupe (order-preserving), and bound graph fallback reasons.

    Phase 7.5 (#180): keep one vocabulary-bound merge path for shadow/refresh
    fail-open reasons and later product/stage fallbacks.
    """
    from git_cg.semantic import MAX_FALLBACK_REASONS, _bound_str_list

    merged: list[str] = []
    seen: set[str] = set()

    def _extend(group: list | str | None) -> None:
        if group is None:
            return
        values = [group] if isinstance(group, str) else list(group or [])
        for reason in values:
            if not isinstance(reason, str) or not reason or reason in seen:
                continue
            seen.add(reason)
            merged.append(reason)

    _extend(existing)
    for group in extra_groups:
        _extend(group)
    return _bound_str_list(merged, max_items=MAX_FALLBACK_REASONS)


def _collect_semantic_producer_metrics(
    repo_root: str,
    *,
    enable_semantic: bool | None,
    verbose: bool = False,
    preflight_groups_count: int = 0,
) -> dict:
    """
    Run dark-launched Phase 1/2 semantic producers and return telemetry fields.

    Flag-off returns zero-safe defaults without touching git/graph/parser I/O.
    Flag-on collects staged parse metrics, HEAD/index fingerprint aggregates, and
    optional graph latencies. Never raises; failures degrade to empty metrics.

    ``preflight_groups_count`` is carry-through only (Phase 0.5 product owns
    grouping). When already >1 it elevates scoped-history split confidence.
    """
    from git_cg.ast_parser import empty_parser_metrics
    from git_cg.semantic_flags import is_semantic_enabled

    semantic_enabled = is_semantic_enabled(enable_semantic)
    # Local defaults keep flag-off zero-safe without importing Phase 7 semantic module.
    graph_product_defaults = {
        "blast_radius_size": None,
        "affected_flows_count": None,
        "test_coverage_gap": None,
        "test_gaps_count": None,
        "risk_assessment": None,
        "graph_enrichment": None,
        "graph_fallback_reasons": [],
        "impacts_tests": None,
        "impacts_production_code": None,
        "impacts_hub_node": None,
        "complex_function_changed": None,
        "notable_callers": [],
    }

    result: dict = {
        "semantic_enabled": semantic_enabled,
        "parser_latency_ms": 0.0,
        "graph_build_latency_ms": 0.0,
        "graph_query_latency_ms": 0.0,
        "semantic_parser_metrics": empty_parser_metrics(enabled=False),
        "body_similarity_min": None,
        "body_similarity_avg": None,
        "fingerprint_files_compared": 0,
        "fingerprint_latency_ms": 0.0,
        "fingerprint_class_counts": None,
        "fingerprint_grammar_version": "unknown",
        "fingerprint_markers": None,
        "crg_schema_version": None,
        **graph_product_defaults,
        "changed_files": [],
    }
    if not semantic_enabled:
        # Phase 9 flag-off defaults (safe; no producer side effects).
        result.setdefault("scoped_history_fallback_reason", "none")
        result.setdefault("scoped_history_latency_ms", 0.0)
        result.setdefault("rename_confidence", "none")
        result.setdefault("split_recommended", False)
        result.setdefault("scoped_history_guidance", None)
        result.setdefault("scoped_history_split_rationale", "")
        result.setdefault("scoped_history_rename_rationale", "")
        result.setdefault("structural_error_handling", False)
        result.setdefault("structural_public_api", False)
        result.setdefault("structural_new_command", False)
        result.setdefault("scoped_history_evidence", None)
        return result

    from git_cg.semantic import empty_graph_product_fields

    # Parser stage — isolated so later producer failures keep parse metrics.
    semantic_parser_metrics: dict | None = None
    staged_files: dict = {}
    parser_batch_results = None  # reused by Phase 9 structural markers (no second parse)
    try:
        from git_cg.ast_parser import parse_files
        from git_cg.git_index import read_staged_sources

        staged = read_staged_sources(repo_root)
        staged_files = dict(staged.files)
        if staged.files:
            batch = parse_files(staged.files)
            parser_batch_results = getattr(batch, "results", None)
            semantic_parser_metrics = batch.metrics.to_dict()
            result["parser_latency_ms"] = float(semantic_parser_metrics.get("parser_latency_ms") or 0.0)
            if staged.skipped:
                semantic_parser_metrics.setdefault("semantic_fallback_reasons", []).extend(
                    f"staged_skip:{s}" for s in staged.skipped[:50]
                )
            if staged.errors:
                semantic_parser_metrics.setdefault("semantic_fallback_reasons", []).extend(
                    f"staged_error:{e}" for e in staged.errors[:50]
                )
            result["semantic_parser_metrics"] = semantic_parser_metrics
        else:
            semantic_parser_metrics = empty_parser_metrics(enabled=True)
            result["semantic_parser_metrics"] = semantic_parser_metrics
            if staged.errors and verbose:
                console.log(f"[yellow]Staged blob read issues: {staged.errors[:3]}[/yellow]")
    except Exception as parser_exc:
        if verbose:
            console.log(f"[yellow]Semantic parser producers failed: {parser_exc}[/yellow]")
        result["semantic_parser_metrics"] = empty_parser_metrics(enabled=False)
        result["parser_latency_ms"] = 0.0
        semantic_parser_metrics = None
        staged_files = {}

    # Fingerprint stage — isolated from parser success and graph failures.
    try:
        from git_cg.fingerprints import compare_fingerprint_sets, empty_fingerprint_metrics
        from git_cg.git_index import read_head_sources

        if staged_files:
            head = read_head_sources(repo_root, paths=list(staged_files.keys()))
            fp_batch = compare_fingerprint_sets(
                baseline_files=head.files,
                staged_files=staged_files,
            )
            fp_metrics = fp_batch.metrics.to_dict()
            result["body_similarity_min"] = fp_metrics.get("body_similarity_min")
            result["body_similarity_avg"] = fp_metrics.get("body_similarity_avg")
            result["fingerprint_files_compared"] = int(fp_metrics.get("fingerprint_files_compared") or 0)
            result["fingerprint_latency_ms"] = float(fp_metrics.get("fingerprint_latency_ms") or 0.0)
            result["fingerprint_class_counts"] = fp_metrics.get("class_counts") or {}
            result["fingerprint_grammar_version"] = str(fp_metrics.get("grammar_version") or "unknown")
            result["fingerprint_markers"] = list(fp_metrics.get("markers") or [])
            if semantic_parser_metrics is not None:
                for reason in (fp_metrics.get("reasons") or [])[:50]:
                    semantic_parser_metrics.setdefault("semantic_fallback_reasons", []).append(f"fingerprint:{reason}")
                if head.errors:
                    semantic_parser_metrics.setdefault("semantic_fallback_reasons", []).extend(
                        f"head_error:{e}" for e in head.errors[:50]
                    )
                if head.skipped:
                    semantic_parser_metrics.setdefault("semantic_fallback_reasons", []).extend(
                        f"head_skip:{s}" for s in head.skipped[:50]
                    )
                result["semantic_parser_metrics"] = semantic_parser_metrics
        else:
            fp_empty = empty_fingerprint_metrics()
            result["fingerprint_grammar_version"] = str(fp_empty.get("grammar_version") or "unknown")
    except Exception as fp_exc:
        if verbose:
            console.log(f"[yellow]Fingerprint compare failed: {fp_exc}[/yellow]")
        result["body_similarity_min"] = None
        result["body_similarity_avg"] = None
        result["fingerprint_files_compared"] = 0
        result["fingerprint_latency_ms"] = 0.0
        result["fingerprint_class_counts"] = None
        result["fingerprint_grammar_version"] = "unknown"
        result["fingerprint_markers"] = None
        # Keep parser metrics already populated.

    # Graph stage — stats/refresh + Phase 7 product queries + Phase 9 Policy B.
    # Failures clear graph fields only; never hard-fail the commit path.
    try:
        from git_cg.git_index import should_refresh_graph
        from git_cg.graph_context import (
            GraphOperationResult,
            GraphOutcome,
            collect_graph_product_bundle,
            collect_graph_telemetry,
            graph_stats,
            refresh_graph,
        )
        from git_cg.scoped_history import (
            ScopedHistoryFallbackReason,
            empty_scoped_history_evidence,
            evaluate_scoped_history,
            extract_file_to_flow_ids,
        )
        from git_cg.semantic import (
            COMMIT_PATH_GRAPH_DETAIL_LEVEL,
            COMMIT_PATH_GRAPH_MAX_DEPTH,
            empty_graph_product_fields,
        )
        from git_cg.telemetry import SemanticRefreshGraph, ShadowFailOpenReason

        result.setdefault("shadow_workspace_used", False)
        result.setdefault("semantic_refresh_graph", SemanticRefreshGraph.SKIPPED.value)
        result.setdefault("shadow_fail_open_reason", ShadowFailOpenReason.NONE.value)
        result.setdefault("scoped_history_fallback_reason", ScopedHistoryFallbackReason.NONE.value)
        result.setdefault("scoped_history_latency_ms", 0.0)
        result.setdefault("rename_confidence", "none")
        result.setdefault("split_recommended", False)
        result.setdefault("scoped_history_guidance", None)
        result.setdefault("scoped_history_evidence", empty_scoped_history_evidence().to_dict())
        # Accumulated only on refresh-on path; folded into graph_build_latency_ms below.
        shadow_clone_sync_latency_ms = 0.0

        build_result = None
        stats_result = None
        query_results: list = []
        changed_files = sorted(staged_files.keys()) if staged_files else []
        result["changed_files"] = list(changed_files)
        # Raw flows payload retained in-process for scoped-history evaluators (not Opik).
        flows_payload_for_evidence: dict | None = None
        policy_b_query_root: str | None = None
        scoped_fallback = ScopedHistoryFallbackReason.NONE.value

        def _cmd_parts(exc: BaseException) -> list[str]:
            cmd = getattr(exc, "cmd", None)
            if isinstance(cmd, (list, tuple)):
                return [str(part) for part in cmd]
            if isinstance(cmd, str):
                return cmd.split()
            return []

        def _append_fallback(reason: str) -> None:
            result["graph_fallback_reasons"] = _merge_graph_fallback_reasons(
                result.get("graph_fallback_reasons"),
                reason,
            )

        def _fail_open_shadow(
            *,
            category: ShadowFailOpenReason,
            vocab1: str,
            error_type: str,
            error: str,
            shadow_used: bool,
        ) -> GraphOperationResult:
            # Fail-open: commit generation must not fail on shadow/refresh errors.
            result["shadow_workspace_used"] = shadow_used
            result["shadow_fail_open_reason"] = category.value
            _append_fallback(vocab1)
            sentry_sdk.set_tag("shadow_fail_open_reason", category.value)
            if verbose:
                console.log(f"[yellow]Shadow workspace refresh failed open: {error_type} ({category.value})[/yellow]")
            return GraphOperationResult(
                ok=False,
                operation="refresh_graph",
                outcome=GraphOutcome.ERROR,
                error_type=error_type,
                error=error[:200],
            )

        def _run_stats_and_product(query_root: str) -> None:
            """Run stats + product bundle against query_root; merge into result."""
            nonlocal stats_result, query_results, flows_payload_for_evidence
            stats_result = graph_stats(repo_root=query_root)
            query_results = [stats_result]
            prior_graph_fallback_reasons = list(result.get("graph_fallback_reasons") or [])
            try:
                product, product_queries = collect_graph_product_bundle(
                    repo_root=query_root,
                    changed_files=changed_files or None,
                    base="HEAD",
                    max_depth=COMMIT_PATH_GRAPH_MAX_DEPTH,
                    detail_level=COMMIT_PATH_GRAPH_DETAIL_LEVEL,
                )
                query_results.extend(product_queries)
                for key, value in product.items():
                    result[key] = value
                result["graph_fallback_reasons"] = _merge_graph_fallback_reasons(
                    prior_graph_fallback_reasons,
                    result.get("graph_fallback_reasons"),
                )
                # Retain bounded raw flows payload for Phase 9 evaluators (in-process only).
                for qr in product_queries:
                    op = getattr(qr, "operation", "") or ""
                    if "flow" in str(op).lower() and getattr(qr, "ok", False):
                        data = getattr(qr, "data", None)
                        if isinstance(data, dict):
                            flows_payload_for_evidence = dict(data)
                            break
                if flows_payload_for_evidence is None:
                    # Fallback: scan any query result with flow-shaped data.
                    for qr in product_queries:
                        data = getattr(qr, "data", None)
                        if isinstance(data, dict) and (
                            "flows" in data or "affected_flows" in data or "file_to_flows" in data
                        ):
                            flows_payload_for_evidence = dict(data)
                            break
            except Exception as product_exc:
                if verbose:
                    console.log(f"[yellow]Semantic graph product bundle failed: {product_exc}[/yellow]")
                for key, value in empty_graph_product_fields().items():
                    result[key] = value
                result["graph_fallback_reasons"] = _merge_graph_fallback_reasons(
                    prior_graph_fallback_reasons,
                    result.get("graph_fallback_reasons"),
                )

        if should_refresh_graph():
            # Phase 7.5 (#180) Policy A + Phase 9 (#163) Policy B:
            # refresh AND stats/product run inside the same index-only shadow `with`
            # when enter ok and refresh ran. Never query shadow.path after exit.
            result["semantic_refresh_graph"] = SemanticRefreshGraph.REQUESTED.value
            from git_cg.shadow_workspace import shadow_workspace

            enter_error: BaseException | None = None
            refresh_error: BaseException | None = None
            import time as _time

            _shadow_t0 = _time.perf_counter()
            try:
                with shadow_workspace(repo_root, include_unstaged=False) as shadow:
                    shadow_clone_sync_latency_ms = float(getattr(shadow, "clone_sync_latency_ms", 0.0) or 0.0)
                    if shadow_clone_sync_latency_ms <= 0.0:
                        # Fallback for test fakes that omit the attribute.
                        shadow_clone_sync_latency_ms = round((_time.perf_counter() - _shadow_t0) * 1000.0, 3)
                    # Enter succeeded (clone + staged sync). Refresh is a separate fail-open stage.
                    try:
                        build_result = refresh_graph(repo_root=shadow.path, full_rebuild=False, postprocess="minimal")
                    except Exception as refresh_exc:
                        refresh_error = refresh_exc
                        build_result = None

                    refresh_ran = (
                        refresh_error is None and build_result is not None and bool(getattr(build_result, "ok", False))
                    )
                    if refresh_ran:
                        # Policy B: stats + product against shadow.path WHILE context is active.
                        result["shadow_workspace_used"] = True
                        result["semantic_refresh_graph"] = SemanticRefreshGraph.RAN.value
                        policy_b_query_root = shadow.path
                        sentry_sdk.add_breadcrumb(category="lifecycle", message="shadow_workspace: used")
                        _run_stats_and_product(shadow.path)
                    # On refresh failure, do not claim staged-truth product inside shadow.
                    # Live-root queries run after the with-block (fail-open).
            except Exception as shadow_exc:
                enter_error = shadow_exc
                # Enter failed before we could read workspace.clone_sync_latency_ms.
                if shadow_clone_sync_latency_ms <= 0.0:
                    shadow_clone_sync_latency_ms = round((_time.perf_counter() - _shadow_t0) * 1000.0, 3)

            if enter_error is not None:
                parts = _cmd_parts(enter_error)
                if isinstance(enter_error, subprocess.CalledProcessError) and (
                    "apply" in parts or ("diff" in parts and "--cached" in parts)
                ):
                    build_result = _fail_open_shadow(
                        category=ShadowFailOpenReason.SHADOW_SYNC_STAGED,
                        vocab1="shadow_sync:staged",
                        error_type=type(enter_error).__name__,
                        error=str(enter_error),
                        shadow_used=False,
                    )
                else:
                    build_result = _fail_open_shadow(
                        category=ShadowFailOpenReason.SHADOW_CREATE_FAILED,
                        vocab1=f"shadow_workspace:{type(enter_error).__name__}",
                        error_type=type(enter_error).__name__,
                        error=str(enter_error),
                        shadow_used=False,
                    )
                scoped_fallback = ScopedHistoryFallbackReason.SHADOW_UNAVAILABLE.value
            elif refresh_error is not None:
                if isinstance(refresh_error, TimeoutError):
                    category = ShadowFailOpenReason.REFRESH_TIMEOUT
                else:
                    category = ShadowFailOpenReason.REFRESH_FAILED
                build_result = _fail_open_shadow(
                    category=category,
                    vocab1=f"refresh_graph:{type(refresh_error).__name__}",
                    error_type=type(refresh_error).__name__,
                    error=str(refresh_error),
                    shadow_used=True,
                )
                scoped_fallback = ScopedHistoryFallbackReason.GRAPH_UNAVAILABLE.value
            elif build_result is not None and not build_result.ok:
                # refresh_graph returned a failed result without raising.
                err_type = str(build_result.error_type or "failed")
                build_result = _fail_open_shadow(
                    category=ShadowFailOpenReason.REFRESH_FAILED,
                    vocab1=f"refresh_graph:{err_type}",
                    error_type=err_type,
                    error=str(build_result.error or "refresh_graph failed"),
                    shadow_used=True,
                )
                scoped_fallback = ScopedHistoryFallbackReason.GRAPH_UNAVAILABLE.value

            # Fail-open / non-Policy-B: query live root (never a destroyed shadow path).
            if policy_b_query_root is None:
                _run_stats_and_product(repo_root)
        else:
            sentry_sdk.add_breadcrumb(category="lifecycle", message="shadow_workspace: skipped")
            _run_stats_and_product(repo_root)

        graph_meta = collect_graph_telemetry(
            build_result=build_result,
            query_results=query_results,
        )
        build_ms = float(graph_meta.get("graph_build_latency_ms") or 0.0)
        # Phase 7.5 (#180): accumulate shadow clone/sync into existing graph_build_latency_ms.
        result["graph_build_latency_ms"] = round(build_ms + float(shadow_clone_sync_latency_ms or 0.0), 3)
        # Product query latency accumulates into existing graph_query_latency_ms.
        result["graph_query_latency_ms"] = float(graph_meta.get("graph_query_latency_ms") or 0.0)
        if stats_result is not None and stats_result.ok:
            maybe_schema = stats_result.data.get("schema_version") or stats_result.data.get("graph_schema_version")
            if maybe_schema is not None:
                result["crg_schema_version"] = str(maybe_schema)
        elif stats_result is not None and verbose:
            console.log(
                f"[yellow]Semantic graph_stats unavailable: {stats_result.error_type}: {stats_result.error}[/yellow]"
            )

        # --- Phase 9 scoped-history producers (advisory; gated; fail-open) ---
        sentry_sdk.add_breadcrumb(category="lifecycle", message="scoped_history: entered")
        try:
            file_to_flow_ids = extract_file_to_flow_ids(
                flows_payload_for_evidence,
                staged_files=changed_files,
            )
            # Cross-path rename bytes: HEAD old path + staged new path.
            renamed_paths: list[tuple[str, str]] = []
            old_bytes: dict[str, bytes] = {}
            new_bytes: dict[str, bytes] = {}
            try:
                from git_cg.git_index import read_head_sources

                new_bytes = dict(staged_files)
                # Rename pairs are not populated on the metrics dict today; discover
                # staged renames via cached name-status (no worktree mutation).
                try:
                    import subprocess as _sp

                    # NUL-delimited records avoid tab/newline path-splitting hazards.
                    status = _sp.check_output(
                        [
                            "git",
                            "-C",
                            repo_root,
                            "diff",
                            "--cached",
                            "--name-status",
                            "-z",
                            "-M",
                        ],
                        timeout=5,
                    )
                    fields = status.split(b"\0")
                    idx = 0
                    while idx < len(fields) and len(renamed_paths) < 32:
                        raw_status = fields[idx]
                        if not raw_status:
                            idx += 1
                            continue
                        status_token = raw_status.decode("utf-8", errors="replace")
                        if status_token.startswith("R") and idx + 2 < len(fields):
                            old_path = fields[idx + 1].decode("utf-8", errors="replace").strip()
                            new_path = fields[idx + 2].decode("utf-8", errors="replace").strip()
                            if old_path and new_path:
                                renamed_paths.append((old_path, new_path))
                            idx += 3
                            continue
                        # Non-rename: status + path (+ optional unused fields)
                        idx += 2 if idx + 1 < len(fields) else 1
                except Exception:
                    pass
                if renamed_paths:
                    head = read_head_sources(repo_root, paths=[old for old, _ in renamed_paths])
                    old_bytes = dict(head.files)
            except Exception:
                renamed_paths = []
                old_bytes = {}
                new_bytes = dict(staged_files)

            # Empty flow map is not an error; the graph product may simply have no flows.
            # preflight_groups_count is carry-through from the commit path (Phase 0.5 product
            # owns grouping; default 0 keeps behaviour identical until preflight runs).
            try:
                pf_groups = int(preflight_groups_count or 0)
            except TypeError, ValueError:
                pf_groups = 0
            if pf_groups < 0:
                pf_groups = 0
            evidence = evaluate_scoped_history(
                enable_semantic=True,
                file_to_flow_ids=file_to_flow_ids,
                staged_files=changed_files,
                renamed_paths=renamed_paths,
                old_bytes_by_path=old_bytes,
                new_bytes_by_path=new_bytes,
                staged_sources=staged_files,
                parse_results=parser_batch_results,
                preflight_groups_count=pf_groups,
                fallback_reason=scoped_fallback,
            )
            evidence_dict = evidence.to_dict()
            # Strip in-process-only map before any telemetry-facing copy.
            result["scoped_history_evidence"] = {k: v for k, v in evidence_dict.items() if k != "file_to_flow_ids"}
            # Keep flow map only on a private key for the post-enforce merge (in-process).
            result["_scoped_history_file_to_flow_ids"] = evidence.file_to_flow_ids
            result["scoped_history_fallback_reason"] = evidence.fallback_reason
            result["scoped_history_latency_ms"] = float(evidence.latency_ms or 0.0)
            result["rename_confidence"] = evidence.rename_confidence
            result["split_recommended"] = bool(evidence.split_high_confidence)
            result["scoped_history_guidance"] = evidence.guidance
            result["scoped_history_split_rationale"] = evidence.split_rationale
            result["scoped_history_rename_rationale"] = evidence.rename_rationale
            result["structural_error_handling"] = bool(evidence.structural_error_handling)
            result["structural_public_api"] = bool(evidence.structural_public_api)
            result["structural_new_command"] = bool(evidence.structural_new_command)
            # P1/P2: fold structural closed-vocab markers into enrichment channel.
            # Additive only; never mutates DiffSignals. Semantic-off path untouched.
            structural_markers: list[str] = []
            if evidence.structural_error_handling:
                structural_markers.extend(["exception_handling_added", "error_handling_improved", "try_except_added"])
            if evidence.structural_public_api:
                structural_markers.extend(["new_api", "new_user_facing_capability", "functional_code_changed"])
            if evidence.structural_new_command:
                structural_markers.append("new_command")
            if structural_markers:
                existing = list(result.get("fingerprint_markers") or [])
                for marker in structural_markers:
                    if marker not in existing:
                        existing.append(marker)
                result["fingerprint_markers"] = existing
        except Exception as scoped_exc:
            if verbose:
                console.log(f"[yellow]Scoped-history producers failed open: {scoped_exc}[/yellow]")
            result["scoped_history_fallback_reason"] = ScopedHistoryFallbackReason.ERROR.value
            with contextlib.suppress(Exception):
                # Closed enum — coerced vocabulary only; never through the free-text gateway.
                sentry_sdk.set_tag(
                    "scoped_history_fallback_reason",
                    ScopedHistoryFallbackReason.ERROR.value,
                )
    except Exception as graph_exc:
        if verbose:
            console.log(f"[yellow]Semantic graph producers failed: {graph_exc}[/yellow]")
        # Reset only graph build/query latency + schema. Do not wipe product fields
        # already merged by collect_graph_product_bundle / inner product_exc fallback.
        result["graph_build_latency_ms"] = 0.0
        result["graph_query_latency_ms"] = 0.0
        result["crg_schema_version"] = None

        result["graph_fallback_reasons"] = _merge_graph_fallback_reasons(
            result.get("graph_fallback_reasons"),
            f"graph_stage:{type(graph_exc).__name__}",
        )
        # Override the pre-populated "none" default — setdefault would mask the error.
        # Use literals here: ScopedHistoryFallbackReason may be unbound if graph imports failed.
        current_fb = result.get("scoped_history_fallback_reason")
        if current_fb in (None, "", "none"):
            result["scoped_history_fallback_reason"] = "error"
    return result


@opik.track(project_name="gitCommitGenerator")
def _run_commit_generation(
    commit_msg_file: str,
    commit_source: str | None,
    extra_args: list[str] | None,
    *,
    engine: str,
    dry_run: bool,
    verbose: bool,
    amend_regenerate: bool,
    strict: bool,
    interactive: bool,
    gui_editor: bool = False,
    enable_semantic: bool | None = None,
    gold_strict: bool = False,
    rank_arbitrate: bool | None = None,
    blueprint: str | None = None,
) -> bool:
    """
    Generate a commit message from the staged diff, optionally review it, and record telemetry.

    Parameters:
        commit_msg_file (str): Path to the commit message file to write.
        commit_source (str | None): Source of the commit request, used to determine whether generation should proceed.
        extra_args (list[str] | None): Additional command-line arguments preserved for compatibility.
        engine (str): AI engine key to use.
        dry_run (bool): Preview the generated message without applying it.
        verbose (bool): Enable detailed console output.
        amend_regenerate (bool): Allow regeneration for an otherwise skipped commit source.
        strict (bool): Use non-zero exit codes when aborting.
        interactive (bool): Present the interactive review flow when a TTY is available.
        gui_editor (bool): Prefer the GUI editor for edit actions.
        enable_semantic (bool | None): Enable or disable semantic processing, or use its configured default.
        gold_strict (bool): Resolve gold lint to strict mode without affecting non-gold strictness.
        rank_arbitrate (bool | None): Enable or disable Low-confidence intent arbitration, or use env/default.
        blueprint (str | None): Optional presentation CommitBlueprint as inline JSON or ``@path.json``.

    Returns:
        bool: `True` when generation completes successfully.
    """
    if verbose:
        console.log("Starting git-cg...")
        console.log(f"Engine: {engine}")
        console.log(f"Commit Msg File: {commit_msg_file}")
        console.log(f"Commit Source: {commit_source}")
        console.log(f"Interactive Mode: {interactive}")

    # F80 / P-S12-9: message-only rebuilds must not re-enter generation via
    # prepare-commit-msg. --no-verify alone is insufficient when hooks still run
    # under hk/global hook paths; operators set GIT_CG_SKIP_PREPARE=1 instead.
    if _is_skip_prepare_enabled():
        if verbose:
            console.log("GIT_CG_SKIP_PREPARE enabled; skipping prepare-commit-msg generation.")
        raise typer.Exit(code=0)

    sentry_sdk.add_breadcrumb(category="lifecycle", message="Starting git-cg execution")

    commit_source = _validate_commit_source(commit_source, commit_msg_file, amend_regenerate, verbose)

    try:
        repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        repo_name = os.path.basename(repo_root)
    except Exception:
        repo_root = "."
        repo_name = "unknown"

    # Phase 14: Tag Sentry events with the code-review-graph schema version
    # so signal regressions can be correlated with CRG upgrades.
    crg_schema_version = "unknown"
    try:
        from code_review_graph.tools import list_graph_stats

        crg_stats = list_graph_stats(repo_root=repo_root)
        crg_schema_version = str(crg_stats.get("schema_version", "unknown"))
    except Exception:
        # CRG graph may not be built yet for this repo; keep fallback.
        crg_schema_version = "unknown"
    sentry_sdk.set_tag("crg_schema_version", crg_schema_version)

    # Phase 1/2/7: semantic producers (parser, fingerprints, graph product bundle).
    # Flag-on may enrich closed-vocab ranking markers and attach SemanticDiffSummary context.
    # Prompt MVP ships no summary evidence block (Phase 11 owns packing).
    # Phase 0.5 preflight product is not built here. Carry-through only: when a
    # future grouping product (or test injection) sets groups >1, scoped-history
    # elevates split confidence. Defaults keep today's skipped behaviour.
    preflight_mode = "skipped"
    preflight_groups_count = 0
    preflight_fallback_reason = ""
    semantic_metrics = _collect_semantic_producer_metrics(
        repo_root,
        enable_semantic=enable_semantic,
        verbose=verbose,
        preflight_groups_count=preflight_groups_count,
    )
    semantic_enabled = bool(semantic_metrics["semantic_enabled"])
    parser_latency_ms = float(semantic_metrics["parser_latency_ms"] or 0.0)
    graph_build_latency_ms = float(semantic_metrics["graph_build_latency_ms"] or 0.0)
    graph_query_latency_ms = float(semantic_metrics["graph_query_latency_ms"] or 0.0)
    semantic_parser_metrics = semantic_metrics["semantic_parser_metrics"]
    body_similarity_min = semantic_metrics["body_similarity_min"]
    body_similarity_avg = semantic_metrics["body_similarity_avg"]
    fingerprint_files_compared = int(semantic_metrics["fingerprint_files_compared"] or 0)
    fingerprint_latency_ms = float(semantic_metrics["fingerprint_latency_ms"] or 0.0)
    fingerprint_class_counts = semantic_metrics["fingerprint_class_counts"]
    fingerprint_grammar_version = str(semantic_metrics["fingerprint_grammar_version"] or "unknown")
    fingerprint_markers = semantic_metrics["fingerprint_markers"]
    blast_radius_size = semantic_metrics.get("blast_radius_size")
    affected_flows_count = semantic_metrics.get("affected_flows_count")
    test_coverage_gap = semantic_metrics.get("test_coverage_gap")
    test_gaps_count = semantic_metrics.get("test_gaps_count")
    graph_enrichment = semantic_metrics.get("graph_enrichment")
    risk_assessment = semantic_metrics.get("risk_assessment")
    if semantic_metrics.get("crg_schema_version"):
        crg_schema_version = str(semantic_metrics["crg_schema_version"])
        sentry_sdk.set_tag("crg_schema_version", crg_schema_version)
    # Phase 7.5 (#180): shadow isolation state.
    shadow_workspace_used = bool(semantic_metrics.get("shadow_workspace_used", False))
    semantic_refresh_graph = str(semantic_metrics.get("semantic_refresh_graph", "skipped"))
    shadow_fail_open_reason = str(semantic_metrics.get("shadow_fail_open_reason", "none"))
    # Phase 9 scoped-history (Issue #163) — advisory only; default-off via semantic gate.
    scoped_history_fallback_reason = str(semantic_metrics.get("scoped_history_fallback_reason") or "none")
    scoped_history_latency_ms = float(semantic_metrics.get("scoped_history_latency_ms") or 0.0)
    rename_confidence = str(semantic_metrics.get("rename_confidence") or "none")
    scoped_history_split_high_confidence = bool(semantic_metrics.get("split_recommended") or False)
    scoped_history_guidance = semantic_metrics.get("scoped_history_guidance")
    if not isinstance(scoped_history_guidance, str):
        scoped_history_guidance = None
    scoped_history_split_rationale = str(semantic_metrics.get("scoped_history_split_rationale") or "")
    scoped_history_rename_rationale = str(semantic_metrics.get("scoped_history_rename_rationale") or "")
    structural_error_handling = bool(semantic_metrics.get("structural_error_handling") or False)
    structural_public_api = bool(semantic_metrics.get("structural_public_api") or False)
    structural_new_command = bool(semantic_metrics.get("structural_new_command") or False)
    scoped_history_evidence = semantic_metrics.get("scoped_history_evidence")
    if not isinstance(scoped_history_evidence, dict):
        scoped_history_evidence = None
    # Closed-vocab Sentry tags only (no free-text rationales / paths).
    with contextlib.suppress(Exception):
        sentry_sdk.set_tag("scoped_history_fallback_reason", scoped_history_fallback_reason)
        sentry_sdk.set_tag("rename_confidence", rename_confidence)
        sentry_sdk.set_tag(
            "scoped_history_split_high_confidence",
            "true" if scoped_history_split_high_confidence else "false",
        )

    opik_metadata = {
        "repo_name": repo_name,
        "commit_source": commit_source,
        "semantic_enabled": semantic_enabled,
        "parser_latency_ms": parser_latency_ms,
        "graph_build_latency_ms": graph_build_latency_ms,
        "graph_query_latency_ms": graph_query_latency_ms,
        "body_similarity_min": body_similarity_min,
        "body_similarity_avg": body_similarity_avg,
        "fingerprint_files_compared": fingerprint_files_compared,
        "fingerprint_latency_ms": fingerprint_latency_ms,
        "fingerprint_class_counts": fingerprint_class_counts,
        "fingerprint_grammar_version": fingerprint_grammar_version,
        "fingerprint_markers": fingerprint_markers,
        # Phase 3 preflight hooks (default skipped until Phase 0.5 grouping product).
        "preflight_mode": preflight_mode,
        "preflight_groups_count": preflight_groups_count,
        "preflight_fallback_reason": preflight_fallback_reason,
        # Phase 7 semantic context product metrics (Issue #162).
        "blast_radius_size": blast_radius_size,
        "affected_flows_count": affected_flows_count,
        "test_coverage_gap": test_coverage_gap,
        "test_gaps_count": test_gaps_count,
        "semantic_context_schema_version": "",
        "semantic_context_fallback_reasons": None,
        # Phase 7.5 (#180): shadow isolation.
        "shadow_workspace_used": shadow_workspace_used,
        "semantic_refresh_graph": semantic_refresh_graph,
        "shadow_fail_open_reason": shadow_fail_open_reason,
        # Phase 9 scoped-history (Issue #163) — allowlisted non-content only.
        "scoped_history_fallback_reason": scoped_history_fallback_reason,
        "scoped_history_latency_ms": scoped_history_latency_ms,
        "rename_confidence": rename_confidence,
        "scoped_history_split_high_confidence": scoped_history_split_high_confidence,
        "structural_error_handling": structural_error_handling,
        "structural_public_api": structural_public_api,
        "structural_new_command": structural_new_command,
    }
    if semantic_parser_metrics:
        # Flatten non-content parser metrics into the trace metadata.
        # Redact path/error-bearing fallback reasons before Opik (same gateway as state write).
        from git_cg.telemetry import redact_payload

        metrics_for_opik = dict(semantic_parser_metrics)
        reasons = metrics_for_opik.get("semantic_fallback_reasons")
        if isinstance(reasons, list):
            redacted_reasons: list[str] = []
            for reason in reasons:
                if not isinstance(reason, str):
                    continue
                redacted = redact_payload(reason)
                if redacted == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]":
                    redacted_reasons.append("[REDACTED]")
                else:
                    redacted_reasons.append(redacted)
            metrics_for_opik["semantic_fallback_reasons"] = redacted_reasons

        for key in (
            "semantic_parser_enabled",
            "semantic_parser_mode",
            "semantic_languages_requested",
            "semantic_languages_parsed",
            "semantic_files_total",
            "semantic_files_parsed",
            "semantic_files_failed",
            "semantic_fallback_reasons",
            "semantic_summary_hash",
            "semantic_summary_chars",
        ):
            if key in metrics_for_opik:
                opik_metadata[key] = metrics_for_opik[key]
        opik_metadata["parser_latency_ms"] = metrics_for_opik.get("parser_latency_ms", parser_latency_ms)

    opik_context.update_current_trace(
        tags=["interactive" if interactive else "non-interactive", engine],
        metadata=opik_metadata,
    )

    global LAST_OPIK_TRACE_ID
    trace_data = opik_context.get_current_trace_data()
    LAST_OPIK_TRACE_ID = trace_data.id if trace_data else None

    analysis_diff = extract_git_diff(verbose=verbose, strict=strict)
    prompt_diff, omitted_prompt_paths = pack_prompt_diff(analysis_diff)
    if omitted_prompt_paths and verbose:
        console.log(
            f"Prompt diff packed: omitted {len(omitted_prompt_paths)} path(s) from LLM payload "
            f"(analysis/rank still uses full staged diff; Phase 11 owns product packing)."
        )
    sentry_sdk.add_breadcrumb(category="lifecycle", message="Extracted git diff successfully")

    try:
        client = get_ai_client(engine)
    except ValueError as e:
        _abort(f"[bold red]{e}[/bold red]", strict=strict)

    if verbose:
        console.log(f"AI Client initialized. Calling {engine} to generate commit message...")

    sentry_sdk.add_breadcrumb(category="lifecycle", message="AI Client initialized")

    engine_config = ENGINE_REGISTRY.get(engine.lower())
    prefix = engine_config.prefix if engine_config else "OMLX"
    preferred_model = os.environ.get(f"{prefix}_MODEL", os.environ.get("OMLX_MODEL", ""))
    model_name = resolve_model_name(client, preferred=preferred_model, verbose=verbose)

    if verbose:
        console.log(f"Using model: {model_name}")

    issue_references = _detect_branch_issue_reference(verbose)
    regeneration_guidance: str | None = None

    try:
        repo_name = os.path.basename(
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        )
        thread_id = f"repo-{repo_name}"
    except Exception:
        thread_id = "default-thread"

    active_directives: dict[str, str] = {}
    residual_guidance: str | None = None
    review_state: ReviewState | None = None

    enrichment_facts = _build_semantic_enrichment_facts(
        semantic_enabled=semantic_enabled,
        fingerprint_class_counts=fingerprint_class_counts if isinstance(fingerprint_class_counts, dict) else None,
        body_similarity_min=body_similarity_min,
        body_similarity_avg=body_similarity_avg,
        fingerprint_markers=fingerprint_markers if isinstance(fingerprint_markers, list) else None,
        graph_enrichment=graph_enrichment,
    )

    semantic_summary = None
    semantic_context_schema_version = ""
    semantic_context_fallback_reasons = None
    if semantic_enabled:
        from git_cg.semantic import build_semantic_summary, semantic_analysis_metadata

        semantic_summary = build_semantic_summary(semantic_metrics, risk_assessment=risk_assessment)
        summary_meta = semantic_analysis_metadata(semantic_summary)
        semantic_context_schema_version = str(summary_meta.get("semantic_context_schema_version") or "")
        semantic_context_fallback_reasons = summary_meta.get("semantic_context_fallback_reasons")
        opik_metadata.update(summary_meta)
        with contextlib.suppress(Exception):
            opik_context.update_current_trace(metadata=opik_metadata)

    gen_context = _build_generation_context(
        analysis_diff,
        enable_semantic=semantic_enabled,
        enrichment_facts=enrichment_facts,
        semantic_summary=semantic_summary,
        risk_assessment=risk_assessment,
    )

    # Issue #182 / #191: resolve gold mode once per generation entry (flags cannot
    # change mid-loop); gold auto-regen is bounded to 2 attempts with monotonic
    # code-set shrinkage (Option B) and tracked separately from Instructor retries.
    from git_cg.commit_gold import check_commit_gold, resolve_gold_mode
    from git_cg.regeneration import (
        RegenerationState,
        enforce_semantic_contract,
        evaluate_contract_lifecycle,
        lift_plan_to_contract_semver,
        resolve_semantic_contract,
    )
    from git_cg.telemetry import GoldSelfCorrectionOutcome

    gold_mode = resolve_gold_mode(
        strict=strict,
        gold_strict=gold_strict,
        interactive=interactive,
        tty_available=interactive and can_open_tty(),
    )
    gold_report = None
    gold_regen_attempts = 0
    gold_guidance: str | None = None
    gold_previous_primary_id: str | None = None
    gold_previous_codes: frozenset[str] | None = None
    gold_self_correction_outcome = GoldSelfCorrectionOutcome.NOT_NEEDED.value
    gold_split_recommendation = False
    # Issue #195: contract lock + arbitration telemetry (Slices 2-4).
    last_lock_resolution = "absent"
    locked_intent_id: str | None = None
    ranking_choice_path: str | None = None
    ranking_override = False
    ranking_arbitrate_effective: str | None = None
    presentation_fallback_reason: str = "none"
    low_confidence_guidance: str | None = None
    low_confidence_adjustment = None
    # Slice 8 (#204): claim-tag harvest + hallucination/craft guards (shared regen budget).
    harvested_claim_tags: list[str] = []
    hallucination_guard_fired: bool = False
    guard_guidance: str | None = None
    # Slice 5 hotfix (#204): contract-lift telemetry (lift-only SemVer floor).
    contract_lift_applied: bool = False
    contract_lift_from_semver: str | None = None
    # Slice 5.5 (#204): contract lifecycle observability.
    contract_locked_semver: str | None = None
    llm_raw_semver: str | None = None
    plan_persisted_semver: str | None = None
    contract_violation: bool = False
    plan_normaliser_applied: bool = False
    plan_normaliser_reason: str = "none"
    presentation_touched_semver: bool = False
    # Issue #204 Slice 7: operator blueprint (presentation-only).
    blueprint_applied: bool = False
    parsed_blueprint = None  # CommitBlueprint | None — never logged raw
    blueprint_guidance: str | None = None
    # Issue #204 Slice 10 / D26: path-class + antisignal + scope-alias telemetry.
    path_class_gate: str = "none"
    changelog_antisignal_applied: bool = False
    scope_normalised_from: str = "none"
    path_class_gate, changelog_antisignal_applied, scope_normalised_from = _presentation_telemetry_from_context(
        gen_context
    )

    # --- Pre-LLM ranking arbitration (Issue #195) ---------------------------
    # Sole insertion seam: after rank/confidence owner, before contract/LLM.
    from git_cg.ranking_arbitrate_flags import is_rank_arbitrate_enabled

    conf = gen_context.ranking_confidence
    tty_ok = interactive and can_open_tty()
    if conf is None:
        ranking_arbitrate_effective = None
        ranking_choice_path = None
    elif conf.level != "low":
        ranking_arbitrate_effective = "skipped_high_medium"
        ranking_choice_path = "skipped_high_medium"
    elif not is_rank_arbitrate_enabled(rank_arbitrate):
        ranking_arbitrate_effective = "flag_off"
        ranking_choice_path = "ni_top_rank"
    elif not tty_ok:
        ranking_arbitrate_effective = "skipped_ni"
        ranking_choice_path = "ni_top_rank"
    else:
        from git_cg.intent_arbitrate import run_intent_arbitration

        ranking_arbitrate_effective = "menu_shown"
        sentry_sdk.add_breadcrumb(
            category="lifecycle",
            message="arbitrate: low confidence menu",
            level="info",
            data={
                "ranking_confidence_level": conf.level if conf else None,
                "ranking_confidence_margin": conf.margin if conf else None,
            },
        )
        # Guidance REGEN may loop here with a rebuilt gen_context.
        # Presentation-only views (directive-narrowed A/B) must not mutate the
        # authoritative rank-pass snapshot on gen_context.
        arbitrate_presentation_note: str | None = None
        present_pair_ranked = list(gen_context.ranked_intents)
        present_pair_conf = gen_context.ranking_confidence
        while True:
            arb = run_intent_arbitration(
                ranked_intents=present_pair_ranked,
                ranking_confidence=present_pair_conf,
                constraints=gen_context.constraints,
                existing_guidance=regeneration_guidance,
                existing_directives=active_directives,
                existing_residual=residual_guidance,
                presentation_note=arbitrate_presentation_note,
            )
            # Consume one-shot REGEN banner after it has been shown once.
            arbitrate_presentation_note = None
            if arb.aborted or arb.action == "aborted":
                ranking_choice_path = "cancel_abort"
                ranking_override = False
                locked_intent_id = None
                _apply_issue195_sentry_tags(
                    ranking_confidence_level=conf.level if conf else None,
                    ranking_choice_path="cancel_abort",
                    gold_mode=gold_mode,
                )
                # Emit safe telemetry then abort without writing COMMIT_EDITMSG (A_06/A_21).
                _write_telemetry_state_safe(
                    review_state=None,
                    diff_output=analysis_diff,
                    engine=engine,
                    model_name=model_name,
                    system_prompt="",
                    repo_name=repo_name,
                    thread_id=thread_id,
                    verbose=verbose,
                    graph_schema_version=crg_schema_version,
                    semantic_enabled=semantic_enabled,
                    parser_latency_ms=parser_latency_ms,
                    graph_build_latency_ms=graph_build_latency_ms,
                    graph_query_latency_ms=graph_query_latency_ms,
                    semantic_parser_metrics=semantic_parser_metrics,
                    body_similarity_min=body_similarity_min,
                    body_similarity_avg=body_similarity_avg,
                    fingerprint_files_compared=fingerprint_files_compared,
                    fingerprint_latency_ms=fingerprint_latency_ms,
                    fingerprint_class_counts=fingerprint_class_counts,
                    fingerprint_grammar_version=fingerprint_grammar_version,
                    fingerprint_markers=fingerprint_markers,
                    preflight_mode=preflight_mode,
                    preflight_groups_count=preflight_groups_count,
                    preflight_fallback_reason=preflight_fallback_reason,
                    blast_radius_size=blast_radius_size
                    if isinstance(blast_radius_size, int) and not isinstance(blast_radius_size, bool)
                    else None,
                    affected_flows_count=affected_flows_count
                    if isinstance(affected_flows_count, int) and not isinstance(affected_flows_count, bool)
                    else None,
                    test_coverage_gap=bool(test_coverage_gap) if test_coverage_gap is not None else None,
                    test_gaps_count=test_gaps_count
                    if isinstance(test_gaps_count, int) and not isinstance(test_gaps_count, bool)
                    else None,
                    semantic_context_schema_version=semantic_context_schema_version,
                    semantic_context_fallback_reasons=semantic_context_fallback_reasons,
                    shadow_workspace_used=shadow_workspace_used,
                    semantic_refresh_graph=semantic_refresh_graph,
                    shadow_fail_open_reason=shadow_fail_open_reason,
                    ranking_confidence_level=conf.level if conf else None,
                    ranking_confidence_margin=conf.margin if conf else None,
                    ranking_confidence_reasons=list(conf.reasons) if conf else None,
                    ranking_choice_path="cancel_abort",
                    ranking_override=False,
                    ranking_arbitrate_effective="menu_shown",
                    lock_resolution="absent",
                    gold_mode=gold_mode,
                    gold_findings_count=0,
                    gold_finding_codes=None,
                    gold_blocked=False,
                    gold_regen_attempts=0,
                    scoped_history_fallback_reason=scoped_history_fallback_reason,
                    scoped_history_latency_ms=scoped_history_latency_ms,
                    rename_confidence=rename_confidence,
                    scoped_history_split_high_confidence=scoped_history_split_high_confidence,
                    scoped_history_guidance=scoped_history_guidance,
                    scoped_history_split_rationale=scoped_history_split_rationale,
                    scoped_history_rename_rationale=scoped_history_rename_rationale,
                    structural_error_handling=structural_error_handling,
                    structural_public_api=structural_public_api,
                    structural_new_command=structural_new_command,
                    presentation_fallback_reason=presentation_fallback_reason,
                    blueprint_applied=blueprint_applied,
                    hallucination_guard_fired=hallucination_guard_fired,
                    path_class_gate=path_class_gate,
                    changelog_antisignal_applied=changelog_antisignal_applied,
                    scope_normalised_from=scope_normalised_from,
                    contract_lift_applied=contract_lift_applied,
                    contract_lift_from_semver=contract_lift_from_semver,
                    contract_locked_semver=contract_locked_semver,
                    llm_raw_semver=llm_raw_semver,
                    plan_persisted_semver=plan_persisted_semver,
                    contract_violation=contract_violation,
                    plan_normaliser_applied=plan_normaliser_applied,
                    plan_normaliser_reason=plan_normaliser_reason,
                )
                opik.flush_tracker()
                _abort(
                    "\n[bold red]Commit aborted during intent arbitration.[/bold red]",
                    strict=True,  # user Abort must always fail the hook/CLI (never exit 0)
                    report=False,
                )

            if arb.action == "re_rank" and arb.re_rank_requested:
                # Apply mapped directives and rebuild sole rank-pass pair (REGEN).
                if arb.active_directives:
                    active_directives = dict(arb.active_directives)
                if arb.guidance:
                    regeneration_guidance = arb.guidance
                residual_guidance = arb.residual_guidance
                locked_intent_id = None  # guidance REGEN starts with no lock
                gen_context = _build_generation_context(
                    analysis_diff,
                    enable_semantic=semantic_enabled,
                    enrichment_facts=enrichment_facts,
                    semantic_summary=semantic_summary,
                    risk_assessment=risk_assessment,
                )
                path_class_gate, changelog_antisignal_applied, _scope_refresh = _presentation_telemetry_from_context(
                    gen_context
                )
                if _scope_refresh != "none":
                    scope_normalised_from = _scope_refresh
                # Presentation narrowing: preferred_type/scope select among the new
                # authoritative ranked snapshot without mutating SOP weights (G1).
                from git_cg.intent_arbitrate import ranked_intents_for_directives
                from git_cg.ranking_confidence import compute_ranking_confidence

                present_ranked, present_note = ranked_intents_for_directives(
                    gen_context.ranked_intents,
                    active_directives,
                )
                # Identity check is insufficient (helper always returns a new list).
                # Narrow only when the filtered set is a proper subset with hits.
                original_ids = [r.intent_id for r in gen_context.ranked_intents]
                present_ids = [r.intent_id for r in present_ranked]
                narrowed = present_ids != original_ids and bool(present_ranked)
                if narrowed:
                    # Presentation-only: pass narrowed pair to the next MAIN without
                    # mutating gen_context (authoritative rank-pass snapshot).
                    present_pair_ranked = list(present_ranked)
                    present_pair_conf = compute_ranking_confidence(present_ranked)
                    conf = present_pair_conf
                else:
                    present_pair_ranked = list(gen_context.ranked_intents)
                    present_pair_conf = gen_context.ranking_confidence
                    conf = present_pair_conf
                if present_note and verbose:
                    console.print(
                        f"[cyan]Guidance REGEN view:[/cyan] {present_note} ({len(present_ranked)} candidate(s))"
                    )
                if conf is not None and conf.level != "low":
                    ranking_choice_path = "re_rank_auto_continue"
                    ranking_override = False
                    locked_intent_id = None
                    break
                # Still Low → MAIN again with narrowed A/B + explicit still-Low banner.
                from git_cg.intent_arbitrate import format_regen_still_low_note

                preferred_type = (active_directives or {}).get("preferred_type")
                preferred_scope = (active_directives or {}).get("preferred_scope")
                arbitrate_presentation_note = format_regen_still_low_note(
                    preferred_type=preferred_type,
                    preferred_scope=preferred_scope,
                    narrowed=narrowed,
                )
                if verbose:
                    console.print(f"[yellow]{arbitrate_presentation_note}[/yellow]")
                continue

            # locked | continue_top
            locked_intent_id = arb.locked_intent_id
            ranking_choice_path = arb.choice_path
            ranking_override = bool(arb.override)
            if arb.guidance:
                regeneration_guidance = arb.guidance
            if arb.active_directives:
                active_directives = dict(arb.active_directives)
            if arb.residual_guidance is not None or arb.action in {"locked", "continue_top"}:
                residual_guidance = arb.residual_guidance
            break

    # Issue #204 Slice 8 — harvest P9-A##/P9-B## claim tags from staged evidence (D14).
    # Pure text harvest from analysis/prompt diffs + staged test blobs (index, not worktree).
    # Runs before low-confidence stubs so claim tags can seed inventory pressure.
    try:
        from git_cg.commit_quality import harvest_claim_tags
        from git_cg.git_index import read_staged_sources

        _claim_texts: list[str] = [analysis_diff or "", prompt_diff or ""]
        _staged_for_claims = [str(p) for p in (getattr(gen_context.diff_signals, "files", None) or []) if p]
        _test_claim_paths: list[str] = []
        for _cp in _staged_for_claims:
            _low = _cp.replace("\\", "/").lower()
            if (
                "/test" in f"/{_low}"
                or _low.startswith("tests/")
                or _low.endswith("_test.py")
                or _low.endswith("test.py")
            ):
                _test_claim_paths.append(_cp)
        if _test_claim_paths:
            _staged_claim_read = read_staged_sources(
                paths=_test_claim_paths,
                max_file_bytes=256_000,
            )
            for _blob in (_staged_claim_read.files or {}).values():
                if not _blob:
                    continue
                _claim_texts.append(_blob.decode("utf-8", errors="replace")[:200_000])
        harvested_claim_tags = harvest_claim_tags(_claim_texts)
    except Exception:
        harvested_claim_tags = []

    # Issue #204 Slice 5 — low-confidence presentation posture (D7).
    # After ranking confidence + #195 arbitration; before prompt construction.
    # Non-interactive: never blocks. Interactive: does not replace TUI.
    try:
        from git_cg.commit_quality import (
            PRESENTATION_FALLBACK_NONE,
            apply_low_confidence_presentation,
            build_included_change_stubs,
            format_low_confidence_guidance,
        )
        from git_cg.models import TrailerPriors as _TrailerPriors

        _priors = gen_context.scope_priors
        if not isinstance(_priors, _TrailerPriors):
            from git_cg.commit_quality import derive_trailer_priors as _derive_trailer_priors

            _priors = _derive_trailer_priors(
                list(getattr(gen_context.diff_signals, "files", None) or []),
                signals=gen_context.diff_signals,
            )
        _stubs = build_included_change_stubs(
            list(getattr(gen_context.diff_signals, "files", None) or []),
            gen_context.diff_signals,
            gen_context.ranked_intents,
            claim_tags=harvested_claim_tags,
        )
        low_confidence_adjustment = apply_low_confidence_presentation(
            None,
            gen_context.ranking_confidence,
            _priors,
            stubs=_stubs,
        )
        if low_confidence_adjustment.active:
            presentation_fallback_reason = low_confidence_adjustment.fallback_reason
            low_confidence_guidance = format_low_confidence_guidance(low_confidence_adjustment)
        else:
            presentation_fallback_reason = PRESENTATION_FALLBACK_NONE
            low_confidence_guidance = None
    except Exception:
        presentation_fallback_reason = "none"
        low_confidence_guidance = None
        low_confidence_adjustment = None

    # Issue #204 Slice 7 — parse/validate operator blueprint before LLM.
    # Strict standalone CLI (strict=True + TTY): BlueprintError → exit 2.
    # Hook / non-TTY: fall closed to deterministic priors; never block commit.
    if blueprint:
        from git_cg.commit_quality import (
            BlueprintError,
            constraints_from_paths,
            format_blueprint_guidance,
            parse_commit_blueprint,
            semver_presentation_ceiling,
            validate_blueprint_against_constraints,
        )

        try:
            # Prefer the already-resolved repo root from generation setup.
            repo_root_for_bp = repo_root if repo_root not in (None, "") else None
            if repo_root_for_bp is None:
                try:
                    repo_root_for_bp = subprocess.check_output(
                        ["git", "rev-parse", "--show-toplevel"], text=True
                    ).strip()
                except Exception:
                    repo_root_for_bp = None
            parsed_blueprint = parse_commit_blueprint(
                blueprint,
                repo_root=repo_root_for_bp,
                cwd=os.getcwd(),
            )
            staged_for_bp = list(getattr(gen_context.diff_signals, "files", None) or [])
            bp_constraints = getattr(gen_context, "presentation_constraints", None)
            if bp_constraints is None:
                bp_constraints = constraints_from_paths(staged_for_bp, signals=gen_context.diff_signals)
            bp_ceiling = semver_presentation_ceiling(staged_for_bp, gen_context.diff_signals)
            validate_blueprint_against_constraints(parsed_blueprint, bp_constraints, ceiling=bp_ceiling)
            blueprint_guidance = format_blueprint_guidance(parsed_blueprint)
        except BlueprintError as bp_exc:
            kind = getattr(bp_exc, "kind", "blueprint") or "blueprint"
            # Never include raw blueprint payload in the operator message.
            safe_msg = str(bp_exc).split(":")[0][:120]
            # Standalone interactive CLI hard-fails; hooks must not block.
            hard_fail = bool(strict) and bool(tty_ok)
            if hard_fail:
                console.print(f"[bold red]Blueprint rejected:[/bold red] {safe_msg}")
                raise typer.Exit(code=2) from bp_exc
            presentation_fallback_reason = "error" if kind == "error" else "blueprint"
            parsed_blueprint = None
            blueprint_guidance = None
            blueprint_applied = False
            # Operator explicitly passed --blueprint: always surface the safe
            # rejection notice (hooks still fall open and do not hard-fail).
            console.print(f"[yellow]Blueprint ignored ({presentation_fallback_reason}): {safe_msg}[/yellow]")
        except Exception as bp_exc:
            hard_fail = bool(strict) and bool(tty_ok)
            safe_msg = type(bp_exc).__name__
            if hard_fail:
                console.print(f"[bold red]Blueprint rejected:[/bold red] {safe_msg}")
                raise typer.Exit(code=2) from bp_exc
            presentation_fallback_reason = "error"
            parsed_blueprint = None
            blueprint_guidance = None
            blueprint_applied = False
            console.print(f"[yellow]Blueprint ignored (error): {safe_msg}[/yellow]")

    while True:
        regen_state = RegenerationState(
            previous_plan=review_state.commit_plan if review_state else None,
            active_directives=active_directives,
            residual_guidance=residual_guidance,
            locked_intent_id=locked_intent_id,
        )
        contract = resolve_semantic_contract(gen_context, regen_state)
        last_lock_resolution = getattr(contract, "lock_resolution", "absent")
        if last_lock_resolution in {"rejected_not_allowed", "rejected_hard_veto"} and (verbose or interactive):
            # Safe UX notice only — closed code, no matrix dump / free text (Issue #195).
            reason = (
                "not in the allowed intent set"
                if last_lock_resolution == "rejected_not_allowed"
                else "hard-vetoed or otherwise ineligible"
            )
            console.print(
                f"[yellow]Intent lock not applied ({last_lock_resolution}): "
                f"requested lock was {reason}; falling through to normal contract precedence.[/yellow]"
            )

        # Slice 7: fold blueprint presentation pressure into the existing guidance
        # channel (no raw JSON). Path-class envelope still wins post-LLM.
        _presentation_guidance = low_confidence_guidance
        if blueprint_guidance:
            if _presentation_guidance:
                _presentation_guidance = f"{blueprint_guidance}\n\n{_presentation_guidance}"
            else:
                _presentation_guidance = blueprint_guidance
        # Slice 8: fold guard findings into presentation guidance on shared regen.
        # When Context:/Changes: is already banned by guards, do not re-append the
        # low-confidence skeleton block (even Hybrid-safe) ahead of the repair order —
        # guard findings must be the dominant wording pressure on retry.
        if guard_guidance:
            if "GUARD_CONTEXT_CHANGES_TEMPLATE" in guard_guidance:
                _presentation_guidance = guard_guidance
            elif _presentation_guidance:
                _presentation_guidance = f"{guard_guidance}\n\n{_presentation_guidance}"
            else:
                _presentation_guidance = guard_guidance
        system_prompt = build_system_prompt(
            analysis_diff,
            verbose,
            active_directives=active_directives,
            residual_guidance=residual_guidance,
            previous_plan=review_state.commit_plan if review_state else None,
            ranked_candidates=gen_context.ranked_intents,
            contract=contract,
            gold_guidance=gold_guidance,
            scoped_history_guidance=scoped_history_guidance,
            staged_paths=list(getattr(gen_context.diff_signals, "files", None) or []),
            concern_tags=None,
            claim_tags=harvested_claim_tags,
            low_confidence_guidance=_presentation_guidance,
        )

        # Offline prompt tracking (synced asynchronously via script)
        system_prompt_hash = compute_prompt_hash(system_prompt)
        opik_args = {
            "trace": {
                "thread_id": thread_id,
                "tags": ["git-cg", f"engine:{engine}", f"repo:{repo_name}", f"prompt_hash:{system_prompt_hash}"],
            }
        }

        try:
            with console.status(
                f"[bold cyan]Generating AI commit message with {model_name}... (this may take 30-90s locally)[/bold cyan]",
                spinner="dots",
            ):
                commit_plan = generate_commit_message(
                    client,
                    prompt_diff,
                    model_name,
                    system_prompt,
                    active_directives=active_directives,
                    residual_guidance=residual_guidance,
                    opik_args=opik_args,
                )
        except Exception as e:
            with sentry_sdk.new_scope() as scope:
                scope.set_tag("engine", engine)
                scope.set_tag("model_name", model_name)
                if conf is not None:
                    scope.set_tag("ranking_confidence_level", conf.level)
                if ranking_choice_path:
                    scope.set_tag("ranking_choice_path", ranking_choice_path)
                scope.set_tag("gold_mode", str(gold_mode or "off"))
                scope.set_context(
                    "git_cg",
                    {
                        "diff_size": len(analysis_diff),
                        "prompt_diff_size": len(prompt_diff),
                        "prompt_omitted_path_count": len(omitted_prompt_paths),
                    },
                )
                _abort(f"[bold red]Error generating commit message from AI:[/bold red] {e}", strict=strict)

        # Slice 5.5: capture raw LLM SemVer before contract enforcement / presentation.
        try:
            _raw = getattr(commit_plan.primary_intent, "semver_impact", None)
            llm_raw_semver = (
                str(_raw.value).upper()
                if hasattr(_raw, "value")
                else (str(_raw).strip().upper() if _raw is not None else None)
            )
            if llm_raw_semver not in {"NONE", "PATCH", "MINOR", "MAJOR"}:
                llm_raw_semver = None
        except Exception:
            llm_raw_semver = None
        try:
            contract_locked_semver = str(getattr(contract, "semver_impact", "") or "").upper() or None
            if contract_locked_semver not in {"NONE", "PATCH", "MINOR", "MAJOR"}:
                contract_locked_semver = None
        except Exception:
            contract_locked_semver = None

        # Always enforce the pre-resolved SOP contract after model render.
        commit_plan = enforce_semantic_contract(commit_plan, contract, active_directives)
        # Issue #204: presentation overlay (path-class / SemVer ceiling / type
        # dominance / changelog allowlist). Never mutates ranked intent_id/gitmoji.
        presentation_overlay_applied = False
        try:
            from git_cg.commit_quality import apply_presentation_overlay

            staged_paths = list(getattr(gen_context.diff_signals, "files", None) or [])
            # Slice 5: seed presentation from TrailerPriors under low confidence first
            # (identity-preserving). Path-class overlay runs after so D11 envelope wins
            # over low-confidence priors when they disagree (locked precedence).
            if low_confidence_adjustment is not None and getattr(low_confidence_adjustment, "active", False):
                from git_cg.commit_quality import (
                    apply_low_confidence_presentation,
                    apply_presentation_seed,
                    derive_trailer_priors,
                )
                from git_cg.models import TrailerPriors

                seed_priors = gen_context.scope_priors
                if not isinstance(seed_priors, TrailerPriors):
                    seed_priors = derive_trailer_priors(
                        staged_paths,
                        signals=gen_context.diff_signals,
                    )
                seeded = apply_low_confidence_presentation(
                    commit_plan,
                    gen_context.ranking_confidence,
                    seed_priors,
                )
                commit_plan = apply_presentation_seed(commit_plan, seeded)
                if seeded.active:
                    presentation_fallback_reason = seeded.fallback_reason
                    presentation_touched_semver = True
            # Slice 7: apply legal blueprint overlay before path-class envelope so
            # path-class / ceilings retain precedence (Approval locks §I).
            if parsed_blueprint is not None:
                from git_cg.commit_quality import (
                    BlueprintError as _BlueprintError,
                    apply_blueprint,
                    constraints_from_paths as _constraints_from_paths,
                    semver_presentation_ceiling as _ceiling_fn,
                )

                try:
                    _bp_cons = gen_context.presentation_constraints
                    if _bp_cons is None:
                        _bp_cons = _constraints_from_paths(staged_paths, signals=gen_context.diff_signals)
                    _bp_ceil = _ceiling_fn(staged_paths, gen_context.diff_signals)
                    _bp_state = apply_blueprint(
                        commit_plan,
                        parsed_blueprint,
                        _bp_cons,
                        ceiling=_bp_ceil,
                        paths=staged_paths,
                        signals=gen_context.diff_signals,
                    )
                    commit_plan = _bp_state.plan
                    blueprint_applied = bool(_bp_state.blueprint_applied)
                    presentation_touched_semver = True
                except _BlueprintError as _bp_apply_exc:
                    kind = getattr(_bp_apply_exc, "kind", "blueprint") or "blueprint"
                    hard_fail = bool(strict) and bool(tty_ok)
                    if hard_fail:
                        safe_msg = str(_bp_apply_exc).split(":")[0][:120]
                        console.print(f"[bold red]Blueprint rejected:[/bold red] {safe_msg}")
                        raise typer.Exit(code=2) from _bp_apply_exc
                    presentation_fallback_reason = "error" if kind == "error" else "blueprint"
                    blueprint_applied = False
                    console.print(f"[yellow]Blueprint apply skipped ({presentation_fallback_reason})[/yellow]")
                except Exception as _bp_apply_exc:
                    hard_fail = bool(strict) and bool(tty_ok)
                    if hard_fail:
                        console.print(f"[bold red]Blueprint rejected:[/bold red] {type(_bp_apply_exc).__name__}")
                        raise typer.Exit(code=2) from _bp_apply_exc
                    presentation_fallback_reason = "error"
                    blueprint_applied = False
                    console.print("[yellow]Blueprint apply skipped (error)[/yellow]")
            commit_plan = apply_presentation_overlay(
                commit_plan,
                paths=staged_paths,
                signals=gen_context.diff_signals,
                priors=gen_context.scope_priors,
                constraints=gen_context.presentation_constraints,
                active_directives=active_directives,
            )
            presentation_overlay_applied = True
            presentation_touched_semver = True
        except typer.Exit:
            # Controlled aborts from blueprint hard-fail must propagate.
            raise
        except Exception as overlay_exc:
            # Presentation overlay must not brick commit generation, but do not
            # silently swallow unexpected failures without a breadcrumb.
            if verbose:
                console.log(
                    f"[yellow]Presentation overlay skipped ({type(overlay_exc).__name__}: {overlay_exc})[/yellow]"
                )
        # Slice 5 hotfix (#204): presentation seed/overlay must never demote the
        # locked SOP contract SemVer. Lift-only — never raise inside the hook path.
        # enforce_semantic_contract runs *before* presentation; this re-asserts the
        # contract as a hard lower bound after any ceiling/seed clamp.
        try:
            commit_plan, contract_lift_applied, contract_lift_from_semver = lift_plan_to_contract_semver(
                commit_plan, contract
            )
            if contract_lift_applied and verbose:
                console.log(
                    f"[yellow]Contract lift: primary.semver_impact "
                    f"{contract_lift_from_semver} → {contract.semver_impact} "
                    f"(locked {contract.primary_intent_id}/{contract.cc_type})[/yellow]"
                )
        except Exception:
            # Lift is best-effort — never brick commit generation.
            contract_lift_applied = False
            contract_lift_from_semver = None
        # Slice 5.5 residual floor: re-assert lift immediately before advisory merge /
        # gold / persist so no later pure path can leave a demoted SemVer.
        try:
            commit_plan, _re_lift, _re_from = lift_plan_to_contract_semver(commit_plan, contract)
            if _re_lift:
                contract_lift_applied = True
                if contract_lift_from_semver is None:
                    contract_lift_from_semver = _re_from
        except Exception:
            pass
        # Capture persisted primary SemVer + evaluate lifecycle snapshot.
        try:
            _pers = getattr(commit_plan.primary_intent, "semver_impact", None)
            plan_persisted_semver = (
                str(_pers.value).upper()
                if hasattr(_pers, "value")
                else (str(_pers).strip().upper() if _pers is not None else None)
            )
            if plan_persisted_semver not in {"NONE", "PATCH", "MINOR", "MAJOR"}:
                plan_persisted_semver = None
        except Exception:
            plan_persisted_semver = None
        try:
            lifecycle = evaluate_contract_lifecycle(
                locked_semver=contract_locked_semver or getattr(contract, "semver_impact", None),
                llm_raw_semver=llm_raw_semver,
                persisted_semver=plan_persisted_semver,
                lift_applied=contract_lift_applied,
                lift_from_semver=contract_lift_from_semver,
                presentation_touched=presentation_touched_semver,
            )
            contract_locked_semver = lifecycle.contract_locked_semver
            llm_raw_semver = lifecycle.llm_raw_semver
            plan_persisted_semver = lifecycle.plan_persisted_semver
            contract_violation = lifecycle.contract_violation
            plan_normaliser_applied = lifecycle.plan_normaliser_applied
            plan_normaliser_reason = lifecycle.plan_normaliser_reason
            if contract_lift_applied:
                contract_lift_from_semver = lifecycle.contract_lift_from_semver
        except Exception:
            contract_violation = False
            plan_normaliser_applied = bool(contract_lift_applied)
            plan_normaliser_reason = "contract_lift" if contract_lift_applied else "none"
        if contract_violation:
            try:
                from git_cg.sentry_config import report_commit_plan_contract_violation
                from git_cg.telemetry import compute_diff_hash

                report_commit_plan_contract_violation(
                    locked_semver=contract_locked_semver,
                    persisted_semver=plan_persisted_semver,
                    lift_applied=contract_lift_applied,
                    lift_from_semver=contract_lift_from_semver,
                    normaliser_reason=plan_normaliser_reason,
                    diff_hash=compute_diff_hash(analysis_diff) if analysis_diff else None,
                )
            except Exception:
                pass
        # Phase 9: advisory OR-merge for split_recommended + rationale notes only.
        # Never mutates intent_id / gitmoji / cc_type / semver / changelog authority.
        try:
            from git_cg.scoped_history import apply_scoped_history_to_plan

            evidence_for_merge = scoped_history_evidence
            if evidence_for_merge is None:
                evidence_for_merge = {
                    "split_high_confidence": scoped_history_split_high_confidence,
                    "split_rationale": scoped_history_split_rationale,
                    "rename_confidence": rename_confidence,
                    "rename_rationale": scoped_history_rename_rationale,
                }
            commit_plan = apply_scoped_history_to_plan(commit_plan, evidence_for_merge)
        except Exception:
            pass
        if verbose:
            console.log(f"Resolved and Enforced Semantic Contract: {contract.primary_intent_id} ({contract.cc_type})")

        mixed_policy = os.environ.get("GIT_CG_MIXED_POLICY", "composite").lower()
        if commit_plan.split_recommended:
            msg = (
                "\n[bold yellow]⚠️  MIXED COMMIT DETECTED[/bold yellow]\n"
                f"[yellow]Rationale:[/yellow] {commit_plan.rationale}\n"
            )
            if mixed_policy == "strict":
                console.print(msg)
                _abort(
                    "[bold red]Policy is 'strict'. Aborting commit. Please split your changes.[/bold red]",
                    strict=strict,
                    report=False,
                )
            if mixed_policy == "warn":
                console.print(msg)
                console.print("[yellow]Policy is 'warn'. Proceeding with composite commit.[/yellow]\n")
            elif mixed_policy == "split_prompt" and verbose:
                console.print(msg)
                console.print(
                    "[yellow]split_prompt requested; this implementation keeps hook/default mode non-interactive. Use git-cg -i for review.[/yellow]"
                )

        # K-P0.3: a gold wording pass must re-anchor to the same primary; a differing
        # primary after a gold pass is a bug, not a feature. Use a controlled abort (not
        # a bare assert) so the invariant holds under `python -O` and surfaces via the
        # project's `_abort` path instead of an uncaught AssertionError on the hook path.
        if (
            gold_guidance is not None
            and gold_previous_primary_id is not None
            and contract.primary_intent_id != gold_previous_primary_id
        ):
            _abort(
                "[bold red]Internal error: gold pass re-anchored to a different primary intent "
                f"({contract.primary_intent_id!r} != {gold_previous_primary_id!r}).[/bold red]",
                strict=True,
            )

        conf_snap = gen_context.ranking_confidence
        review_state = ReviewState(
            commit_plan=commit_plan,
            issue_references=list(issue_references),
            ranking_confidence_level=(conf_snap.level if conf_snap else None),
            ranking_confidence_margin=(conf_snap.margin if conf_snap else None),
            ranking_confidence_reasons=(list(conf_snap.reasons) if conf_snap else []),
            ranking_confidence_top_intent_id=(conf_snap.top_intent_id if conf_snap else None),
            ranking_confidence_runner_up_intent_id=(conf_snap.runner_up_intent_id if conf_snap else None),
        )
        if regeneration_guidance:
            review_state.set_regeneration_guidance(regeneration_guidance)

        # Issue #204 Slice 8 — hallucination / craft guards (D14/D21).
        # Shares gold_regen_attempts ceiling (I-14); non-blocking on hooks after exhaustion
        # via deterministic priors/skeleton fallback.
        try:
            from git_cg.commit_quality import (
                apply_guard_skeleton_fallback,
                evaluate_presentation_guards,
                format_guard_guidance,
                merge_presentation_fallback_reason,
                try_repair_presentation_guards,
            )

            _guard_paths = list(getattr(gen_context.diff_signals, "files", None) or [])
            _guard_report = evaluate_presentation_guards(
                commit_plan,
                paths=_guard_paths,
                signals=gen_context.diff_signals,
                evidence_text=analysis_diff or "",
                constraints=getattr(gen_context, "presentation_constraints", None),
            )
            if _guard_report.hallucination_guard_fired:
                hallucination_guard_fired = True
            if _guard_report.dirty:
                # Deterministic wording repair first (security-noun scrub and
                # docs/tests craft openers — issue #214). This keeps gold-strict
                # usable without skeleton provenance when repair clears the dirty set.
                # Capture pre-repair codes before try_repair overwrites the report
                # with the clean post-repair evaluation (needed for operator copy).
                _pre_repair_codes = set(_guard_report.codes())
                commit_plan, _guard_report, _guard_repaired = try_repair_presentation_guards(
                    commit_plan,
                    paths=_guard_paths,
                    signals=gen_context.diff_signals,
                    evidence_text=analysis_diff or "",
                    constraints=getattr(gen_context, "presentation_constraints", None),
                    report=_guard_report,
                )
                if _guard_repaired:
                    review_state.commit_plan = commit_plan
                    guard_guidance = None
                    if verbose or gold_mode != "off":
                        # Keep security-noun wording for the single-code security path so
                        # Slice 8 harnesses and operators still see the established phrase;
                        # craft-only repairs use the generic wording label (#214).
                        if _pre_repair_codes == {"GUARD_SECURITY_NOUN"}:
                            _repair_label = "deterministic security-noun repair"
                        else:
                            _repair_label = "deterministic wording repair"
                        console.print(
                            f"[yellow]Presentation guard: applied {_repair_label} (no skeleton provenance).[/yellow]"
                        )
                    # Fall through to gold with the repaired plan.
                else:
                    presentation_fallback_reason = merge_presentation_fallback_reason(
                        presentation_fallback_reason,
                        _guard_report.fallback_reason,
                    )
                    with contextlib.suppress(Exception):
                        sentry_sdk.set_tag("presentation_fallback_reason", str(presentation_fallback_reason))
                        sentry_sdk.set_tag("path_class_gate", str(path_class_gate))
                        sentry_sdk.set_tag(
                            "hallucination_guard_fired",
                            "true" if hallucination_guard_fired else "false",
                        )
                    if gold_regen_attempts >= 2:
                        # Exhausted shared wording budget → deterministic skeleton (D14).
                        commit_plan = apply_guard_skeleton_fallback(
                            commit_plan,
                            paths=_guard_paths,
                            signals=gen_context.diff_signals,
                            priors=gen_context.scope_priors,
                            constraints=gen_context.presentation_constraints,
                            claim_tags=harvested_claim_tags,
                            report=_guard_report,
                        )
                        review_state.commit_plan = commit_plan
                        guard_guidance = None
                        # Fresh gold evaluation against the skeleton; do not inherit prior gold codes.
                        gold_guidance = None
                        gold_previous_codes = None
                        if verbose:
                            console.log(
                                "[yellow]Presentation guards exhausted shared regen budget; "
                                "applied deterministic skeleton fallback.[/yellow]"
                            )
                    else:
                        # Shared wording budget with gold (I-14). Clear gold guidance/codes so a
                        # guard retry does not re-anchor on stale gold findings.
                        gold_regen_attempts += 1
                        guard_guidance = format_guard_guidance(_guard_report)
                        gold_guidance = None
                        gold_previous_codes = None
                        gold_previous_primary_id = commit_plan.primary_intent.intent_id
                        if verbose or gold_mode != "off":
                            codes = ", ".join(sorted(_guard_report.codes()))
                            console.print(
                                f"[yellow]Presentation guard ({_guard_report.fallback_reason}): {codes} "
                                f"(shared regen {gold_regen_attempts}/2)[/yellow]"
                            )
                        continue
            else:
                guard_guidance = None
        except typer.Exit:
            # Controlled aborts (e.g. strict blueprint / gold hard-fail) must propagate.
            raise
        except Exception as _guard_exc:
            # Guards must never brick commit generation.
            if verbose:
                console.log(f"[yellow]Presentation guards skipped ({type(_guard_exc).__name__}: {_guard_exc})[/yellow]")

        # Issue #182 / #191: gold runs after mixed-policy and ReviewState construction,
        # before render/write/acceptance display. Findings print unconditionally in
        # warn/surface/strict (never verbose-gated); pass/fail derives from
        # STRICT_FAIL_CODES + mode. Bounded self-correction (max 2) with monotonic
        # code-set shrinkage — never re-enters #195 arbitration.
        gold_report = check_commit_gold(
            commit_plan,
            contract,
            signals=gen_context.diff_signals,
            ranked_intents=gen_context.ranked_intents,
            presentation_overlay_applied=presentation_overlay_applied,
        )
        review_state.gold_findings = list(gold_report.findings)
        # P6 telemetry: structured signal from GoldFinding.split_preferred (not message prose).
        if gold_report.has_split_recommendation():
            gold_split_recommendation = True
        gold_guidance = None
        if gold_mode != "off" and gold_report.findings:
            codes = ", ".join(sorted(gold_report.codes()))
            console.print(f"[yellow]Gold lint ({gold_mode}): {codes}[/yellow]")
            for finding in gold_report.findings:
                console.print(f"  [yellow]- {finding.code}: {finding.message}[/yellow]")
        if not gold_report.ok_for_mode(gold_mode):
            # Issue #191 lock: compare ALL emitted finding codes for shrinkage
            # (not only STRICT_FAIL_CODES). Pass/fail still uses ok_for_mode.
            current_codes = gold_report.codes()
            abort_outcome: str | None = None
            # Option B (Issue #191): after 2 completed regens any remaining fail is exhausted.
            # Stall/growth apply only when fewer than 2 regens have completed.
            if gold_regen_attempts >= 2:
                abort_outcome = GoldSelfCorrectionOutcome.EXHAUSTED.value
            elif gold_previous_codes is not None:
                if current_codes == gold_previous_codes:
                    abort_outcome = GoldSelfCorrectionOutcome.ABORTED_STALL.value
                elif not current_codes < gold_previous_codes:
                    # Grew, disjoint, or non-strict-subset.
                    abort_outcome = GoldSelfCorrectionOutcome.ABORTED_GROWTH.value
            if abort_outcome is None:
                gold_regen_attempts += 1  # incremented immediately before the gold continue
                gold_guidance = "; ".join(f.message for f in gold_report.findings)
                gold_previous_primary_id = commit_plan.primary_intent.intent_id
                gold_previous_codes = current_codes
                console.print(
                    f"[yellow]Regenerating wording from gold feedback (attempt {gold_regen_attempts}/2)...[/yellow]"
                )
                continue
            # Strict gold abort — codes/summary only; Sentry-visible (report=True).
            gold_self_correction_outcome = abort_outcome
            _apply_issue195_sentry_tags(
                ranking_confidence_level=(
                    gen_context.ranking_confidence.level if gen_context.ranking_confidence else None
                ),
                ranking_choice_path=ranking_choice_path,
                gold_mode=gold_mode,
                gold_self_correction_outcome=gold_self_correction_outcome,
            )
            # Persist v1.1 outcome before abort so Opik state captures the fail mode.
            path_class_gate, changelog_antisignal_applied, _scope_from = _presentation_telemetry_from_context(
                gen_context,
                commit_plan=getattr(review_state, "commit_plan", None) if review_state is not None else None,
                preferred_scope_raw=(active_directives or {}).get("preferred_scope"),
            )
            _stashed = getattr(getattr(review_state, "commit_plan", None), "_scope_normalised_from", None)
            if _stashed and str(_stashed) != "none":
                scope_normalised_from = str(_stashed)
            elif _scope_from != "none":
                scope_normalised_from = _scope_from
            _write_telemetry_state_safe(
                review_state=review_state,
                diff_output=analysis_diff,
                engine=engine,
                model_name=model_name,
                system_prompt=system_prompt,
                repo_name=repo_name,
                thread_id=thread_id,
                verbose=verbose,
                graph_schema_version=crg_schema_version,
                semantic_enabled=semantic_enabled,
                parser_latency_ms=parser_latency_ms,
                graph_build_latency_ms=graph_build_latency_ms,
                graph_query_latency_ms=graph_query_latency_ms,
                semantic_parser_metrics=semantic_parser_metrics,
                body_similarity_min=body_similarity_min,
                body_similarity_avg=body_similarity_avg,
                fingerprint_files_compared=fingerprint_files_compared,
                fingerprint_latency_ms=fingerprint_latency_ms,
                fingerprint_class_counts=fingerprint_class_counts,
                fingerprint_grammar_version=fingerprint_grammar_version,
                fingerprint_markers=fingerprint_markers,
                preflight_mode=preflight_mode,
                preflight_groups_count=preflight_groups_count,
                preflight_fallback_reason=preflight_fallback_reason,
                blast_radius_size=blast_radius_size
                if isinstance(blast_radius_size, int) and not isinstance(blast_radius_size, bool)
                else None,
                affected_flows_count=affected_flows_count
                if isinstance(affected_flows_count, int) and not isinstance(affected_flows_count, bool)
                else None,
                test_coverage_gap=bool(test_coverage_gap) if test_coverage_gap is not None else None,
                test_gaps_count=test_gaps_count
                if isinstance(test_gaps_count, int) and not isinstance(test_gaps_count, bool)
                else None,
                semantic_context_schema_version=semantic_context_schema_version,
                semantic_context_fallback_reasons=semantic_context_fallback_reasons,
                shadow_workspace_used=shadow_workspace_used,
                semantic_refresh_graph=semantic_refresh_graph,
                shadow_fail_open_reason=shadow_fail_open_reason,
                ranking_confidence_level=(
                    gen_context.ranking_confidence.level if gen_context.ranking_confidence else None
                ),
                ranking_confidence_margin=(
                    gen_context.ranking_confidence.margin if gen_context.ranking_confidence else None
                ),
                ranking_confidence_reasons=(
                    list(gen_context.ranking_confidence.reasons) if gen_context.ranking_confidence else None
                ),
                ranking_choice_path=ranking_choice_path,
                ranking_override=bool(ranking_override),
                ranking_arbitrate_effective=ranking_arbitrate_effective,
                lock_resolution=last_lock_resolution,
                gold_mode=gold_mode,
                gold_findings_count=len(gold_report.findings),
                gold_finding_codes=sorted(gold_report.codes()),
                gold_blocked=True,
                gold_regen_attempts=gold_regen_attempts,
                gold_self_correction_attempts=gold_regen_attempts,
                gold_self_correction_outcome=gold_self_correction_outcome,
                gold_split_recommendation=bool(gold_split_recommendation),
                scoped_history_fallback_reason=scoped_history_fallback_reason,
                scoped_history_latency_ms=scoped_history_latency_ms,
                rename_confidence=rename_confidence,
                scoped_history_split_high_confidence=scoped_history_split_high_confidence,
                scoped_history_guidance=scoped_history_guidance,
                scoped_history_split_rationale=scoped_history_split_rationale,
                scoped_history_rename_rationale=scoped_history_rename_rationale,
                structural_error_handling=structural_error_handling,
                structural_public_api=structural_public_api,
                structural_new_command=structural_new_command,
                presentation_fallback_reason=presentation_fallback_reason,
                blueprint_applied=blueprint_applied,
                hallucination_guard_fired=hallucination_guard_fired,
                path_class_gate=path_class_gate,
                changelog_antisignal_applied=changelog_antisignal_applied,
                scope_normalised_from=scope_normalised_from,
                contract_lift_applied=contract_lift_applied,
                contract_lift_from_semver=contract_lift_from_semver,
                contract_locked_semver=contract_locked_semver,
                llm_raw_semver=llm_raw_semver,
                plan_persisted_semver=plan_persisted_semver,
                contract_violation=contract_violation,
                plan_normaliser_applied=plan_normaliser_applied,
                plan_normaliser_reason=plan_normaliser_reason,
            )
            _abort(
                "[bold red]Commit message failed gold lint in strict mode: "
                + ", ".join(sorted(gold_report.codes()))
                + "[/bold red]",
                strict=True,
                report=True,
            )
        elif gold_regen_attempts > 0:
            # Clean after one or more wording regens.
            gold_self_correction_outcome = GoldSelfCorrectionOutcome.CLEARED.value

        result_string = review_state.render()
        if verbose or dry_run:
            console.print(Panel(result_string, title="Generated Commit Message", border_style="green"))

        if dry_run:
            # Phase 7.5 (#180): bounded shadow-state echo (resolved semantic-on, quiet dry-run).
            if semantic_enabled and not verbose:
                from git_cg.telemetry import ShadowFailOpenReason

                shadow_used = "true" if shadow_workspace_used else "false"
                console.log(f"[dim]shadow_workspace used={shadow_used}[/dim]")
                console.log(f"[dim]semantic_refresh_graph state={semantic_refresh_graph}[/dim]")
                if shadow_fail_open_reason != ShadowFailOpenReason.NONE.value:
                    console.log(f"[dim]shadow_fail_open reason={shadow_fail_open_reason}[/dim]")

            should_interact = interactive and can_open_tty()
            if interactive and not should_interact and verbose:
                console.log(
                    "[yellow]Interactive mode requested but /dev/tty is unavailable. Proceeding non-interactively.[/yellow]"
                )
            if should_interact:
                action = _interactive_review_dry_run(
                    review_state, verbose=verbose, strict=strict, gui_editor=gui_editor
                )
                issue_references = list(review_state.issue_references)
                regeneration_guidance = review_state.regeneration_guidance
                active_directives = review_state.active_directives
                residual_guidance = review_state.residual_guidance
                if action == "Regenerate":
                    console.print("\n[yellow]Regenerating commit message...[/yellow]")
                    continue
                if action == "Cancel":
                    _abort("\n[bold red]Dry-run cancelled by user.[/bold red]", strict=strict, report=False)
            break

        _write_commit_message(commit_msg_file, result_string, strict=strict, verbose=verbose)

        should_interact = interactive and can_open_tty()
        if interactive and not should_interact and verbose:
            console.log(
                "[yellow]Interactive mode requested but /dev/tty is unavailable. Proceeding non-interactively.[/yellow]"
            )

        if should_interact:
            action = _interactive_review(
                commit_msg_file, review_state, verbose=verbose, strict=strict, gui_editor=gui_editor
            )
            issue_references = list(review_state.issue_references)
            regeneration_guidance = review_state.regeneration_guidance
            active_directives = review_state.active_directives
            residual_guidance = review_state.residual_guidance
            if action == "Regenerate":
                console.print("\n[yellow]Regenerating commit message...[/yellow]")
                continue
            if action == "Cancel":
                _abort("\n[bold red]Commit aborted by user.[/bold red]", strict=strict, report=False)
            break

        break

    path_class_gate, changelog_antisignal_applied, _scope_from = _presentation_telemetry_from_context(
        gen_context,
        commit_plan=getattr(review_state, "commit_plan", None) if review_state is not None else None,
        preferred_scope_raw=(active_directives or {}).get("preferred_scope") if active_directives else None,
    )
    _stashed = getattr(getattr(review_state, "commit_plan", None), "_scope_normalised_from", None)
    if _stashed and str(_stashed) != "none":
        scope_normalised_from = str(_stashed)
    elif _scope_from != "none":
        scope_normalised_from = _scope_from
    _write_telemetry_state_safe(
        review_state=review_state,
        diff_output=analysis_diff,
        engine=engine,
        model_name=model_name,
        system_prompt=system_prompt,
        repo_name=repo_name,
        thread_id=thread_id,
        verbose=verbose,
        graph_schema_version=crg_schema_version,
        semantic_enabled=semantic_enabled,
        parser_latency_ms=parser_latency_ms,
        graph_build_latency_ms=graph_build_latency_ms,
        graph_query_latency_ms=graph_query_latency_ms,
        semantic_parser_metrics=semantic_parser_metrics,
        body_similarity_min=body_similarity_min,
        body_similarity_avg=body_similarity_avg,
        fingerprint_files_compared=fingerprint_files_compared,
        fingerprint_latency_ms=fingerprint_latency_ms,
        fingerprint_class_counts=fingerprint_class_counts,
        fingerprint_grammar_version=fingerprint_grammar_version,
        fingerprint_markers=fingerprint_markers,
        preflight_mode=preflight_mode,
        preflight_groups_count=preflight_groups_count,
        preflight_fallback_reason=preflight_fallback_reason,
        blast_radius_size=blast_radius_size
        if isinstance(blast_radius_size, int) and not isinstance(blast_radius_size, bool)
        else None,
        affected_flows_count=affected_flows_count
        if isinstance(affected_flows_count, int) and not isinstance(affected_flows_count, bool)
        else None,
        test_coverage_gap=bool(test_coverage_gap) if test_coverage_gap is not None else None,
        test_gaps_count=test_gaps_count
        if isinstance(test_gaps_count, int) and not isinstance(test_gaps_count, bool)
        else None,
        semantic_context_schema_version=semantic_context_schema_version,
        semantic_context_fallback_reasons=semantic_context_fallback_reasons,
        shadow_workspace_used=shadow_workspace_used,
        semantic_refresh_graph=semantic_refresh_graph,
        shadow_fail_open_reason=shadow_fail_open_reason,
        ranking_confidence_level=(gen_context.ranking_confidence.level if gen_context.ranking_confidence else None),
        ranking_confidence_margin=(gen_context.ranking_confidence.margin if gen_context.ranking_confidence else None),
        ranking_confidence_reasons=(
            list(gen_context.ranking_confidence.reasons) if gen_context.ranking_confidence else None
        ),
        ranking_choice_path=ranking_choice_path,
        ranking_override=bool(ranking_override),
        ranking_arbitrate_effective=ranking_arbitrate_effective,
        lock_resolution=last_lock_resolution,
        gold_mode=gold_mode,
        gold_findings_count=len(getattr(review_state, "gold_findings", []) or []),
        gold_finding_codes=sorted(
            {getattr(f, "code", str(f)) for f in (getattr(review_state, "gold_findings", []) or [])}
        ),
        gold_blocked=bool(gold_mode == "strict" and gold_report is not None and not gold_report.ok_for_mode("strict")),
        gold_regen_attempts=gold_regen_attempts,
        gold_self_correction_attempts=gold_regen_attempts,
        gold_self_correction_outcome=gold_self_correction_outcome,
        gold_split_recommendation=bool(gold_split_recommendation),
        scoped_history_fallback_reason=scoped_history_fallback_reason,
        scoped_history_latency_ms=scoped_history_latency_ms,
        rename_confidence=rename_confidence,
        scoped_history_split_high_confidence=scoped_history_split_high_confidence,
        scoped_history_guidance=scoped_history_guidance,
        scoped_history_split_rationale=scoped_history_split_rationale,
        scoped_history_rename_rationale=scoped_history_rename_rationale,
        structural_error_handling=structural_error_handling,
        structural_public_api=structural_public_api,
        structural_new_command=structural_new_command,
        presentation_fallback_reason=presentation_fallback_reason,
        blueprint_applied=blueprint_applied,
        hallucination_guard_fired=hallucination_guard_fired,
        path_class_gate=path_class_gate,
        changelog_antisignal_applied=changelog_antisignal_applied,
        scope_normalised_from=scope_normalised_from,
        contract_lift_applied=contract_lift_applied,
        contract_lift_from_semver=contract_lift_from_semver,
        contract_locked_semver=contract_locked_semver,
        llm_raw_semver=llm_raw_semver,
        plan_persisted_semver=plan_persisted_semver,
        contract_violation=contract_violation,
        plan_normaliser_applied=plan_normaliser_applied,
        plan_normaliser_reason=plan_normaliser_reason,
    )

    opik.flush_tracker()
    sentry_sdk.flush(timeout=2.0)
    return True


def _apply_standalone_commit(commit_msg_file: str, *, strict: bool) -> None:
    """
    Run `git commit -F <commit_msg_file>` to create a commit from the specified message file and abort on failure.

    Parameters:
        commit_msg_file (str): Path to the file containing the commit message to apply.
        strict (bool): If True, a failed commit results in a non-zero exit (strict abort); if False, abort exits with code 0 to avoid blocking hooks.
    """
    try:
        result = subprocess.run(["git", "commit", "-F", commit_msg_file], check=False)
        if result.returncode != 0:
            console.print(f"\n[yellow]Your generated commit message was safely retained at: {commit_msg_file}[/yellow]")
            console.print("[green]To retry applying it after fixing the hook errors, run:[/green]")
            console.print("[bold cyan]  git-cg --recover[/bold cyan]\n")
            _abort("[bold red]git commit failed while applying generated commit message.[/bold red]", strict=strict)
    except FileNotFoundError as e:
        _abort(f"[bold red]Unable to execute git commit:[/bold red] {e}", strict=strict)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Enable terminal-native interactive review via gum."
    ),
    term_editor: bool = typer.Option(
        True, "--term", "-t", help="Use Terminal Editor ($EDITOR) when editing commit messages (Default)."
    ),
    gui_editor: bool = typer.Option(
        False, "--gui", "-g", help="Use GUI Editor ($VISUAL) when editing commit messages."
    ),
    enable_semantic: bool | None = typer.Option(
        None,
        "--enable-semantic/--no-enable-semantic",
        help="Enable Phase 1 semantic producers (default: GIT_CG_ENABLE_SEMANTIC env or off).",
    ),
    rank_arbitrate: bool | None = typer.Option(
        None,
        "--rank-arbitrate/--no-rank-arbitrate",
        help=(
            "Allow Low-confidence pre-LLM intent arbitration when -i + TTY "
            "(default: GIT_CG_RANK_ARBITRATE env or auto)."
        ),
    ),
    gold_strict: bool = typer.Option(
        False,
        "--gold-strict",
        help="Resolve gold lint to strict mode without enabling general --strict.",
    ),
    blueprint: str | None = typer.Option(
        None,
        "--blueprint",
        help=(
            "Optional presentation CommitBlueprint as inline JSON or @path.json "
            "(max 64KiB; never overrides ranked intent_id)."
        ),
    ),
    engine: str = typer.Option(
        os.environ.get("GIT_CG_ENGINE") or "mtplx",
        "--engine",
        "-e",
        help="AI engine to use when running git-cg directly.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d", help="Generate and print the commit message without applying a commit."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output."),
    strict: bool = typer.Option(True, "--strict", help="Exit non-zero on failure for standalone CLI use."),
    recover: bool = typer.Option(
        False, "--recover", "-r", help="Recover and retry the last generated commit message without querying the AI."
    ),
) -> None:
    """
    Entrypoint callback for the CLI that generates a Conventional Commit from staged changes and, when invoked without a subcommand, applies it to the repository.

    Runs the commit-generation and optional interactive review flow using the provided options, resolves the repository COMMIT_EDITMSG path, and — unless `dry_run` is true — runs a standalone `git commit` with the generated message. Always terminates the CLI by raising `typer.Exit` (exit code 0 on success).

    Parameters:
        ctx (typer.Context): Typer invocation context; if a subcommand was invoked or resilient parsing is active, the callback returns early.
        interactive (bool): If true, enable terminal-native interactive review via gum.
        engine (str): AI engine identifier to use when generating the commit message.
        dry_run (bool): If true, generate and display the commit message without applying a commit.
        verbose (bool): If true, enable verbose output.
        strict (bool): If true, exit with a non-zero code on failure suitable for standalone CLI usage.

    Raises:
        typer.Exit: Raised at the end to terminate the CLI; exit code reflects success or configured strict behaviour.
    """
    if ctx.invoked_subcommand is not None or ctx.resilient_parsing:
        return

    try:
        git_dir = subprocess.check_output(["git", "rev-parse", "--git-dir"], text=True).strip()
        commit_msg_file = os.path.join(git_dir, "COMMIT_EDITMSG")
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        OSError,
    ):
        commit_msg_file = os.path.join(".git", "COMMIT_EDITMSG")

    if recover:
        if os.path.exists(commit_msg_file) and os.path.getsize(commit_msg_file) > 0:
            console.print(f"[green]Recovering previous commit message from {commit_msg_file}...[/green]")
            if not dry_run:
                _apply_standalone_commit(commit_msg_file, strict=strict)
            raise typer.Exit(code=0)
        else:
            _abort("[red]No previous commit message found to recover.[/red]", strict=strict)

    _run_commit_generation(
        commit_msg_file,
        None,
        None,
        engine=engine,
        dry_run=dry_run,
        verbose=verbose,
        amend_regenerate=False,
        strict=strict,
        interactive=interactive,
        gui_editor=gui_editor,
        enable_semantic=enable_semantic,
        gold_strict=gold_strict,
        rank_arbitrate=rank_arbitrate,
        blueprint=blueprint,
    )
    if not dry_run:
        _apply_standalone_commit(commit_msg_file, strict=strict)
    raise typer.Exit(code=0)


@app.command("commit")
def commit(
    commit_msg_file: str = typer.Argument(".git/COMMIT_EDITMSG", help="Path to the commit message file"),
    commit_source: str = typer.Argument(
        "", help="Source of the commit message (e.g., 'message', 'template', or empty for default generation)"
    ),
    extra_args: list[str] | None = typer.Argument(None, help="Any extra arguments passed by git hooks"),
    engine: str = typer.Option(
        os.environ.get("GIT_CG_ENGINE") or "mtplx", "--engine", "-e", help="AI engine to use (e.g. omlx, mtplx)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Do not write the commit message, just print it"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    amend_regenerate: bool = typer.Option(
        False,
        "--amend-regenerate",
        help="Opt in to regenerating the message on git --amend (source 'commit'). Off by default.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit non-zero on failure. Leave OFF for git hooks so a failed generation never blocks the commit; turn ON for CLI/CI use.",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Enable terminal-native interactive review via gum when a TTY is available.",
    ),
    gold_strict: bool = typer.Option(
        False,
        "--gold-strict",
        help="Resolve gold lint to strict mode without enabling general --strict.",
    ),
    term_editor: bool = typer.Option(
        True, "--term", "-t", help="Use Terminal Editor ($EDITOR) when editing commit messages (Default)."
    ),
    gui_editor: bool = typer.Option(
        False, "--gui", "-g", help="Use GUI Editor ($VISUAL) when editing commit messages."
    ),
    enable_semantic: bool | None = typer.Option(
        None,
        "--enable-semantic/--no-enable-semantic",
        help="Enable Phase 1 semantic producers (default: GIT_CG_ENABLE_SEMANTIC env or off).",
    ),
    rank_arbitrate: bool | None = typer.Option(
        None,
        "--rank-arbitrate/--no-rank-arbitrate",
        help=(
            "Allow Low-confidence pre-LLM intent arbitration when -i + TTY "
            "(default: GIT_CG_RANK_ARBITRATE env or auto)."
        ),
    ),
    blueprint: str | None = typer.Option(
        None,
        "--blueprint",
        help=(
            "Optional presentation CommitBlueprint as inline JSON or @path.json "
            "(max 64KiB; never overrides ranked intent_id)."
        ),
    ),
) -> None:
    """Generate an AI commit message based on staged changes."""
    _run_commit_generation(
        commit_msg_file,
        commit_source,
        extra_args,
        engine=engine,
        dry_run=dry_run,
        verbose=verbose,
        amend_regenerate=amend_regenerate,
        strict=strict,
        interactive=interactive,
        gui_editor=gui_editor,
        enable_semantic=enable_semantic,
        gold_strict=gold_strict,
        rank_arbitrate=rank_arbitrate,
        blueprint=blueprint,
    )


@app.command("preflight")
def preflight(
    paths: list[str] | None = typer.Argument(
        None,
        help="Optional staged-path overrides. Defaults to `git diff --cached --name-only`.",
    ),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of human tables.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Include stub notes and theme bullets."),
) -> None:
    """Print a read-only diff-class / path-class preflight summary (Issue #204).

    Does not invoke the LLM, ranker, hooks, or git writes. Safe for CI and local
    operator dry-runs before commit generation.
    """
    import json as _json
    import subprocess as _subprocess

    from git_cg.commit_quality import (
        build_high_risk_checklist_themes,
        build_included_change_stubs,
        classify_diff_class,
        constraints_from_paths,
        derive_trailer_priors,
        detect_high_risk_surfaces,
        format_high_risk_body_checklist,
        presentation_constraints,
        semver_presentation_ceiling,
    )

    resolved: list[str] = []
    if paths:
        resolved = [str(p).strip() for p in paths if str(p).strip()]
    else:
        try:
            proc = _subprocess.run(
                ["git", "diff", "--cached", "--name-only", "-z"],
                check=False,
                capture_output=True,
                text=False,
            )
            if proc.returncode == 0 and proc.stdout:
                resolved = [p.decode("utf-8", "surrogateescape") for p in proc.stdout.split(b"\0") if p]
        except OSError as exc:
            console.print(f"[red]preflight could not read staged paths: {type(exc).__name__}[/red]")
            raise typer.Exit(code=1) from exc

    # Preserve order, drop blanks/dupes.
    seen: set[str] = set()
    clean_paths: list[str] = []
    for raw in resolved:
        item = raw.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        clean_paths.append(item)

    diff_class = classify_diff_class(clean_paths)
    cons = constraints_from_paths(clean_paths)
    # constraints_from_paths may already embed class; keep presentation_constraints as fallback.
    if cons is None:
        cons = presentation_constraints(diff_class)
    priors = derive_trailer_priors(clean_paths)
    ceiling = semver_presentation_ceiling(clean_paths)
    surfaces = detect_high_risk_surfaces(clean_paths)
    themes = build_high_risk_checklist_themes(clean_paths)
    stubs = build_included_change_stubs(clean_paths)

    payload = {
        "paths": clean_paths,
        "path_count": len(clean_paths),
        "diff_class": getattr(diff_class, "name", str(diff_class)),
        "has_runtime_surface": bool(getattr(diff_class, "has_runtime_surface", False)),
        "force_cc_type": getattr(getattr(cons, "force_cc_type", None), "value", None),
        "forbid_cc_types": sorted(getattr(cons, "forbid_cc_types", ()) or ()),
        "force_semver": getattr(getattr(cons, "force_semver", None), "value", None),
        "force_scope": getattr(cons, "force_scope", None),
        "force_changelog_group": getattr(cons, "force_changelog_group", None),
        "semver_ceiling": getattr(ceiling, "value", str(ceiling)),
        "priors": {
            "role": getattr(priors, "role", None),
            "cc_type": getattr(getattr(priors, "cc_type", None), "value", None),
            "semver_impact": getattr(getattr(priors, "semver_impact", None), "value", None),
            "changelog_group": getattr(priors, "changelog_group", None),
            "scope_hint": getattr(priors, "scope_hint", None),
        },
        "high_risk_surfaces": list(surfaces),
        "high_risk_themes": list(themes),
        "included_change_stubs": [
            {
                "role": s.role,
                "surface": s.surface,
                "suggested_cc_type": s.suggested_cc_type.value,
                "scope": s.scope,
                "note": s.note,
                "claim_tags": list(s.claim_tags),
                "source": s.source,
            }
            for s in stubs
        ],
        "empty_or_unknown": not clean_paths,
    }

    if json_out:
        typer.echo(_json.dumps(payload, indent=2, sort_keys=True))
        raise typer.Exit(code=0)

    console.print(Panel("[bold green]git-cg preflight[/bold green] (read-only · no LLM · no ranker)"))
    if not clean_paths:
        console.print("[yellow]No paths resolved (empty staged set or unknown).[/yellow]")
    else:
        console.print(f"[cyan]paths[/cyan] ({len(clean_paths)}):")
        for p in clean_paths[:40]:
            console.print(f"  - {p}")
        if len(clean_paths) > 40:
            console.print(f"  … +{len(clean_paths) - 40} more")

    table = Table(title="Path-class envelope", show_lines=True)
    table.add_column("Field", style="magenta")
    table.add_column("Value", style="white")
    table.add_row("diff_class", str(payload["diff_class"]))
    table.add_row("has_runtime_surface", str(payload["has_runtime_surface"]))
    table.add_row("force_cc_type", str(payload["force_cc_type"]))
    table.add_row("forbid_cc_types", ", ".join(payload["forbid_cc_types"]) or "—")
    table.add_row("force_semver", str(payload["force_semver"]))
    table.add_row("semver_ceiling", str(payload["semver_ceiling"]))
    table.add_row("force_scope", str(payload["force_scope"]))
    table.add_row("force_changelog_group", str(payload["force_changelog_group"]))
    table.add_row("prior.role", str(payload["priors"]["role"]))
    table.add_row("prior.cc_type", str(payload["priors"]["cc_type"]))
    table.add_row("prior.scope_hint", str(payload["priors"]["scope_hint"]))
    console.print(table)

    if surfaces or themes:
        console.print("[cyan]high-risk surfaces[/cyan]: " + (", ".join(surfaces) if surfaces else "—"))
        console.print("[cyan]high-risk themes[/cyan]: " + (", ".join(themes) if themes else "—"))
        if verbose:
            checklist = format_high_risk_body_checklist(clean_paths, themes=themes)
            if checklist:
                console.print(Panel(checklist, title="High-risk checklist", border_style="yellow"))
    else:
        console.print("[dim]No high-risk surfaces detected.[/dim]")

    if stubs:
        stub_table = Table(title="Included-change stubs", show_lines=False)
        stub_table.add_column("role")
        stub_table.add_column("surface")
        stub_table.add_column("cc_type")
        stub_table.add_column("scope")
        if verbose:
            stub_table.add_column("note")
        for s in stubs:
            row = [s.role, s.surface, s.suggested_cc_type.value, str(s.scope or "")]
            if verbose:
                row.append(str(s.note or ""))
            stub_table.add_row(*row)
        console.print(stub_table)
    else:
        console.print("[dim]No included-change stubs (single-surface / no pressure).[/dim]")

    raise typer.Exit(code=0)


@app.command("sop")
def show_sop() -> None:
    """Display the GitOps SOP matrices and workflows."""
    data = load_sop()
    if not data:
        console.print(
            "[red]Could not locate gitops_agent_sop.json. Set GIT_CG_SOP_PATH or run inside the git-cg repo.[/red]"
        )
        raise typer.Exit(code=1)

    console.print(Panel("[bold green]GitOps SOP Loaded[/bold green]"))

    if "semver_resolution_matrix" in data:
        table = Table(title="SemVer Resolution Matrix", show_lines=True)
        table.add_column("Impact", style="cyan", no_wrap=True)
        table.add_column("Rule", style="white")
        for k, v in data["semver_resolution_matrix"].items():
            table.add_row(k, v)
        console.print(table)
        console.print("")

    if "agentic_release_workflow" in data:
        table = Table(title="Agentic Release Workflow", show_lines=True)
        table.add_column("Phase", style="magenta")
        for phase in data["agentic_release_workflow"].get("phases", []):
            table.add_row(phase)
        console.print(table)
        console.print("")

    if "changelog_generation_rules" in data:
        table = Table(title="Changelog Generation Rules", show_lines=True)
        table.add_column("Taxonomy", style="yellow")
        for tax in data["changelog_generation_rules"].get("taxonomy", []):
            table.add_row(tax)
        console.print(table)
        console.print("")


@app.command("release")
def release(
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d", help="Print changes without modifying files or executing git tags"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    pre_release: str | None = typer.Option(
        None, "--pre-release", help="Add or bump a pre-release identifier (e.g., 'alpha', 'rc')"
    ),
    theme: str | None = typer.Option(
        None,
        "--theme",
        help="GitHub release title theme after the version (e.g. 'Semantic Context integration')",
    ),
    notes_file: str | None = typer.Option(
        None,
        "--notes-file",
        help="Path to write gold-standard GitHub release notes markdown (default under .git/)",
    ),
    publish_github: bool = typer.Option(
        False,
        "--publish-github",
        help="Create the GitHub Release via `gh` after preparing files (requires network + auth)",
    ),
    github_latest: bool = typer.Option(
        False,
        "--github-latest",
        help="Publish GitHub release as latest (not pre-release). Default is pre-release.",
    ),
    skip_github_notes: bool = typer.Option(
        False,
        "--skip-github-notes",
        help="Only bump versions/CHANGELOG; skip gold-standard GitHub notes assembly",
    ),
    repo_slug: str | None = typer.Option(
        None,
        "--repo-slug",
        help="GitHub owner/repo for compare links and gh publish (default: detect from origin/gh)",
    ),
    github_target: str | None = typer.Option(
        None,
        "--github-target",
        help="Optional git ref for gh release create --target; omit to use an existing local tag",
    ),
) -> None:
    """
    Run the release workflow.

    Calculates SemVer impact from Hybrid trailers, injects versions, updates
    CHANGELOG.md, and assembles gold-standard GitHub Release notes (Issue #181).

    Parameters:
        dry_run: Print planned changelog/notes without writing files or publishing.
        verbose: Extra logging.
        pre_release: Pre-release identifier to add or bump (e.g. `alpha`, `rc`).
        theme: Optional title theme after ``vX.Y.Z:``.
        notes_file: Optional path for the GitHub notes markdown file.
        publish_github: Create the GitHub release with ``gh`` (non-dry-run only).
        github_latest: When publishing, mark as full latest release instead of pre-release.
        skip_github_notes: Legacy path — version/changelog only.
        repo_slug: Optional ``owner/repo`` override for notes links and publish.
        github_target: Optional ref for ``gh release create --target``.
    """
    if publish_github and skip_github_notes:
        raise typer.BadParameter("--publish-github cannot be combined with --skip-github-notes")

    try:
        from git_cg.release import execute_release

        execute_release(
            dry_run=dry_run,
            verbose=verbose,
            pre_release=pre_release,
            theme=theme,
            notes_path=notes_file,
            publish_github=publish_github,
            github_prerelease=not github_latest,
            repo_slug=repo_slug,
            skip_github_notes=skip_github_notes,
            github_target=github_target,
        )
    except ImportError as e:
        console.print(f"[bold red]Error loading release module:[/bold red] {e}")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[bold red]Invalid release options:[/bold red] {e}")
        sys.exit(2)


@app.command("record-telemetry")
def record_telemetry(
    commit_msg_file: str = typer.Argument(".git/COMMIT_EDITMSG", help="Path to the final commit message file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    """
    Record final commit telemetry in Opik.

    Classifies how the generated commit message was changed, logs the stored telemetry metadata, and clears the saved telemetry state afterwards.

    Parameters:
        commit_msg_file (str): Path to the final commit message file.
        verbose (bool): Enables verbose output.
    """
    import subprocess

    from git_cg.telemetry import (
        classify_edit,
        clear_telemetry_state,
        read_telemetry_state,
        redact_payload,
        reverse_parse_commit_message,
    )

    try:
        git_dir = subprocess.check_output(["git", "rev-parse", "--git-dir"], text=True).strip()
    except Exception:
        git_dir = ".git"

    state = read_telemetry_state(git_dir)
    if not state:
        if verbose:
            console.log("No git-cg telemetry state found. Skipping.")
        raise typer.Exit(code=0)

    try:
        with open(commit_msg_file, encoding="utf-8") as f:
            final_message = f.read()
    except Exception as e:
        if verbose:
            console.log(f"Failed to read final commit message: {e}")
        clear_telemetry_state(git_dir)
        raise typer.Exit(code=0) from e

    provenance = classify_edit(state.generated_message, final_message)
    if verbose:
        console.log(f"Edit classification: {provenance.value}")

    # Log the final trace data to Opik
    try:

        @opik.track(
            project_name="gitCommitGenerator",
            ignore_arguments=["final_commit_message", "telemetry_state"],
        )
        def log_final_commit_telemetry(
            final_commit_message: str,
            provenance: str,
            telemetry_state: dict,
            **kwargs,
        ):
            # The decorator automatically logs inputs/outputs
            """
            Record final commit telemetry and the corresponding user-acceptance score in Opik.

            Parameters:
                final_commit_message (str): The final commit message to classify and record.
                provenance (str): Classification of how the message was modified.
                telemetry_state (dict): Telemetry metadata associated with the generated commit message.

            Returns:
                dict: A result containing `"status": "recorded"` and the supplied provenance classification.
            """
            opik_args = kwargs.get("opik_args") or {}
            thread_id = opik_args.get("trace", {}).get("thread_id")

            # Map provenance to feedback score
            score_mapping = {
                "ai_accepted": 1.0,
                "ai_accepted_refs_only": 0.9,
                "ai_edited_minor": 0.6,
                "ai_edited_substantive": 0.15,
                "human_authored": 0.0,
                "cancelled": 0.0,
            }
            feedback_score = score_mapping.get(provenance, 0.0)

            # Phase 14: Reverse-parse the final message into structured fields
            # for DPO training pairs: (original_plan, final_plan, edit_classification).
            # Always redact before parse/transmit — betterleaks gateway is mandatory.
            redacted_final_message = redact_payload(final_commit_message)
            final_plan_json = reverse_parse_commit_message(redacted_final_message)

            plan_str = json.dumps(final_plan_json)
            redacted_plan_str = redact_payload(plan_str)
            if redacted_plan_str == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]":
                final_plan_json = {"_redaction": "failed", "_partial": True}
            else:
                final_plan_json = json.loads(redacted_plan_str)

            opik_context.update_current_trace(
                tags=[
                    provenance,
                    "git-cg-final",
                    "git-cg",
                    f"engine:{telemetry_state.get('engine')}",
                    f"repo:{telemetry_state.get('repo_name')}",
                ],
                metadata={
                    "diff_hash": telemetry_state.get("diff_hash"),
                    "repo_name": telemetry_state.get("repo_name"),
                    "engine": telemetry_state.get("engine"),
                    "model_name": telemetry_state.get("model_name"),
                    "system_prompt_hash": telemetry_state.get("system_prompt_hash"),
                    "score_card": telemetry_state.get("score_card"),
                    "commit_plan": telemetry_state.get("commit_plan_json"),
                    # Partial reverse-parse of the rendered message (not a full CommitPlan).
                    "final_commit_plan": final_plan_json,
                    "final_commit_plan_schema": "commit_plan_partial_v1",
                    "graph_schema_version": telemetry_state.get("graph_schema_version"),
                    # Phase 1 semantic producer metrics (from prepare-commit-msg state).
                    "semantic_enabled": telemetry_state.get("semantic_enabled", False),
                    "parser_latency_ms": telemetry_state.get("parser_latency_ms", 0.0),
                    "graph_build_latency_ms": telemetry_state.get("graph_build_latency_ms", 0.0),
                    "graph_query_latency_ms": telemetry_state.get("graph_query_latency_ms", 0.0),
                    "semantic_parser_metrics": telemetry_state.get("semantic_parser_metrics"),
                    # Phase 2 fingerprint algebra metrics (Issue #160).
                    "body_similarity_min": telemetry_state.get("body_similarity_min"),
                    "body_similarity_avg": telemetry_state.get("body_similarity_avg"),
                    "fingerprint_files_compared": telemetry_state.get("fingerprint_files_compared", 0),
                    "fingerprint_latency_ms": telemetry_state.get("fingerprint_latency_ms", 0.0),
                    "fingerprint_class_counts": telemetry_state.get("fingerprint_class_counts"),
                    "fingerprint_grammar_version": telemetry_state.get("fingerprint_grammar_version", "unknown"),
                    "fingerprint_markers": telemetry_state.get("fingerprint_markers"),
                    # Phase 3 preflight telemetry (Issue #161).
                    "preflight_mode": telemetry_state.get("preflight_mode", "skipped"),
                    "preflight_groups_count": telemetry_state.get("preflight_groups_count", 0),
                    "preflight_fallback_reason": telemetry_state.get("preflight_fallback_reason", ""),
                    # Phase 7 semantic context product metrics (Issue #162).
                    "blast_radius_size": telemetry_state.get("blast_radius_size"),
                    "affected_flows_count": telemetry_state.get("affected_flows_count"),
                    "test_coverage_gap": telemetry_state.get("test_coverage_gap"),
                    "test_gaps_count": telemetry_state.get("test_gaps_count"),
                    "semantic_context_schema_version": telemetry_state.get("semantic_context_schema_version", ""),
                    "semantic_context_fallback_reasons": telemetry_state.get("semantic_context_fallback_reasons"),
                    # Phase 7.29 ranking confidence + arbitration (Issue #195).
                    "ranking_confidence_level": telemetry_state.get("ranking_confidence_level"),
                    "ranking_confidence_margin": telemetry_state.get("ranking_confidence_margin"),
                    "ranking_confidence_reasons": telemetry_state.get("ranking_confidence_reasons"),
                    "ranking_choice_path": telemetry_state.get("ranking_choice_path"),
                    "ranking_override": bool(telemetry_state.get("ranking_override", False)),
                    "ranking_arbitrate_effective": telemetry_state.get("ranking_arbitrate_effective"),
                    "lock_resolution": telemetry_state.get("lock_resolution", "absent"),
                    # Issue #204 Slice 5 presentation fallback (closed vocab).
                    "presentation_fallback_reason": telemetry_state.get("presentation_fallback_reason", "none"),
                    # Issue #204 Slice 7: blueprint applied (bool only).
                    "blueprint_applied": bool(telemetry_state.get("blueprint_applied", False)),
                    "hallucination_guard_fired": bool(telemetry_state.get("hallucination_guard_fired", False)),
                    # Issue #204 Slice 10 / D26: remaining presentation observability.
                    "path_class_gate": telemetry_state.get("path_class_gate", "none"),
                    "changelog_antisignal_applied": bool(telemetry_state.get("changelog_antisignal_applied", False)),
                    "scope_normalised_from": telemetry_state.get("scope_normalised_from", "none"),
                    # Issue #204 Slice 5 hotfix: contract-lift breadcrumbs (closed vocab).
                    "contract_lift_applied": bool(telemetry_state.get("contract_lift_applied", False)),
                    "contract_lift_from_semver": telemetry_state.get("contract_lift_from_semver"),
                    # Issue #204 Slice 5.5: contract lifecycle (closed vocab).
                    "contract_locked_semver": telemetry_state.get("contract_locked_semver"),
                    "llm_raw_semver": telemetry_state.get("llm_raw_semver"),
                    "plan_persisted_semver": telemetry_state.get("plan_persisted_semver"),
                    "contract_violation": bool(telemetry_state.get("contract_violation", False)),
                    "plan_normaliser_applied": bool(telemetry_state.get("plan_normaliser_applied", False)),
                    "plan_normaliser_reason": telemetry_state.get("plan_normaliser_reason", "none"),
                    # Phase 7.25 gold parity (absorbed into #195).
                    "gold_mode": telemetry_state.get("gold_mode", "off"),
                    "gold_findings_count": telemetry_state.get("gold_findings_count", 0),
                    "gold_finding_codes": telemetry_state.get("gold_finding_codes"),
                    "gold_blocked": bool(telemetry_state.get("gold_blocked", False)),
                    "gold_regen_attempts": telemetry_state.get("gold_regen_attempts", 0),
                },
                feedback_scores=[
                    {"name": "user_acceptance", "value": feedback_score, "reason": provenance},
                    # Issue #195: derived float at score boundary only — metadata bool remains source of truth.
                    {
                        "name": "ranking_override",
                        "value": 1.0 if bool(telemetry_state.get("ranking_override")) else 0.0,
                        "reason": "ranking_override",
                    },
                    # Issue #204 Slice 5.5: contract_consistent = 1.0 when no violation.
                    {
                        "name": "contract_consistent",
                        "value": (0.0 if bool(telemetry_state.get("contract_violation", False)) else 1.0),
                        "reason": str(telemetry_state.get("plan_normaliser_reason") or "none"),
                    },
                ],
                thread_id=thread_id,
            )
            return {"status": "recorded", "provenance": provenance}

        opik_args = {}
        if state.trace_id:
            opik_args["trace"] = {"id": state.trace_id}
        if state.thread_id:
            if "trace" not in opik_args:
                opik_args["trace"] = {}
            opik_args["trace"]["thread_id"] = state.thread_id

        log_final_commit_telemetry(
            final_commit_message=final_message,
            provenance=provenance.value,
            telemetry_state=state.__dict__,
            opik_args=opik_args if opik_args else None,
        )
        opik.flush_tracker()
        sentry_sdk.flush(timeout=2.0)
        if verbose:
            console.log("Successfully recorded final telemetry to Opik.")
    except Exception as e:
        if verbose:
            console.log(f"Failed to log telemetry to Opik: {e}")

    # Always clear state to prevent stale reads
    clear_telemetry_state(git_dir)
    raise typer.Exit(code=0)


@app.command("evals", help="Manage and run the git-cg evals benchmarking suite")
def evals(
    install: bool = typer.Option(False, "--install", help="Install evaluation dependencies"),
    dashboard: bool = typer.Option(False, "--dashboard", help="Start the Streamlit dashboard"),
    run: bool = typer.Option(False, "--run", help="Run the evaluation benchmark"),
    thinking: bool = typer.Option(False, "--thinking", help="Enable reasoning benchmarks"),
    gen_img: bool = typer.Option(False, "--gen-img", help="Generate static PNGs"),
) -> None:
    """
    Opt-in benchmarking and evaluation suite for git-cg.
    """
    try:
        # Lazy import to prevent slowing down git-cg's core execution
        from git_cg.evals.cli_handler import handle_evals

        handle_evals(
            install=install,
            dashboard=dashboard,
            run=run,
            thinking=thinking,
            gen_img=gen_img,
        )
    except ImportError:
        if install:
            console.print("[yellow]Starting installation of evals dependencies...[/yellow]")
            # We'll implement the actual install logic shortly
        else:
            console.print("[bold red]⚠️ Evals system is not currently installed.[/bold red]")
            console.print("Run [bold cyan]git-cg evals --install[/bold cyan] to download it.")
            raise typer.Exit(code=1) from None


if __name__ == "__main__":
    app()
