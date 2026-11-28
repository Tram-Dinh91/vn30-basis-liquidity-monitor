"""Unit tests cho NEO API Client, chuẩn hóa UTC+7 và Cross-Check với SSI."""
import pandas as pd
from src.neo_api.client import (
    NeoApiClient,
    RateLimiter,
    normalize_timestamp_vn,
    parse_neo_quotes_to_tick,
)
from src.data.cross_check import cross_check_sources


def test_neo_client_read_only_and_missing_creds():
    client = NeoApiClient(client_id="", client_secret="")
    assert client.READ_ONLY is True
    assert client.authenticate() is False
    status = client.get_status()
    assert status["read_only"] is True
    assert status["rate_limit_rps"] <= 5
    assert status["last_error"] is not None


def test_rate_limiter_clamps_to_max_5_rps():
    rl = RateLimiter(max_per_second=20)
    assert rl.max_per_second == 5


def test_normalize_timestamp_and_parse_quotes():
    ts = normalize_timestamp_vn("2026-11-28 09:30:00")
    assert ts == "2026-11-28 09:30:00"

    fut_q = {
        "lastPrice": 1350.5,
        "bidPrice1": 1350.4,
        "bidVol1": 25,
        "askPrice1": 1350.6,
        "askVol1": 30,
        "totalVol": 1200,
        "timestamp": "2026-11-28 09:30:00",
    }
    idx_q = {"indexValue": 1345.0, "timestamp": "2026-11-28 09:30:00"}
    tick = parse_neo_quotes_to_tick(fut_q, idx_q)
    assert tick is not None
    assert tick["futures_price"] == 1350.5
    assert tick["underlying_price"] == 1345.0
    assert tick["data_source"] == "NEO_API"


def test_cross_check_sources():
    df_neo = pd.DataFrame({
        "timestamp": ["2026-11-28 09:30:00", "2026-11-28 09:31:00"],
        "futures_price": [1350.5, 1351.0],
        "underlying_price": [1345.0, 1345.2],
    })
    df_ssi = pd.DataFrame({
        "timestamp": ["2026-11-28 09:30:05", "2026-11-28 09:31:00"],
        "futures_price": [1350.4, 1351.0],
        "underlying_price": [1345.0, 1345.2],
    })
    res = cross_check_sources(df_neo, df_ssi)
    assert res["available"] is True
    assert res["matched_records"] == 2
    assert res["mean_abs_futures_diff"] >= 0.0
    assert res["mean_lag_seconds"] == 2.5

    empty_res = cross_check_sources(pd.DataFrame(), df_ssi)
    assert empty_res["available"] is False
