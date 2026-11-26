"""Unit tests cho module tính toán Basis và Z-score."""
import pytest
import pandas as pd
import numpy as np
from datetime import date
from src.finance.basis import (
    calculate_basis,
    calculate_basis_series,
    calculate_z_score,
    get_expiry_date,
    calculate_dte,
    calculate_fair_basis
)


def test_calculate_basis_basic():
    # Khi Futures cao hơn Spot -> Basis dương (+5.0)
    assert calculate_basis(1285.0, 1280.0) == 5.0
    # Khi Futures thấp hơn Spot -> Basis âm (-3.5)
    assert calculate_basis(1276.5, 1280.0) == -3.5
    # Trường hợp None
    assert calculate_basis(None, 1280.0) == 0.0


def test_calculate_basis_series():
    df = pd.DataFrame({
        "futures_price": [1280.0, 1282.0, 1285.0],
        "underlying_price": [1275.0, 1280.0, 1290.0]
    })
    res = calculate_basis_series(df)
    expected = pd.Series([5.0, 2.0, -5.0])
    pd.testing.assert_series_equal(res, expected, check_names=False)


def test_calculate_z_score():
    # Chuỗi hằng số -> Z-score phải bằng 0 (tránh chia cho 0)
    series = pd.Series([5.0, 5.0, 5.0, 5.0, 5.0])
    z = calculate_z_score(series, window=5)
    assert (z == 0.0).all()

    # Chuỗi có 1 giá trị đột biến cực đoan
    series_spike = pd.Series([0.0, 0.0, 0.0, 0.0, 10.0])
    z_spike = calculate_z_score(series_spike, window=5)
    assert z_spike.iloc[-1] > 1.5


def test_get_expiry_date():
    # Kiểm tra ngày đáo hạn tháng 11/2026:
    # Ngày 1/11/2026 là Chủ Nhật (weekday 6).
    # Thứ Năm đầu tiên là 5/11/2026.
    # Thứ Năm tuần thứ 3 = 5 + 14 = 19/11/2026.
    expiry = get_expiry_date(2026, 11)
    assert expiry == date(2026, 11, 19)
    assert expiry.weekday() == 3  # Luôn là Thứ Năm


def test_calculate_dte():
    today = date(2026, 11, 10)
    expiry = date(2026, 11, 19)
    assert calculate_dte(today, expiry) == 9

    # Nếu đã qua ngày đáo hạn
    past_expiry = date(2026, 11, 5)
    assert calculate_dte(today, past_expiry) == 0


def test_calculate_fair_basis():
    # Khi DTE = 0 -> Fair basis = 0
    assert calculate_fair_basis(1280.0, dte=0) == 0.0
    
    # Khi r > q (5% > 1.5%) -> r - q = 3.5% > 0 -> Fair basis > 0
    fair = calculate_fair_basis(1280.0, dte=30, risk_free_rate=0.05, dividend_yield=0.015)
    assert fair > 0.0
    assert round(fair, 2) == round(1280.0 * 0.035 * (30 / 365), 2)
