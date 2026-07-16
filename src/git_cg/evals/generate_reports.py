import glob
import json
import os

from rich.console import Console

console = Console()


def generate_reports(gen_img: bool = False):
    """
    Parses benchmark history and generates Dual Pipelines:
    - Lite: For Zensical static Github deployment
    - Full: For local Streamlit processing
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    history_dir = os.path.join(base_dir, "results", "history")

    docs_data_dir = os.path.join(base_dir, "docs", "data")
    os.makedirs(docs_data_dir, exist_ok=True)

    lite_path = os.path.join(docs_data_dir, "benchmark_lite.json")
    full_path = os.path.join(base_dir, "results", "benchmark_full.json")

    if not os.path.exists(history_dir):
        console.print("[dim]No benchmark history found. Skipping report generation.[/dim]")
        return

    full_payload = []
    lite_payload = []

    for file_path in glob.glob(os.path.join(history_dir, "*.json")):
        try:
            with open(file_path) as f:
                data = json.load(f)
                full_payload.append(data)

                # Strip raw texts for lite payload
                lite_data = {k: v for k, v in data.items() if k != "raw_outputs"}
                lite_payload.append(lite_data)
        except Exception as e:
            console.print(f"[dim]Failed to read {file_path}: {e}[/dim]")

    # Write Lite Payload
    with open(lite_path, "w") as f:
        json.dump(lite_payload, f, indent=2)
    console.print(f"[green]Generated Lite Benchmark Report:[/green] {lite_path}")

    # Write Full Payload
    with open(full_path, "w") as f:
        json.dump(full_payload, f, indent=2)
    console.print(f"[green]Generated Full Benchmark Report:[/green] {full_path}")

    # Optional image generation
    if gen_img:
        console.print("[yellow]Generating static PNG images...[/yellow]")
        try:
            import matplotlib.pyplot as plt

            # Placeholder image generation logic
            img_path = os.path.join(base_dir, "results", "benchmark_graph.png")
            plt.figure(figsize=(10, 6))
            plt.plot([1, 2, 3], [42.5, 43.1, 44.0], marker="o")
            plt.title("Tokens Per Second Over Time")
            plt.xlabel("Run ID")
            plt.ylabel("TPS")
            plt.savefig(img_path)
            console.print(f"[green]Generated PNG graph:[/green] {img_path}")
        except ImportError:
            console.print("[bold red]matplotlib is not installed. Run with --install to fix.[/bold red]")


if __name__ == "__main__":
    generate_reports(gen_img=True)
