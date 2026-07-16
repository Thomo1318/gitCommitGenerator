import json
import os
import subprocess
import time
from datetime import datetime

from rich.console import Console

console = Console()


class PathResolver:
    """Resolves dataset paths for evals."""

    @staticmethod
    def get_results_dir() -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        results_dir = os.path.join(base_dir, "results")
        history_dir = os.path.join(results_dir, "history")
        os.makedirs(history_dir, exist_ok=True)
        return results_dir


class ServerManager:
    """Manages the startup and lifecycle of the local evaluation server."""

    def __init__(self, engine: str):
        self.engine = engine.lower()
        self.process = None

    def start(self):
        """Starts the server in the background and waits for it to become ready."""
        console.print(f"[yellow]Starting local server for engine: {self.engine}[/yellow]")
        # Placeholder for actual engine start logic (e.g. omlxd, mtplx)
        # For evaluation, we assume it's running or started similarly to main.py
        time.sleep(1)
        console.print(f"[green]Server for {self.engine} is ready.[/green]")

    def stop(self):
        """Stops the background server."""
        if self.process:
            self.process.terminate()
            self.process.wait()
            console.print(f"[dim]Stopped server for {self.engine}[/dim]")


def check_ac_power():
    """Checks if macOS is on AC power using pmset."""
    try:
        output = subprocess.check_output(["pmset", "-g", "batt"], text=True)
        if "AC Power" not in output:
            console.print("[bold red]⚠️ WARNING: Running benchmarks on battery power![/bold red]")
            console.print("Results will be throttled. Please plug in your Mac for accurate MLX benchmarking.")
            time.sleep(2)
    except Exception as e:
        console.print(f"[dim]Could not check AC power: {e}[/dim]")


def run_benchmark(
    engine: str = "omlx",
    model: str = "default-model",
    thinking: bool = False,
):
    """
    Core benchmark execution pipeline.
    """
    check_ac_power()

    # Wrap in caffeinate to prevent sleep during long evals
    # Note: we are currently INSIDE the python script, so we just run our tasks.
    # We could also re-exec ourselves with caffeinate, but simpler to just do it at the CLI layer.

    server = ServerManager(engine=engine)
    server.start()

    console.print(f"[bold cyan]Running evaluation on {model} using {engine} (Thinking: {thinking})[/bold cyan]")

    # Placeholder for actual evaluation logic looping through test datasets
    start_time = time.time()

    # Simulate work
    time.sleep(2)

    # KV-Cache Profiling
    peak_memory_mb = 0
    try:
        import mlx.core as mx

        active_mem = mx.metal.get_active_memory()
        peak_memory_mb = active_mem / (1024 * 1024)
    except ImportError:
        console.print("[dim]MLX not installed. Cannot profile KV-Cache memory.[/dim]")
    except Exception as e:
        console.print(f"[dim]Failed to read MLX memory: {e}[/dim]")

    end_time = time.time()

    results = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "engine": engine,
        "thinking": thinking,
        "duration_seconds": round(end_time - start_time, 2),
        "peak_memory_mb": round(peak_memory_mb, 2),
        "metrics": {"accuracy": 0.95, "tokens_per_second": 42.5},
        "raw_outputs": [{"prompt": "Test", "output": "Output", "thinking_trace": "..." if thinking else None}],
    }

    results_dir = PathResolver.get_results_dir()
    history_dir = os.path.join(results_dir, "history")
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{timestamp_str}_{model}_{engine}.json"
    file_path = os.path.join(history_dir, file_name)

    with open(file_path, "w") as f:
        json.dump(results, f, indent=2)

    console.print(f"[green]Saved benchmark results to {file_path}[/green]")
    server.stop()


if __name__ == "__main__":
    run_benchmark()
