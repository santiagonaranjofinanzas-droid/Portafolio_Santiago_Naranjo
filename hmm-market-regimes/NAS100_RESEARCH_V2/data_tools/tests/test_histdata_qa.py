from __future__ import annotations

import zipfile

import pandas as pd

from NAS100_RESEARCH_V2.data_tools.histdata_qa import rebuild_histdata


def test_rebuild_converts_fixed_est_and_matches_legacy(tmp_path):
    source = tmp_path / "zips"
    source.mkdir()
    rows = (
        "20200101 180000000,100.0,100.5,0\n"
        "20200101 180500000,101.0,101.5,0\n"
        "20200101 181500000,102.0,102.5,0\n"
    )
    with zipfile.ZipFile(source / "DAT_ASCII_NSXUSD_T_202001.zip", "w") as archive:
        archive.writestr("DAT_ASCII_NSXUSD_T_202001.csv", rows)
    legacy = pd.DataFrame(
        {"open": [100.0, 102.0], "high": [101.0, 102.0], "low": [100.0, 102.0], "close": [101.0, 102.0]},
        index=pd.DatetimeIndex(["2020-01-01 18:00", "2020-01-01 18:15"]),
    )
    legacy_path = tmp_path / "legacy.parquet"
    legacy.to_parquet(legacy_path)
    result = rebuild_histdata(source, legacy_path, tmp_path / "out", first_month="2020-01", last_month="2020-01")
    assert result["ok"]
    rebuilt = pd.read_parquet(tmp_path / "out" / "NSXUSD_M15_HISTDATA_DEVELOPMENT_UTC.parquet")
    assert str(rebuilt.index.tz) == "UTC"
    assert rebuilt.index[0] == pd.Timestamp("2020-01-01 23:00", tz="UTC")
    assert rebuilt.iloc[0]["tick_count"] == 2
