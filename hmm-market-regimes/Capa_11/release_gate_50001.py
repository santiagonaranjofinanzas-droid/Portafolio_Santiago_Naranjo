from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "Capa_11" / "forward_50001"
STATUS = OUTDIR / "forward_status_50001.csv"
GATE = OUTDIR / "release_gate_50001.csv"
REPORT = OUTDIR / "REPORTE_RELEASE_GATE_50001.md"


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    if not STATUS.exists():
        result = {
            "bot_id": 50001,
            "decision": "BLOCKED_WAITING_FOR_FORWARD_DATA",
            "closed_trades": 0,
            "profit_factor": 0.0,
            "max_consecutive_losses": 0,
            "monitor_state": "WAITING_FOR_FORWARD_DATA",
        }
    else:
        status = pd.read_csv(STATUS).iloc[0].to_dict()
        closed_trades = int(status.get("closed_trades", 0))
        pf = float(status.get("profit_factor", 0.0))
        max_losses = int(status.get("max_consecutive_losses", 0))
        monitor_state = str(status.get("monitor_state", "UNKNOWN"))
        max_dd = float(status.get("max_drawdown_pct", 0.0))
        avg_slippage = float(status.get("avg_slippage_points", 0.0))
        pass_gate = (
            closed_trades >= 50
            and pf >= 1.10
            and max_dd >= -12.0
            and avg_slippage <= 50.0
            and max_losses <= 6
            and monitor_state == "ACTIVE_FORWARD"
        )
        result = {
            "bot_id": 50001,
            "decision": "PASS_DEMO_FORWARD_GATE" if pass_gate else "BLOCKED_DEMO_ONLY",
            "closed_trades": closed_trades,
            "profit_factor": pf,
            "max_consecutive_losses": max_losses,
            "max_drawdown_pct": max_dd,
            "avg_slippage_points": avg_slippage,
            "monitor_state": monitor_state,
        }
    pd.DataFrame([result]).to_csv(GATE, index=False)
    REPORT.write_text(
        "# Release gate 50001\n\n"
        f"Decision: {result['decision']}\n\n"
        f"Closed trades: {result['closed_trades']}\n\n"
        f"Profit factor: {result['profit_factor']:.3f}\n\n"
        f"Max consecutive losses: {result['max_consecutive_losses']}\n\n"
        f"Max drawdown pct: {result.get('max_drawdown_pct', 0.0):.2f}\n\n"
        f"Avg slippage points: {result.get('avg_slippage_points', 0.0):.2f}\n\n"
        f"Monitor state: {result['monitor_state']}\n\n"
        "El 50001 no pasa a real si la decision no es PASS_DEMO_FORWARD_GATE.\n",
        encoding="utf-8",
    )
    print(result)


if __name__ == "__main__":
    main()
