import os
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "Universo de activos" / "Datos_Crudos_Zip"
OUT_ROOT = ROOT / "Universo de activos" / "ticks_parquet"
RESULTS_DIR = ROOT / "SUB_RAMA_MEAN_REVERSION" / "resultados"


def months_needed(asset: str) -> list[str]:
    trades_path = RESULTS_DIR / asset / f"{asset}_mr_trades_OOS.csv"
    if not trades_path.exists():
        return []
    trades = pd.read_csv(trades_path, parse_dates=["entry_time", "exit_time"])
    months = set()
    for _, row in trades.iterrows():
        for p in pd.period_range(row["entry_time"].to_period("M"), row["exit_time"].to_period("M"), freq="M"):
            months.add(f"{p.year}{p.month:02d}")
    return sorted(months)


def zip_for(asset: str, yyyymm: str) -> Path:
    return RAW_ROOT / asset / f"DAT_ASCII_{asset}_T_{yyyymm}.zip"


def convert_month(asset: str, yyyymm: str, chunksize: int = 1_000_000) -> dict:
    zip_path = zip_for(asset, yyyymm)
    if not zip_path.exists():
        return {"asset": asset, "month": yyyymm, "status": "MISSING_ZIP", "rows": 0}

    out_dir = OUT_ROOT / asset / f"year={yyyymm[:4]}" / f"month={int(yyyymm[4:])}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"ticks_{asset}_{yyyymm}.parquet"
    if out_path.exists():
        try:
            meta = pq.ParquetFile(out_path)
            return {"asset": asset, "month": yyyymm, "status": "EXISTS", "rows": meta.metadata.num_rows, "parquet_file": str(out_path)}
        except Exception:
            out_path.unlink()

    rows = 0
    writer = None
    with zipfile.ZipFile(zip_path) as zf:
        csv_members = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        name = csv_members[0] if csv_members else zf.namelist()[0]
        with zf.open(name) as handle:
            reader = pd.read_csv(
                handle,
                header=None,
                names=["raw_time", "bid", "ask", "volume"],
                dtype={"raw_time": "string", "bid": "float64", "ask": "float64", "volume": "float64"},
                chunksize=chunksize,
            )
            for chunk in reader:
                out = pd.DataFrame({
                    "timestamp": pd.to_datetime(chunk["raw_time"], format="%Y%m%d %H%M%S%f").astype("datetime64[ms]"),
                    "bid": chunk["bid"].to_numpy(dtype="float64"),
                    "ask": chunk["ask"].to_numpy(dtype="float64"),
                })
                rows += len(out)
                table = pa.Table.from_pandas(out, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(out_path, table.schema, compression="snappy")
                writer.write_table(table)

    if writer is not None:
        writer.close()
    return {"asset": asset, "month": yyyymm, "status": "WRITTEN", "rows": rows, "parquet_file": str(out_path)}


def main():
    assets = sys.argv[1:] if len(sys.argv) > 1 else ["NSXUSD", "XAGUSD"]
    manifest = []
    for asset in assets:
        needed = months_needed(asset)
        print(f"[*] {asset}: {len(needed)} meses necesarios", flush=True)
        for idx, yyyymm in enumerate(needed, start=1):
            print(f"  [{idx}/{len(needed)}] {yyyymm}", flush=True)
            manifest.append(convert_month(asset, yyyymm))

    manifest_path = OUT_ROOT / "conversion_manifest_mr_oos.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(manifest).to_csv(manifest_path, index=False)
    print(f"[+] Manifest: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
