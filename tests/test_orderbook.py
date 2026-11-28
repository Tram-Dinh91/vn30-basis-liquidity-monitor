"""Unit tests cho module phân tích vi cấu trúc sổ lệnh (OBI, Micro-price & Slippage Simulator)."""
import pytest
from src.finance.orderbook import (
    calculate_obi,
    calculate_micro_price,
    classify_obi_signal,
    simulate_order_execution,
)


def test_calculate_obi():
    assert calculate_obi([100, 50, 20], [0, 0, 0]) == 1.0
    assert calculate_obi([0, 0, 0], [100, 50, 20]) == -1.0
    assert calculate_obi([50, 50, 50], [50, 50, 50]) == 0.0
    assert calculate_obi([0, 0, 0], [0, 0, 0]) == 0.0


def test_calculate_micro_price():
    p = calculate_micro_price(1280.0, 10.0, 1281.0, 90.0)
    assert p == 1280.1

    p_up = calculate_micro_price(1280.0, 90.0, 1281.0, 10.0)
    assert p_up == 1280.9


def test_classify_obi_signal():
    code1, _ = classify_obi_signal(0.75, extreme_threshold=0.6)
    assert code1 == "BULLISH_PRESSURE"

    code2, _ = classify_obi_signal(-0.8, extreme_threshold=0.6)
    assert code2 == "BEARISH_PRESSURE"

    code3, _ = classify_obi_signal(0.1, extreme_threshold=0.6)
    assert code3 == "NEUTRAL"


def test_simulate_order_execution_l2_walk():
    bid_p = [1300.0, 1299.8, 1299.5]
    bid_v = [10, 20, 30]
    ask_p = [1300.2, 1300.5, 1301.0]
    ask_v = [10, 20, 30]

    # Mua 20 HĐ: khớp 10 @ 1300.2 + 10 @ 1300.5 -> TB = 1300.35
    res_buy = simulate_order_execution("BUY", 20, bid_p, bid_v, ask_p, ask_v)
    assert res_buy["read_only"] is True
    assert res_buy["is_l2_depth_available"] is True
    assert res_buy["avg_fill_price"] == 1300.35
    assert res_buy["slippage_points"] == 0.15
    assert res_buy["unfilled_qty"] == 0

    # Bán 100 HĐ vượt quá độ sâu 60 HĐ ở 3 bước giá
    res_sell = simulate_order_execution("SELL", 100, bid_p, bid_v, ask_p, ask_v)
    assert res_sell["filled_qty"] == 60
    assert res_sell["unfilled_qty"] == 40
    assert res_sell["depth_coverage_pct"] == 60.0


def test_simulate_order_execution_zero_l2_fallback():
    res = simulate_order_execution(
        "BUY", 50,
        [1300.0, 1299.9, 1299.8], [0, 0, 0],
        [1300.2, 1300.3, 1300.4], [0, 0, 0],
    )
    assert res["is_l2_depth_available"] is False
    assert res["read_only"] is True
    assert res["avg_fill_price"] >= 1300.2
