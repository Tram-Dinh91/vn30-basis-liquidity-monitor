"""Unit tests cho module phân tích vi cấu trúc sổ lệnh (OBI & Micro-price)."""
import pytest
from src.finance.orderbook import (
    calculate_obi,
    calculate_micro_price,
    classify_obi_signal
)


def test_calculate_obi():
    # Khi chỉ có mua, không có bán -> OBI = +1.0
    assert calculate_obi([100, 50, 20], [0, 0, 0]) == 1.0
    
    # Khi chỉ có bán, không có mua -> OBI = -1.0
    assert calculate_obi([0, 0, 0], [100, 50, 20]) == -1.0
    
    # Khi khối lượng hai bên bằng nhau -> OBI = 0.0
    assert calculate_obi([50, 50, 50], [50, 50, 50]) == 0.0
    
    # Tổng khối lượng bằng 0
    assert calculate_obi([0, 0, 0], [0, 0, 0]) == 0.0


def test_calculate_micro_price():
    # Bid = 1280.0 (Vol 10), Ask = 1281.0 (Vol 90) -> Cung áp đảo, giá dễ khớp về Bid
    # Micro-price = (1280 * 90 + 1281 * 10) / 100 = 1280.1
    p = calculate_micro_price(1280.0, 10.0, 1281.0, 90.0)
    assert p == 1280.1

    # Ngược lại: Bid Vol = 90, Ask Vol = 10 -> Cầu áp đảo, Micro-price = 1280.9
    p_up = calculate_micro_price(1280.0, 90.0, 1281.0, 10.0)
    assert p_up == 1280.9


def test_classify_obi_signal():
    code1, msg1 = classify_obi_signal(0.75, extreme_threshold=0.6)
    assert code1 == "BULLISH_PRESSURE"
    
    code2, msg2 = classify_obi_signal(-0.8, extreme_threshold=0.6)
    assert code2 == "BEARISH_PRESSURE"
    
    code3, msg3 = classify_obi_signal(0.1, extreme_threshold=0.6)
    assert code3 == "NEUTRAL"
