import os
import sys
import subprocess
import json
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typing import Optional
import instructor
from openai import OpenAI

from git_cg.models import Commit

app = typer.Typer(add_completion=False, help="GitOps AI Commit Generator and Release Automation")
console = Console()

def get_ai_client(engine: str) -> instructor.Instructor:
    """Initialize the AI client based on the requested engine."""
    if engine.lower() in ("omlx", "mtplx", "mlx"):
        api_key = os.environ.get("OMLX_API_KEY", "not-needed")
        base_url = os.environ.get("OMLX_BASE_URL", "http://localhost:8000/v1")
        
        # Initialize AgentOps Observability
        try:
            import agentops
            agentops.init(
                api_key=os.environ.get('AGENTOPS_API_KEY', '233574f8-620e-44c6-b64c-f25e4156f7b3'),
                default_tags=['git-cg', engine]
            )
        except ImportError:
            pass # AgentOps not installed, skip tracing

        client = instructor.from_openai(
            OpenAI(base_url=base_url, api_key=api_key)
        )
        return client
    else:
        console.print(f"[bold red]Unsupported engine:[/bold red] {engine}")
        sys.exit(1)


@app.command("commit")
def commit(
    commit_msg_file: str = typer.Argument(..., help="Path to the commit message file"),
    commit_source: Optional[str] = typer.Argument(None, help="Source of the commit message (e.g., 'message', 'template')"),
    extra_args: Optional[list[str]] = typer.Argument(None, help="Any extra arguments passed by git hooks"),
    engine: str = typer.Option("omlx", "--engine", "-e", help="AI engine to use (e.g. omlx, mtplx)"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Do not write the commit message, just print it"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """
    Generate an AI commit message based on staged changes.
    """
    if verbose:
        console.log(f"Starting git-cg...")
        console.log(f"Engine: {engine}")
        console.log(f"Commit Msg File: {commit_msg_file}")
        console.log(f"Commit Source: {commit_source}")

    try:
        import shutil
        has_rtk = shutil.which("rtk") is not None
        
        diff_cmd_standard = [
            "git", "diff", "--cached", "--", ".", 
            ":(exclude)*.lock", 
            ":(exclude)*-lock.json", 
            ":(exclude)*-lock.yaml",
            ":(exclude)*.lockb",
            ":(exclude)*zensical*",
            ":(exclude)*auxly*"
        ]
        
        diff_output = subprocess.check_output(diff_cmd_standard, stderr=subprocess.STDOUT, text=True)
        max_chars = 50000
        
        if len(diff_output) > max_chars and has_rtk:
            if verbose:
                console.log(f"Standard diff exceeds {max_chars} chars. Falling back to rtk for token compression...")
            
            diff_cmd_rtk = ["rtk", "git", "diff", "--cached", "--", "."] + diff_cmd_standard[5:]
            diff_output = subprocess.check_output(diff_cmd_rtk, stderr=subprocess.STDOUT, text=True)
            
        if len(diff_output) > max_chars:
            diff_output = diff_output[:max_chars] + "\n\n... [DIFF TRUNCATED DUE TO LENGTH] ..."
            if verbose:
                console.log(f"Diff truncated to {max_chars} chars.")
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error getting git diff:[/bold red] {e.output}")
        sys.exit(1)
        
    if not diff_output.strip():
        console.print("[yellow]No staged changes found. Aborting commit message generation.[/yellow]")
        sys.exit(0)
        
    if verbose:
        console.log(f"Extracted git diff ({len(diff_output)} characters).")

    client = get_ai_client(engine)
    
    trace_context = None
    try:
        import agentops
        trace_context = agentops.start_trace("git-cg-commit", tags={"engine": engine, "dry_run": str(dry_run)})
    except ImportError:
        pass
    
    if verbose:
        console.log(f"AI Client initialized. Calling {engine} to generate commit message...")

    model_name = os.environ.get("OMLX_MODEL", "")
    if not model_name:
        try:
            models = client.models.list()
            if models.data:
                model_name = models.data[0].id
            else:
                model_name = "default"
        except Exception:
            model_name = "default"
            
    if verbose:
        console.log(f"Using model: {model_name}")

    gitops_matrix_str = ""
    sop_path = os.path.join(os.getcwd(), "config", "gitops_agent_sop.json")
    if not os.path.exists(sop_path):
        sop_path = os.path.join(os.getcwd(), "config", "gitCommitGenerator", "config", "gitops_agent_sop.json")
        
    if os.path.exists(sop_path):
        try:
            with open(sop_path, "r") as f:
                sop_data = json.load(f)
                gitops_matrix = sop_data.get("gitmoji_reference_matrix", [])
                specs = sop_data.get("specifications_and_standards", {})
                workflow = sop_data.get("agentic_commit_workflow", {})
                
                context_parts = []
                if specs:
                    context_parts.append("Specifications and Standards:\n" + json.dumps(specs, indent=2))
                if workflow:
                    context_parts.append("Agentic Commit Workflow:\n" + json.dumps(workflow, indent=2))
                if gitops_matrix:
                    context_parts.append("Use the following reference matrix to select the exact literal unicode emoji and cc_type:\n" + json.dumps(gitops_matrix, indent=2))
                
                if context_parts:
                    gitops_matrix_str = "\n\n" + "\n\n".join(context_parts)
        except Exception as e:
            if verbose:
                console.log(f"Could not load gitops matrix: {e}")

    try:
        commit: Commit = client.chat.completions.create(
            model=model_name,
            response_model=Commit,
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "You are a senior software engineer who writes perfect Conventional Commit messages. "
                        "Analyze the provided git diff and generate a structured commit message. "
                        "Be concise, use the imperative mood for descriptions, and select the most appropriate emoji and type. "
                        "CRITICAL: The final rendered commit header (emoji + type + scope + description) MUST NOT exceed 72 characters in total length."
                        f"{gitops_matrix_str}"
                    )
                },
                {"role": "user", "content": f"Here is the diff:\n\n```diff\n{diff_output}\n```"}
            ],
            max_retries=2
        )
    except Exception as e:
        console.print(f"[bold red]Error generating commit message from AI:[/bold red] {e}")
        try:
            import agentops
            if trace_context:
                agentops.end_trace(trace_context, end_state="Fail")
            agentops.end_session('Fail')
        except ImportError:
            pass
        sys.exit(1)

    result_string = commit.render()
    
    if verbose or dry_run:
        console.print(Panel(result_string, title="Generated Commit Message", border_style="green"))
        
    if not dry_run:
        try:
            with open(commit_msg_file, "w") as f:
                f.write(result_string)
            if verbose:
                console.log(f"Commit message written to {commit_msg_file}")
        except Exception as e:
            console.print(f"[bold red]Error writing to {commit_msg_file}:[/bold red] {e}")
            try:
                import agentops
                if trace_context:
                    agentops.end_trace(trace_context, end_state="Fail")
                agentops.end_session('Fail')
            except ImportError:
                pass
            sys.exit(1)

    try:
        import agentops
        if trace_context:
            agentops.end_trace(trace_context, end_state="Success")
        agentops.end_session('Success')
    except ImportError:
        pass


@app.command("sop")
def show_sop():
    """Display the GitOps SOP matrices and workflows."""
    sop_path = os.path.join(os.getcwd(), "config", "gitops_agent_sop.json")
    if not os.path.exists(sop_path):
        sop_path = os.path.join(os.getcwd(), "config", "gitCommitGenerator", "config", "gitops_agent_sop.json")
        
    if not os.path.exists(sop_path):
        console.print(f"[red]Could not locate gitops_agent_sop.json at {sop_path}[/red]")
        sys.exit(1)
        
    with open(sop_path, "r") as f:
        data = json.load(f)
        
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
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Print changes without modifying files or executing git tags"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
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
