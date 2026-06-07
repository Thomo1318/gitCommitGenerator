import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import NoReturn

from dotenv import load_dotenv

# Load .env fallback immediately
load_dotenv()

# Set opik logging level before importing it
os.environ["OPIK_CONSOLE_LOGGING_LEVEL"] = "ERROR"

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
from git_cg.models import CommitPlan  # noqa: E402
from git_cg.sop import load_sop  # noqa: E402

app = typer.Typer(add_completion=False, help="GitOps AI Commit Generator and Release Automation")
console = Console()

# Only generate for an interactive (empty) or template commit. Everything else
# (-m/-F => "message", merge, squash, --amend/-c/-C => "commit") already has a
# message we must NOT overwrite — critical for safe global-hook operation.
GENERATING_SOURCES: set[str | None] = {None, "", "template"}


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

    api_key = os.environ.get(f"{config.prefix}_API_KEY", "not-needed")
    base_url = os.environ.get(f"{config.prefix}_BASE_URL", config.default_base_url)

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
                f"[yellow]🚀 Local AI server for {engine} is not running. Starting it in a new window...[/yellow]"
            )
            script_path = f"/tmp/start_{engine_lower}.command"
            parsed = urllib.parse.urlparse(base_url)
            port = parsed.port or 8000

            server_cmd = f"mtplx start --port {port}" if engine_lower == "mtplx" else f"omlxd --port {port}"

            with open(script_path, "w") as f:
                f.write("#!/usr/bin/env bash\n")
                f.write(f"echo 'Starting {engine_lower} server...'\n")
                f.write(f"{server_cmd}\n")
                f.write("echo 'Server stopped. You can close this window.'\n")
            os.chmod(script_path, 0o755)

            ret = subprocess.run(["open", "-a", "Ghostty", script_path], stderr=subprocess.DEVNULL)
            if ret.returncode != 0:
                subprocess.run(["open", script_path])

            console.print("Waiting for AI server to become ready", end="")
            for _ in range(60):
                try:
                    req = urllib.request.Request(models_url, method="GET")
                    with urllib.request.urlopen(req, timeout=1) as response:
                        if response.status == 200:
                            server_ready = True
                            console.print("\n[green]✅ AI server is ready![/green]")
                            break
                except urllib.error.URLError, TimeoutError:
                    pass
                console.print(".", end="")
                sys.stdout.flush()
                time.sleep(1)

            if not server_ready:
                _abort(
                    "\n[bold red]❌ Timed out waiting for local AI server.[/bold red]",
                    strict=True,
                )

    openai_client = track_openai(OpenAI(base_url=base_url, api_key=api_key))
    client = instructor.from_openai(openai_client)
    return client


@opik.track(project_name="gitCommitGenerator")
def generate_commit_message(
    client: instructor.Instructor,
    diff_output: str,
    model_name: str,
    system_prompt: str,
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
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Here is the diff:\n\n```diff\n{diff_output}\n```"},
                ],
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


