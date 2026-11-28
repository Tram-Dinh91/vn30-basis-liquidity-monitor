"""Unit tests cho module đo lường thanh khoản, Spread và Slippage Scenarios."""
import pandas as pd
from src.finance.liquidity import (
    calculate_relative_spread,
    calculate_market_depth,
    detect_spread_shock,
    simulate_slippage_scenarios,
)


def test_calculate_relative_spread():
    spread = calculate_relative_spread(1280.0, 1280.2)
    expected = (0.2 / 1280.1) * 100.0
    assert round(spread, 5) == round(expected, 5)

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
    spreads = [0.015] * 95 + [0.1] * 5
    series = pd.Series(spreads)
    shocks = detect_spread_shock(series, percentile_threshold=95.0)

    assert shocks.iloc[-1] == True
    assert shocks.iloc[0] == False


def test_simulate_slippage_scenarios():
    row = pd.Series({
        "bid_price_1": 1300.0, "bid_price_2": 1299.8, "bid_price_3": 1299.6,
        "bid_vol_1": 15, "bid_vol_2": 25, "bid_vol_3": 40,
        "ask_price_1": 1300.2, "ask_price_2": 1300.4, "ask_price_3": 1300.6,
        "ask_vol_1": 15, "ask_vol_2": 25, "ask_vol_3": 40,
    })
    df_sim = simulate_slippage_scenarios(row, quantities=[5, 20, 50, 100], side="BUY")
    assert len(df_sim) == 4
    assert list(df_sim["Quy mô (HĐ)"]) == [5, 20, 50, 100]
    assert df_sim["Trượt giá (điểm)"].is_monotonic_increasing
