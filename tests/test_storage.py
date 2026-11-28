"""Unit tests cho module tạo, đọc dữ liệu và Resilience Log."""
import pandas as pd
import numpy as np
from src.data.generator import generate_sample_session_data
from src.data.storage import load_market_data, audit_data_resilience, load_market_data_with_audit


def test_generate_sample_session_data():
    df = generate_sample_session_data(num_days=2, ticks_per_day=50)
    assert len(df) == 100
    assert "futures_price" in df.columns
    assert "underlying_price" in df.columns
    assert "bid_price_1" in df.columns
    assert "ask_price_1" in df.columns


def test_load_market_data():
    df = load_market_data()
    assert not df.empty
    assert "timestamp" in df.columns
    assert df["futures_price"].isnull().sum() == 0
    assert df["underlying_price"].isnull().sum() == 0


def test_audit_data_resilience_detects_anomalies():
    raw = pd.DataFrame({
        "timestamp": ["2026-11-28 09:30:00", "2026-11-28 09:30:00", "2026-11-28 09:31:00"],
        "bid_price_1": [1300.5, 1300.0, 1300.0],
        "ask_price_1": [1300.0, 1300.2, np.nan],  # dòng 0 crossed book (Ask < Bid), dòng 2 NaN
        "bid_vol_1": [10, -5, 10],                # dòng 1 khối lượng âm
        "ask_vol_1": [10, 10, 10],
    })
    audit = audit_data_resilience(raw, source_label="real", fallback_used=True, api_disconnects=2)
    assert audit["duplicate_timestamps_count"] == 1
    assert audit["crossed_book_count"] == 1
    assert audit["negative_volume_count"] == 1
    assert audit["missing_values_count"] == 1
    assert audit["fallback_used"] is True
    assert audit["api_disconnects"] == 2
    assert audit["reliability_status"] == "DEGRADED"


def test_load_market_data_with_audit():
    df_clean, is_real, audit = load_market_data_with_audit(source="sample")
    assert not df_clean.empty
    assert is_real is False
    assert audit["total_clean_rows"] == len(df_clean)
