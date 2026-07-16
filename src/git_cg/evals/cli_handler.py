import typer
from rich.console import Console

console = Console()


def handle_evals(
    install: bool = False,
    dashboard: bool = False,
    run: bool = False,
    thinking: bool = False,
    gen_img: bool = False,
) -> None:
    """
    Core handler for the evals module.
    """
    if install:
        console.print("[green]Installing evaluation dependencies...[/green]")
        # Installation logic (pip install matplotlib, streamlit, etc) will go here
        raise typer.Exit(code=0)

    if dashboard:
        console.print("[green]Starting Streamlit dashboard...[/green]")
        import os
        import subprocess
        import sys

        dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.py")
        try:
            subprocess.run(["streamlit", "run", dashboard_path], check=True)
        except FileNotFoundError:
            console.print("[bold red]streamlit is not installed. Run with --install to fix.[/bold red]")
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Streamlit exited with error: {e}[/bold red]")
        raise typer.Exit(code=0)

    if run:
        console.print("[green]Starting evaluation benchmark...[/green]")

        # Check if we are already caffeinated to prevent recursion
        import os
        import subprocess
        import sys

        if not os.environ.get("GIT_CG_CAFFEINATED"):
            console.print("[dim]Wrapping execution with caffeinate to prevent system sleep...[/dim]")
            env = os.environ.copy()
            env["GIT_CG_CAFFEINATED"] = "1"
            cmd = ["caffeinate", "-is", sys.executable, *sys.argv]
            try:
                result = subprocess.run(cmd, env=env)
                raise typer.Exit(code=result.returncode)
            except FileNotFoundError:
                console.print("[dim]caffeinate not found. Running normally.[/dim]")

        from git_cg.evals.generate_reports import generate_reports
        from git_cg.evals.run_eval import run_benchmark

        run_benchmark(thinking=thinking)
        generate_reports(gen_img=gen_img)
        raise typer.Exit(code=0)

    # If no flags passed, show help
    console.print("[yellow]Please specify an action (e.g., --run, --dashboard, or --install).[/yellow]")
    raise typer.Exit(code=1)