@app.command("commit")
def commit(
    commit_msg_file: str = typer.Argument(..., help="Path to the commit message file"),
    commit_source: str | None = typer.Argument(None, help="Source of the commit message (e.g., 'message', 'template')"),
    extra_args: list[str] | None = typer.Argument(None, help="Any extra arguments passed by git hooks"),
    engine: str = typer.Option(
        os.environ.get("GIT_CG_ENGINE", "omlx"), "--engine", "-e", help="AI engine to use (e.g. omlx, mtplx)"
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
        help="Exit non-zero on failure. Leave OFF for git hooks so a failed "
        "generation never blocks the commit; turn ON for CLI/CI use.",
    ),
):
    """
    Generate an AI commit message based on staged changes.
    """
    if verbose:
        console.log("Starting git-cg...")
        console.log(f"Engine: {engine}")
        console.log(f"Commit Msg File: {commit_msg_file}")
        console.log(f"Commit Source: {commit_source}")

    # hk hook framework passes the file path as the second argument if git provides no source.
    if commit_source and (commit_source == commit_msg_file or commit_source.endswith("COMMIT_EDITMSG")):
        commit_source = None

    # Fix B: never clobber an existing/user-provided message.
    if commit_source not in GENERATING_SOURCES:
        if amend_regenerate and commit_source == "commit":
            if verbose:
                console.log("Amend regeneration explicitly enabled; proceeding.")
        else:
            if verbose:
                console.log(
                    f"Commit source '{commit_source}' indicates an existing message "
                    "(merge/squash/amend/-m). Skipping generation."
                )
            raise typer.Exit(code=0)

    try:
        import shutil

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

    # Assemble the system prompt from the SOP (install-relative resolution).
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

        # 1. Primary Candidates (Top 3 absolute matches)
        primary_candidates = ranked_candidates[:3]

        # 2. Secondary Candidates (Ensure diversity for secondary sub-changes)
        secondary_candidates = []
        seen_groups = {cand.intent_group for cand in primary_candidates}

        for cand in ranked_candidates[3:]:
            if len(secondary_candidates) >= 3:
                break
            # Only inject if it scored reasonably well (avoid hard-vetoed items) and is a distinct group
            if cand.intent_group not in seen_groups and cand.score > 0:
                secondary_candidates.append(cand)
                seen_groups.add(cand.intent_group)

        # If we didn't find enough diverse groups, fill with the next best positive-scoring candidates
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

        # 3. Vocabulary Dictionary (Ultimate fallback to prevent hallucinated emojis)
        vocab = [f"{r.get('intent_id', r.get('code', '').strip(':'))} ({r.get('emoji')})" for r in gitops_matrix]
        candidates_str += "VALID INTENT DICTIONARY (Ultimate Fallback):\n"
        candidates_str += "If NONE of the detailed candidates above fit a secondary change, you MUST select an intent_id from this list. Do NOT invent new intents or emojis:\n"
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
        "CRITICAL: You must invoke the CommitPlan tool EXACTLY ONCE. Do not output multiple tool calls. Put all secondary intents inside the secondary_intents array."
        f"{gitops_matrix_str}"
    )

    try:
        repo_name = os.path.basename(
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        )
        thread_id = f"repo-{repo_name}"
    except Exception:
        thread_id = "default-thread"

    try:
        commit_plan = generate_commit_message(
            client, diff_output, model_name, system_prompt, opik_args={"trace": {"thread_id": thread_id}}
        )
    except Exception as e:
        _abort(f"[bold red]Error generating commit message from AI:[/bold red] {e}", strict=strict)

    mixed_policy = os.environ.get("GIT_CG_MIXED_POLICY", "composite").lower()

    if commit_plan.split_recommended:
        msg = f"\n[bold yellow]⚠️  MIXED COMMIT DETECTED[/bold yellow]\n[yellow]Rationale:[/yellow] {commit_plan.rationale}\n"

        if mixed_policy == "strict":
            console.print(msg)
            _abort(
                "[bold red]Policy is 'strict'. Aborting commit. Please split your changes.[/bold red]", strict=strict
            )

        elif mixed_policy == "split_prompt":
            console.print(msg)
            if sys.stdin.isatty():
                do_split = typer.confirm("Would you like to abort and split these changes?")
                if do_split:
                    _abort("[bold red]Aborting commit so you can split your changes.[/bold red]", strict=strict)
            else:
                if verbose:
                    console.print("[yellow]Non-TTY environment detected; bypassing split_prompt.[/yellow]")

        elif mixed_policy == "warn":
            console.print(msg)
            console.print("[yellow]Policy is 'warn'. Proceeding with composite commit.[/yellow]\n")

    result_string = commit_plan.render()

    if verbose or dry_run:
        console.print(Panel(result_string, title="Generated Commit Message", border_style="green"))

    if not dry_run:
        try:
            with open(commit_msg_file, "w", encoding="utf-8") as f:
                f.write(result_string)
            if verbose:
                console.log(f"Commit message written to {commit_msg_file}")
        except OSError as e:
            _abort(f"[bold red]Error writing to {commit_msg_file}:[/bold red] {e}", strict=strict)

    opik.flush_tracker()


@app.command("sop")
def show_sop():
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
):
    """
    Calculate SemVer bump, inject versions into changed files, and generate Changelog.
    """
    try:
        from git_cg.release import execute_release

        execute_release(dry_run=dry_run, verbose=verbose)
    except ImportError as e:
        console.print(f"[bold red]Error loading release module:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    app()
