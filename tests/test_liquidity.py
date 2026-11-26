"""Unit tests cho module đo lường thanh khoản và Spread."""
import pytest
import pandas as pd
from src.finance.liquidity import (
    calculate_relative_spread,
    calculate_market_depth,
    detect_spread_shock
)


def test_calculate_relative_spread():
    # Bid = 1280.0, Ask = 1280.2 -> Midpoint = 1280.1 -> Spread = 0.2 / 1280.1 * 100
    spread = calculate_relative_spread(1280.0, 1280.2)
    expected = (0.2 / 1280.1) * 100.0
    assert round(spread, 5) == round(expected, 5)

    # Dữ liệu bất thường hoặc đảo ngược (Ask < Bid)
    assert calculate_relative_spread(1280.2, 1280.0) == 0.0
    assert calculate_relative_spread(None, 1280.0) == 0.0
    assert calculate_relative_spread(0.0, 1280.0) == 0.0


def test_calculate_market_depth():
    bids = [100.0, 50.0, 25.0]
    asks = [80.0, 40.0, 20.0]
    depth = calculate_market_depth(bids, asks)
    
    assert depth["total_bid_volume"] == 175.0
    assert depth["total_ask_volume"] == 140.0
    assert depth["total_market_depth"] == 315.0
    assert depth["bid_depth_ratio"] > depth["ask_depth_ratio"]


def test_detect_spread_shock():
    # 95 quan sát spread nhỏ (0.015) và 5 quan sát spread rất to (0.1)
    spreads = [0.015] * 95 + [0.1] * 5
    series = pd.Series(spreads)
    shocks = detect_spread_shock(series, percentile_threshold=95.0)
    
    # 5 giá trị cuối phải được gắn nhãn True (Shock)
    assert shocks.iloc[-1] == True
    assert shocks.iloc[0] == False
