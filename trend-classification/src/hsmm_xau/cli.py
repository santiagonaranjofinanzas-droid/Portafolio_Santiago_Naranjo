from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import typer

from .config import load_config, resolve_path
from .data import add_gap_segments, audit_ticks, bar_quality, build_bars_for_symbol, join_context
from .equilibrium import add_equilibrium
from .features import build_features
from .labels import add_all_labels
from .reporting import create_report
from .shadow import infer_latest
from .walkforward import run_walk_forward

app = typer.Typer(no_args_is_help=True, help="Causal XAUUSD HSMM research pipeline")


def _artifacts(cfg: dict) -> Path:
    path = resolve_path(cfg, "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


@app.command()
def audit(config: Path = Path("configs/research_v1.yaml")) -> None:
    cfg = load_config(config)
    symbols = [cfg["data"]["primary_symbol"], *cfg["data"]["context_symbols"]]
    report = audit_ticks(resolve_path(cfg, "ticks"), symbols, _artifacts(cfg) / "data_audit.json")
    typer.echo(json.dumps({k: v for k, v in report.items() if k != "symbols"}, indent=2))
    for symbol, item in report["symbols"].items():
        typer.echo(f"{symbol}: {item['rows']:,} ticks, {item['start']} -> {item['end']}")


@app.command()
def bars(config: Path = Path("configs/research_v1.yaml")) -> None:
    cfg = load_config(config)
    tick_root = resolve_path(cfg, "ticks")
    output = _artifacts(cfg) / "bars"
    quality = {}
    for symbol in [cfg["data"]["primary_symbol"], *cfg["data"]["context_symbols"]]:
        path = output / f"{symbol}_M15.parquet"
        frame = build_bars_for_symbol(tick_root, symbol, path, cfg["data"]["bar_frequency"])
        quality[symbol] = bar_quality(frame, cfg["data"]["bar_frequency"])
        typer.echo(f"{symbol}: {len(frame):,} bars -> {path}")
    (output / "quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")


@app.command()
def dataset(config: Path = Path("configs/research_v1.yaml")) -> None:
    cfg = load_config(config)
    bar_dir = _artifacts(cfg) / "bars"
    primary = pd.read_parquet(bar_dir / f"{cfg['data']['primary_symbol']}_M15.parquet")
    contexts = {
        symbol: pd.read_parquet(bar_dir / f"{symbol}_M15.parquet")
        for symbol in cfg["data"]["context_symbols"]
    }
    frame = join_context(primary, contexts)
    frame = add_gap_segments(frame, cfg["data"]["bar_frequency"], int(cfg["data"]["max_gap_bars"]))
    processed = []
    for _, segment in frame.groupby("segment_id", sort=True):
        segment = add_equilibrium(segment, cfg)
        segment = build_features(segment, cfg)
        segment = add_all_labels(segment, cfg)
        processed.append(segment)
    frame = pd.concat(processed).sort_index()
    output = _artifacts(cfg) / "research_dataset.parquet"
    frame.to_parquet(output)
    typer.echo(f"{len(frame):,} rows, {len(frame.columns)} columns -> {output}")


@app.command("walk-forward")
def walk_forward(config: Path = Path("configs/research_v1.yaml")) -> None:
    cfg = load_config(config)
    frame = pd.read_parquet(_artifacts(cfg) / "research_dataset.parquet")
    result = run_walk_forward(frame, cfg, _artifacts(cfg) / "walk_forward")
    typer.echo(f"Completed {result['n_folds']} purged OOS folds")


@app.command()
def report(config: Path = Path("configs/research_v1.yaml")) -> None:
    cfg = load_config(config)
    result = create_report(
        _artifacts(cfg) / "walk_forward", _artifacts(cfg) / "FINAL_REPORT.json", cfg
    )
    typer.echo(f"Decision: {result['decision']}")


@app.command("shadow-once")
def shadow_once(config: Path = Path("configs/research_v1.yaml"), model: Path  None = None) -> None:
    cfg = load_config(config)
    artifacts = _artifacts(cfg)
    model = model or sorted((artifacts / "walk_forward").glob("fold_*.joblib"))[-1]
    report_path = artifacts / "FINAL_REPORT.json"
    decision = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    result = infer_latest(
        artifacts / "research_dataset.parquet",
        model,
        artifacts / "shadow" / "inference.jsonl",
        research_approved=decision.get("decision") == "approve_for_shadow",
        kill_switch=bool(cfg["shadow"]["kill_switch"]),
    )
    typer.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()
