"""Unit tests cho hệ thống đánh giá rủi ro tổng hợp và phân loại Market Regime."""
import pandas as pd
from src.finance.risk import evaluate_system_risk
from src.analytics.risk_engine import classify_market_regime, classify_regime_series


def test_evaluate_system_risk_normal():
    res = evaluate_system_risk(basis=-0.5, z_basis=0.3, relative_spread=0.015, obi=0.1)
    assert res["status"] == "BÌNH THƯỜNG (NORMAL)"
    assert res["risk_score"] <= 30.0
    assert res["alerts_count"] == 0
    assert res["regime_code"] == "BALANCED_NORMAL"


def test_evaluate_system_risk_critical():
    res = evaluate_system_risk(basis=18.5, z_basis=2.8, relative_spread=0.15, obi=0.7)
    assert "RỦI RO CAO" in res["status"]
    assert res["risk_score"] >= 65.0
    assert res["alerts_count"] >= 2
    assert res["regime_code"] == "BASIS_EXTREME_ILLIQUID"


def test_classify_market_regime_variants():
    assert classify_market_regime(0.5, 0.12, 0.1)["regime_code"] == "LIQUIDITY_STRESS"
    assert classify_market_regime(-2.4, 0.02, 0.1)["regime_code"] == "BASIS_EXTREME"
    assert classify_market_regime(0.2, 0.02, -0.75)["regime_code"] == "ORDERBOOK_IMBALANCE_PRESSURE"
    assert classify_market_regime(1.7, 0.02, 0.1)["regime_code"] == "BASIS_STRETCH"

    df = pd.DataFrame({
        "z_basis": [0.1, 2.5, -0.2],
        "relative_spread": [0.02, 0.10, 0.02],
        "obi": [0.0, 0.1, 0.8],
    })
    regimes = classify_regime_series(df)
    assert list(regimes) == ["BALANCED_NORMAL", "BASIS_EXTREME_ILLIQUID", "ORDERBOOK_IMBALANCE_PRESSURE"]
