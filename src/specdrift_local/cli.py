from __future__ import annotations

import typer
from rich.console import Console

from specdrift_local.dashboard import benchmark_summary, build_dashboard
from specdrift_local.runner import export_demo_pack, init_demo, score_suite, verify_outputs

app = typer.Typer(help="Local API spec drift and agent-callability scoreboard.")
console = Console()


@app.command("init-demo")
def init_demo_command(force: bool = typer.Option(False, "--force")) -> None:
    console.print_json(data=init_demo(force=force))


@app.command("score")
def score_command(iterations: int = typer.Option(20, min=1, max=1000)) -> None:
    console.print_json(score_suite(iterations=iterations).model_dump_json(indent=2))


@app.command("verify")
def verify_command() -> None:
    report = verify_outputs()
    console.print_json(data=report)
    if not report["passed"]:
        raise typer.Exit(1)


@app.command("dashboard")
def dashboard_command() -> None:
    console.print(str(build_dashboard()))


@app.command("benchmark")
def benchmark_command() -> None:
    console.print_json(data=benchmark_summary())


@app.command("export-demo-pack")
def export_demo_pack_command() -> None:
    console.print(str(export_demo_pack()))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
