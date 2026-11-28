"""Unit tests cho kiểm chứng ngoài mẫu (Out-of-sample Validation) và phân loại khung giờ nhiễu."""
import pandas as pd
from src.data.generator import generate_sample_session_data
from src.analytics.metrics import classify_intraday_window, evaluate_out_of_sample_signals


def test_classify_intraday_window():
    ts = pd.Series([
        "2026-11-28 09:00:00",
        "2026-11-28 10:15:00",
        "2026-11-28 13:45:00",
        "2026-11-28 14:35:00",
    ])
    labels = list(classify_intraday_window(ts))
    assert labels == [
        "ATO (08:45-09:15)",
        "Phiên Sáng (09:15-11:30)",
        "Phiên Chiều (13:00-14:30)",
        "ATC (14:30-14:45)",
    ]


def test_evaluate_out_of_sample_signals():
    df = generate_sample_session_data(num_days=4, ticks_per_day=60)
    res = evaluate_out_of_sample_signals(df, split_ratio=0.7, window=20, z_threshold=2.0, horizon_bars=5)
    assert res["valid"] is True
    assert res["train_rows"] + res["test_rows"] == len(df)
    assert res["train_spread_p95"] > 0
    assert not res["window_stats_df"].empty
