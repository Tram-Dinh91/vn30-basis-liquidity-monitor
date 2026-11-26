"""Unit tests cho module tạo và đọc dữ liệu."""
import pytest
import pandas as pd
from src.data.generator import generate_sample_session_data
from src.data.storage import load_market_data


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
    # Kiểm tra không có giá trị null sau khi load
    assert df["futures_price"].isnull().sum() == 0
    assert df["underlying_price"].isnull().sum() == 0
