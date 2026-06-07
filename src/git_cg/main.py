import json
import os
import subprocess
import sys
from typing import NoReturn

import instructor

os.environ["OPIK_CONSOLE_LOGGING_LEVEL"] = "ERROR"
import opik
import typer
from openai import OpenAI
from opik import opik_context
from opik.integrations.openai import track_openai
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from git_cg.models import Commit
from git_cg.sop import load_sop

app = typer.Typer(add_completion=False, help="GitOps AI Commit Generator and Release Automation")
console = Console()

# Only generate for an interactive (empty) or template commit. Everything else
# (-m/-F => "message", merge, squash, --amend/-c/-C => "commit") already has a
# message we must NOT overwrite — critical for safe global-hook operation.
GENERATING_SOURCES: set[str | None] = {None, "", "template"}


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
    if engine_lower in ("omlx", "mtplx", "mlx"):
        prefix = "MTPLX" if engine_lower == "mtplx" else "OMLX"
        api_key = os.environ.get(f"{prefix}_API_KEY", os.environ.get("OMLX_API_KEY", "not-needed"))
        base_url = os.environ.get(f"{prefix}_BASE_URL", os.environ.get("OMLX_BASE_URL", "http://localhost:8000/v1"))

        openai_client = track_openai(OpenAI(base_url=base_url, api_key=api_key))
        client = instructor.from_openai(openai_client)
        return client
    raise ValueError(f"Unsupported engine: {engine}")


@opik.track(project_name="gitCommitGenerator")
def generate_commit_message(
    client: instructor.Instructor, diff_output: str, model_name: str, system_prompt: str
) -> str:
    """Generate a structured commit message using AI."""
    opik_context.update_current_trace(
        metadata={
            "_opik_graph_definition": {
                "format": "mermaid",
                "data": "graph TD; User[Git Hook] --> App[git-cg]; App --> Instructor[Instructor]; Instructor --> API[LLM API]; API --> Instructor; Instructor --> App; App --> User;",
            }
        }
    )

    commit_result: Commit = client.chat.completions.create(
        model=model_name,
        response_model=Commit,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the diff:\n\n```diff\n{diff_output}\n```"},
        ],
        max_retries=2,
    )
    return commit_result.render()


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

        diff_output = subprocess.check_output(diff_cmd_standard, stderr=subprocess.STDOUT, text=True)
        max_chars = 50000

        if len(diff_output) > max_chars and has_rtk:
            if verbose:
                console.log(f"Standard diff exceeds {max_chars} chars. Falling back to rtk for token compression...")

            diff_cmd_rtk = ["rtk", "git", "diff", "--cached", "--", ".", *diff_cmd_standard[5:]]
            diff_output = subprocess.check_output(diff_cmd_rtk, stderr=subprocess.STDOUT, text=True)

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

    prefix = "MTPLX" if engine.lower() == "mtplx" else "OMLX"
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
        context_parts.append(
            "Use the following reference matrix to select the exact literal unicode emoji and cc_type:\n"
            + json.dumps(gitops_matrix, indent=2)
        )
    if context_parts:
        gitops_matrix_str = "\n\n" + "\n\n".join(context_parts)

    system_prompt = (
        "You are a senior software engineer who writes perfect Conventional Commit messages. "
        "Analyze the provided git diff and generate a structured commit message. "
        "Be concise, use the imperative mood for descriptions, and select the most appropriate emoji and type. "
        "CRITICAL: The final rendered commit header (emoji + type + scope + description) MUST NOT exceed 72 characters in total length."
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
        result_string = generate_commit_message(
            client, diff_output, model_name, system_prompt, opik_args={"trace": {"thread_id": thread_id}}
        )
    except Exception as e:
        _abort(f"[bold red]Error generating commit message from AI:[/bold red] {e}", strict=strict)

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
