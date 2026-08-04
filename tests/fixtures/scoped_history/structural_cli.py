import typer

app = typer.Typer()


@app.command()
def run(verbose: bool = False) -> None:
    """Run the tool."""
    print(verbose)
