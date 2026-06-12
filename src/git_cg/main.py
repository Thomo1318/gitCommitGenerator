import contextlib
import enum
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Annotated, NoReturn

from dotenv import load_dotenv

# Load .env fallback immediately
load_dotenv()

# Set opik logging level before importing it
os.environ["OPIK_CONSOLE_LOGGING_LEVEL"] = "INFO"
# Increase logging level to reduce console spam from Opik
os.environ["OPIK_CONSOLE_LOGGING_LEVEL"] = os.environ.get("OPIK_CONSOLE_LOGGING_LEVEL", "error")

import instructor  # noqa: E402
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
    format_issue_reference_status,
    format_regeneration_guidance_status,
    prompt_issue_number,
    prompt_issue_reference_type,
    prompt_regeneration_guidance,
    prompt_with_gum,
)
from git_cg.models import CommitPlan, IssueReference, IssueReferenceKind  # noqa: E402
from git_cg.secrets import resolve_secret  # noqa: E402
from git_cg.sop import load_sop  # noqa: E402

app = typer.Typer(
    add_completion=False,
    help="GitOps AI Commit Generator and Release Automation",
    invoke_without_command=True,
    no_args_is_help=False,
)
console = Console()

# Only generate for an interactive (empty) or template commit. Everything else
# (-m/-F => "message", merge, squash, --amend/-c/-C => "commit") already has a
# message we must NOT overwrite — critical for safe global-hook operation.
GENERATING_SOURCES: set[str | None] = {None, "", "template"}


class ReviewStateMutationResult(enum.StrEnum):
    """Possible outcomes when mutating issue-reference state during review."""

    ADDED = "added"
    DUPLICATE = "duplicate"
    CONFLICTING_ISSUE_NUMBER = "conflicting_issue_number"


@dataclass
class ReviewState:
    """A deterministic container for review-related state, holding the CommitPlan and associated review metadata."""

    commit_plan: CommitPlan
    issue_references: list[IssueReference] = field(default_factory=list)
    regeneration_guidance: str | None = None

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
        Add an IssueReference to the review state using deterministic idempotency and conflict rules.

        Returns:
            ReviewStateMutationResult: `ADDED` when appended, `DUPLICATE` when already present,
            or `CONFLICTING_ISSUE_NUMBER` when the issue number already exists with a different verb.
        """
        existing_issue_reference = self.get_issue_reference_by_issue_number(issue_reference.issue_number)
        if existing_issue_reference is not None:
            if existing_issue_reference == issue_reference:
                return ReviewStateMutationResult.DUPLICATE
            return ReviewStateMutationResult.CONFLICTING_ISSUE_NUMBER

        self.issue_references.append(issue_reference)
        return ReviewStateMutationResult.ADDED

    def set_regeneration_guidance(self, guidance: str) -> bool:
        """Store normalized regeneration guidance and return True when the stored value changes."""
        normalized_guidance = " ".join(guidance.split()).strip()
        if not normalized_guidance:
            return False
        if self.regeneration_guidance == normalized_guidance:
            return False
        self.regeneration_guidance = normalized_guidance
        return True

    def clear_regeneration_guidance(self) -> bool:
        """Clear stored regeneration guidance and return True when guidance was present."""
        if self.regeneration_guidance is None:
            return False
        self.regeneration_guidance = None
        return True


@dataclass
class EngineConfig:
    prefix: str
    default_base_url: str


ENGINE_REGISTRY: dict[str, EngineConfig] = {
    "omlx": EngineConfig(prefix="OMLX", default_base_url="http://127.0.0.1:8000/v1"),
    "mtplx": EngineConfig(prefix="MTPLX", default_base_url="http://127.0.0.1:8000/v1"),
    "openai": EngineConfig(prefix="OPENAI", default_base_url="https://api.openai.com/v1"),
}


def _abort(message: str, *, strict: bool, code: int = 1) -> NoReturn:
    """Print an error and exit.

    In non-strict (hook) mode we exit 0 so a failed generation NEVER blocks the
    user's commit — git simply proceeds with its default message.
    """
    console.print(message)
    opik.flush_tracker()
    raise typer.Exit(code=code if strict else 0)


def get_ai_client(engine: str) -> instructor.Instructor:
    """Initialize the AI client based on the requested engine."""
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
        except urllib.error.URLError, TimeoutError:
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

            cmd_args = (
                shlex.split(f"{mtplx_path} quickstart --profile sustained --port {port}")
                if engine_lower == "mtplx"
                else shlex.split(f"{omlxd_path} --port {port}")
            )

            log_path = f"/tmp/{engine_lower}_server.log"
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
                    except urllib.error.URLError, TimeoutError, Exception:
                        pass

                    time.sleep(1)

            if not server_ready:
                _abort(
                    f"\n[bold red]❌ Timed out waiting for local AI server. Check {log_path} for details.[/bold red]",
                    strict=True,
                )

    openai_client = track_openai(OpenAI(base_url=base_url, api_key=api_key))
    client = instructor.from_openai(openai_client)
    return client


def build_generation_messages(
    system_prompt: str,
    diff_output: str,
    regeneration_guidance: str | None = None,
) -> list[dict[str, str]]:
    """Build the chat messages used for commit generation, optionally adding separate user-authored regeneration guidance."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Here is the diff:\n\n```diff\n{diff_output}\n```"},
    ]
    if regeneration_guidance:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Regeneration guidance for this retry only: "
                    f"{regeneration_guidance}\n\n"
                    "Use this guidance to improve framing and emphasis, but do not treat it as final commit content."
                ),
            }
        )
    return messages


