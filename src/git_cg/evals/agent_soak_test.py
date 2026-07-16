"""
agent_soak_test.py

A script designed for Pitchfork background agents to continuously execute
the git-cg evaluation suite without blocking the user's IDE.
"""

import os
import subprocess
import time

from rich.console import Console

console = Console()


def run_soak_test(iterations: int = 5, delay_seconds: int = 60):
    """
    Runs the git-cg evals module multiple times in the background.
    """
    console.print(f"[bold magenta]Starting Pitchfork Soak Test ({iterations} iterations)[/bold magenta]")

    # We locate the entry point
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    main_script = os.path.join(base_dir, "src", "git_cg", "main.py")

    for i in range(1, iterations + 1):
        console.print(f"[cyan]Iteration {i}/{iterations}...[/cyan]")
        try:
            # We run the evals via subprocess.
            # We assume `python -m git_cg main evals --run` or similar works,
            # but we can just invoke it directly.
            subprocess.run(["python", main_script, "evals", "--run"], check=True)
            console.print(f"[green]Iteration {i} complete.[/green]")
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Iteration {i} failed: {e}[/bold red]")
            break

        if i < iterations:
            console.print(f"[dim]Sleeping for {delay_seconds} seconds before next run...[/dim]")
            time.sleep(delay_seconds)

    console.print("[bold magenta]Soak test finished.[/bold magenta]")


if __name__ == "__main__":
    # Usually executed by a background pitchfork agent
    run_soak_test()