@opik.track(project_name="gitCommitGenerator")
def generate_commit_message(
    client: instructor.Instructor,
    diff_output: str,
    model_name: str,
    system_prompt: str,
    regeneration_guidance: str | None = None,
    **kwargs,
) -> CommitPlan:
    """Generate a structured commit message using AI."""
    opik_context.update_current_trace(
        metadata={
            "_opik_graph_definition": {
                "format": "mermaid",
                "data": "graph TD; User[Git Hook] --> App[git-cg]; App --> Instructor[Instructor]; Instructor --> API[LLM API]; API --> Instructor; Instructor --> App; App --> User;",
            }
        }
    )
    import time

    import openai

    max_retries = 10
    for attempt in range(max_retries):
        try:
            commit_result: CommitPlan = client.chat.completions.create(
                model=model_name,
                response_model=CommitPlan,
                messages=build_generation_messages(system_prompt, diff_output, regeneration_guidance),
                max_retries=2,
                parallel_tool_calls=False,
            )
            return commit_result
        except openai.APIConnectionError:
            if attempt == max_retries - 1:
                raise
            console.print(
                f"[yellow]Waiting for local AI server to load model weights (attempt {attempt + 1}/{max_retries})...[/yellow]"
            )
            time.sleep(10)


def build_system_prompt(
    diff_output: str,
    verbose: bool = False,
    regeneration_guidance: str | None = None,
) -> str:
    """Assemble the system prompt from the SOP, noting that optional regeneration guidance may be supplied separately."""
    sop_data = load_sop()
    if not sop_data and verbose:
        console.log("[yellow]SOP could not be located; generating without matrix enforcement.[/yellow]")

    gitops_matrix_str = ""
    context_parts = []
    specs = sop_data.get("specifications_and_standards", {})
    workflow = sop_data.get("agentic_commit_workflow", {})
    gitops_matrix = sop_data.get("gitmoji_reference_matrix", [])
    if specs:
        context_parts.append("Specifications and Standards:\n" + json.dumps(specs, indent=2))
    if workflow:
        context_parts.append("Agentic Commit Workflow:\n" + json.dumps(workflow, indent=2))

    if gitops_matrix:
        if verbose:
            console.log("Analyzing diff signals and ranking intents...")

        signals = extract_diff_signals(diff_output)
        ranked_candidates = rank_commit_intents(signals, gitops_matrix)

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
                candidates_str += f"   Evidence: {', '.join(cand.evidence[:3])}\n"
            candidates_str += "\n"

        if secondary_candidates:
            candidates_str += "SECONDARY CANDIDATES (For distinct sub-changes):\n"
            for i, cand in enumerate(secondary_candidates, 1):
                candidates_str += f"{i}. {cand.emoji} {cand.cc_type} ({cand.intent_id})\n"
                candidates_str += f"   Description: {cand.description}\n"
                if cand.evidence:
                    candidates_str += f"   Evidence: {', '.join(cand.evidence[:3])}\n"
                candidates_str += "\n"

        vocab = [f"{r.get('intent_id', r.get('code', '').strip(':'))} ({r.get('emoji')})" for r in gitops_matrix]
        candidates_str += "VALID INTENT DICTIONARY (Ultimate Fallback):\n"
        candidates_str += (
            "If NONE of the detailed candidates above fit a secondary change, you MUST select an intent_id from this list. "
            "Do NOT invent new intents or emojis:\n"
        )
        candidates_str += ", ".join(vocab) + "\n"

        context_parts.append(candidates_str.strip())
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
        "CRITICAL: If regeneration guidance is provided separately in a later user message, use it to improve framing and emphasis, but do not treat it as final commit content or trailer text."
        f"{gitops_matrix_str}"
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
    Prompt the user to add a structured issue reference to the given review state.

    Prompts for a reference type and an issue number; returns a constructed IssueReference
    when both are provided, or None if the user cancels or selects the back option.

    Parameters:
        review_state (ReviewState): The current review state; accepted for orchestration symmetry.

    Returns:
        IssueReference or None: An IssueReference when the user supplies a valid type and number,
        `None` if the operation was cancelled or the user selected "Back".
    """
    reference_type = prompt_issue_reference_type()
    if reference_type in (None, "Back"):
        return None

    issue_number = prompt_issue_number()
    if issue_number is None:
        return None

    return IssueReference(kind=IssueReferenceKind(reference_type), issue_number=issue_number)


def _build_regeneration_guidance(review_state: ReviewState) -> str | None:
    """Prompt the user for regeneration guidance to steer the next AI retry."""
    return prompt_regeneration_guidance(review_state.regeneration_guidance)


def _interactive_review(commit_msg_file: str, review_state: ReviewState, *, verbose: bool, strict: bool) -> str:
    """
    Display an interactive review UI for the generated commit and allow adding review metadata or editing before finalising.

    Parameters:
        commit_msg_file (str): Path to the commit message file that will be updated if the message changes.
        review_state (ReviewState): Current review state containing the generated CommitPlan and attached IssueReference(s).
        verbose (bool): Enable additional informational messages when interactive UI is unavailable.
        strict (bool): Passed through to the commit-message writer to control strict write/abort behaviour.

    Returns:
        action (str): The action chosen by the user (for example "Commit", "Edit", "Regenerate", "Cancel"). Metadata actions such as adding issue references or regeneration guidance are processed in-place and the loop continues until a terminating action is selected.
    """
    emit_terminal_bell()

    while True:
        result_string = review_state.render()
        status_text = "\n".join(
            [
                format_issue_reference_status(review_state.issue_references),
                format_regeneration_guidance_status(review_state.regeneration_guidance),
            ]
        )
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
            else:
                existing_issue_reference = review_state.get_issue_reference_by_issue_number(
                    issue_reference.issue_number
                )
                existing_issue_reference_text = (
                    str(existing_issue_reference)
                    if existing_issue_reference
                    else f"issue #{issue_reference.issue_number}"
                )
                console.print(
                    "[yellow]"
                    f"{existing_issue_reference_text} is already attached to this review state. "
                    "Changing the verb for an existing issue reference is deferred for this phase. "
                    "Use Edit for manual changes."
                    "[/yellow]"
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

        if action == "Edit":
            editor = os.environ.get("EDITOR", "nano")
            subprocess.run([editor, commit_msg_file], check=False)
        return action


def _interactive_review_dry_run(review_state: ReviewState, *, verbose: bool, strict: bool) -> str:
    """
    Present the current ReviewState to the user via a temporary preview file and run the interactive review flow.

    Writes the rendered commit message from `review_state` to a temporary file, invokes the same interactive review routine used for actual commits, and ensures the temporary file is removed afterwards.

    Parameters:
        review_state (ReviewState): The review state containing the generated CommitPlan and any issue references to preview.
        verbose (bool): If True, enable verbose logging within the interactive flow.
        strict (bool): If True, treat interactive failures as strict errors (affects behaviour in the interactive routine).

    Returns:
        str: The action chosen by the user (for example `"Regenerate"`, `"Edit"`, `"Commit"`, `"Cancel"`).
    """
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, suffix=".git-cg-preview.txt"
        ) as temp_file:
            temp_file.write(review_state.render())
            temp_path = temp_file.name
        return _interactive_review(temp_path, review_state, verbose=verbose, strict=strict)
    finally:
        if temp_path:
            with contextlib.suppress(OSError):
                os.unlink(temp_path)


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
) -> bool:
    """
    Generate a commit message from staged changes using an AI client and write it to a commit message file, optionally running an interactive review or dry-run.

    This function:
    - extracts the staged git diff (with token-compression via `rtk` when available) and truncates it if very large;
    - initialises an AI client and model, builds a system prompt, and requests a CommitPlan from the model;
    - handles mixed-change policies (warn/strict/split_prompt) based on `GIT_CG_MIXED_POLICY`;
    - renders a deterministic ReviewState and either writes the commit message file or presents interactive review/dry-run UI flows that can regenerate or cancel;
    - honours `amend_regenerate` for commits originating from amend flows and uses `strict` to decide exit codes for aborts.

    Parameters:
        commit_msg_file (str): Path to the commit message file to write when not in dry-run.
        commit_source (str | None): Origin of the commit (e.g. "commit", file path, or None). Values outside GENERATING_SOURCES will skip generation unless `amend_regenerate` permits.
        extra_args (list[str] | None): Additional command-line args (present for signature compatibility; not interpreted here).
        engine (str): Engine key to select the AI backend (matches keys in ENGINE_REGISTRY).
        dry_run (bool): If true, do not write to `commit_msg_file`; allow interactive dry-run flows instead.
        verbose (bool): Enable verbose logging to the global console.
        amend_regenerate (bool): When true, allow regeneration for amend-origin commits even if `commit_source` would normally skip generation.
        strict (bool): When true, aborts raise non-zero exit codes; when false, aborts exit with code 0 to avoid blocking git hooks.
        interactive (bool): If true and a TTY is available, present interactive review UI which can add issue references, edit, regenerate, or cancel.

    Returns:
        bool: `True` when commit message generation (and any interactive flow) completed successfully.
    """
    if verbose:
        console.log("Starting git-cg...")
        console.log(f"Engine: {engine}")
        console.log(f"Commit Msg File: {commit_msg_file}")
        console.log(f"Commit Source: {commit_source}")
        console.log(f"Interactive Mode: {interactive}")

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

    try:
        has_rtk = shutil.which("rtk") is not None
        diff_cmd_standard = [
            "git",
            "diff",
            "--cached",
            "--",
            ".",
            ":(exclude)*.lock",
            ":(exclude)*-lock.json",
            ":(exclude)*-lock.yaml",
            ":(exclude)*.lockb",
            ":(exclude)*zensical*",
            ":(exclude)*auxly*",
        ]
        max_chars = 50000

        if has_rtk:
            if verbose:
                console.log("Using rtk for token compression...")
            try:
                diff_cmd_rtk = ["rtk", "git", "diff", "--cached", "--", ".", *diff_cmd_standard[5:]]
                diff_output = subprocess.check_output(diff_cmd_rtk, stderr=subprocess.STDOUT, text=True)
            except subprocess.CalledProcessError as e:
                if verbose:
                    console.log(f"rtk failed ({e}). Falling back to standard diff.")
                diff_output = subprocess.check_output(diff_cmd_standard, stderr=subprocess.STDOUT, text=True)
        else:
            diff_output = subprocess.check_output(diff_cmd_standard, stderr=subprocess.STDOUT, text=True)

        if len(diff_output) > max_chars:
            diff_output = diff_output[:max_chars] + "\n\n... [DIFF TRUNCATED DUE TO LENGTH] ..."
            if verbose:
                console.log(f"Diff truncated to {max_chars} chars.")
    except subprocess.CalledProcessError as e:
        _abort(f"[bold red]Error getting git diff:[/bold red] {e.output}", strict=strict)

    if not diff_output.strip():
        console.print("[yellow]No staged changes found. Aborting commit message generation.[/yellow]")
        raise typer.Exit(code=0)

    if verbose:
        console.log(f"Extracted git diff ({len(diff_output)} characters).")

    try:
        client = get_ai_client(engine)
    except ValueError as e:
        _abort(f"[bold red]{e}[/bold red]", strict=strict)

    if verbose:
        console.log(f"AI Client initialized. Calling {engine} to generate commit message...")

    engine_config = ENGINE_REGISTRY.get(engine.lower())
    prefix = engine_config.prefix if engine_config else "OMLX"
    model_name = os.environ.get(f"{prefix}_MODEL", os.environ.get("OMLX_MODEL", ""))
    if not model_name:
        try:
            models = client.models.list()
            model_name = models.data[0].id if models.data else "default"
        except Exception:
            model_name = "default"

    if verbose:
        console.log(f"Using model: {model_name}")

    issue_references: list[IssueReference] = []
    regeneration_guidance: str | None = None

    try:
        repo_name = os.path.basename(
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        )
        thread_id = f"repo-{repo_name}"
    except Exception:
        thread_id = "default-thread"

    while True:
        system_prompt = build_system_prompt(
            diff_output,
            verbose,
            regeneration_guidance=regeneration_guidance,
        )

        try:
            with console.status(
                f"[bold cyan]Generating AI commit message with {model_name}... (this may take 30-90s locally)[/bold cyan]",
                spinner="dots",
            ):
                commit_plan = generate_commit_message(
                    client,
                    diff_output,
                    model_name,
                    system_prompt,
                    regeneration_guidance=regeneration_guidance,
                    opik_args={"trace": {"thread_id": thread_id}},
                )
        except Exception as e:
            _abort(f"[bold red]Error generating commit message from AI:[/bold red] {e}", strict=strict)

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
                )
            if mixed_policy == "warn":
                console.print(msg)
                console.print("[yellow]Policy is 'warn'. Proceeding with composite commit.[/yellow]\n")
            elif mixed_policy == "split_prompt" and verbose:
                console.print(msg)
                console.print(
                    "[yellow]split_prompt requested; this implementation keeps hook/default mode non-interactive. Use git-cg -i for review.[/yellow]"
                )

        review_state = ReviewState(
            commit_plan=commit_plan,
            issue_references=list(issue_references),
            regeneration_guidance=regeneration_guidance,
        )
        result_string = review_state.render()
        if verbose or dry_run:
            console.print(Panel(result_string, title="Generated Commit Message", border_style="green"))

        if dry_run:
            should_interact = interactive and can_open_tty()
            if interactive and not should_interact and verbose:
                console.log(
                    "[yellow]Interactive mode requested but /dev/tty is unavailable. Proceeding non-interactively.[/yellow]"
                )
            if should_interact:
                action = _interactive_review_dry_run(review_state, verbose=verbose, strict=strict)
                issue_references = list(review_state.issue_references)
                regeneration_guidance = review_state.regeneration_guidance
                if action == "Regenerate":
                    console.print("\n[yellow]Regenerating commit message...[/yellow]")
                    continue
                if action == "Cancel":
                    _abort("\n[bold red]Dry-run cancelled by user.[/bold red]", strict=strict)
            break

        _write_commit_message(commit_msg_file, result_string, strict=strict, verbose=verbose)

        should_interact = interactive and can_open_tty()
        if interactive and not should_interact and verbose:
            console.log(
                "[yellow]Interactive mode requested but /dev/tty is unavailable. Proceeding non-interactively.[/yellow]"
            )

        if should_interact:
            action = _interactive_review(commit_msg_file, review_state, verbose=verbose, strict=strict)
            issue_references = list(review_state.issue_references)
            regeneration_guidance = review_state.regeneration_guidance
            if action == "Regenerate":
                console.print("\n[yellow]Regenerating commit message...[/yellow]")
                continue
            if action == "Cancel":
                _abort("\n[bold red]Commit aborted by user.[/bold red]", strict=strict)
            break

        break

    opik.flush_tracker()
    return True


def _apply_standalone_commit(commit_msg_file: str, *, strict: bool) -> None:
    try:
        result = subprocess.run(["git", "commit", "-F", commit_msg_file], check=False)
        if result.returncode != 0:
            _abort("[bold red]git commit failed while applying generated commit message.[/bold red]", strict=strict)
    except FileNotFoundError as e:
        _abort(f"[bold red]Unable to execute git commit:[/bold red] {e}", strict=strict)


@app.callback()
def main_callback(
    ctx: typer.Context,
    interactive: Annotated[
        bool,
        typer.Option("--interactive", "-i", help="Enable terminal-native interactive review via gum."),
    ] = False,
    engine: Annotated[
        str,
        typer.Option("--engine", "-e", help="AI engine to use when running git-cg directly."),
    ] = os.environ.get("GIT_CG_ENGINE") or "mtplx",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-d", help="Generate and print the commit message without applying a commit."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output."),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Exit non-zero on failure for standalone CLI use."),
    ] = True,
) -> None:
    """Run git-cg directly with non-interactive default behavior.

    When invoked without a subcommand, git-cg generates a commit message from the
    staged diff and applies `git commit` automatically. Use `-i` to opt into the
    terminal-native review flow via gum.
    """
    if ctx.invoked_subcommand is not None or ctx.resilient_parsing:
        return

    commit_msg_file = os.path.join(".git", "COMMIT_EDITMSG")
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
    )
    if not dry_run:
        _apply_standalone_commit(commit_msg_file, strict=strict)
    raise typer.Exit(code=0)


@app.command("commit")
def commit(
    commit_msg_file: str = typer.Argument(..., help="Path to the commit message file"),
    commit_source: str | None = typer.Argument(None, help="Source of the commit message (e.g., 'message', 'template')"),
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
    )


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
) -> None:
    """Calculate SemVer bump, inject versions into changed files, and generate Changelog."""
    try:
        from git_cg.release import execute_release

        execute_release(dry_run=dry_run, verbose=verbose)
    except ImportError as e:
        console.print(f"[bold red]Error loading release module:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    app()
