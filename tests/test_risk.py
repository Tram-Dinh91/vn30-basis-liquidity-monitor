"""Unit tests cho hệ thống đánh giá rủi ro tổng hợp."""
import pytest
from src.finance.risk import evaluate_system_risk


def test_evaluate_system_risk_normal():
    # Khi mọi chỉ số bình thường (Basis thấp, Spread nhỏ, OBI cân bằng)
    res = evaluate_system_risk(basis=-0.5, z_basis=0.3, relative_spread=0.015, obi=0.1)
    assert res["status"] == "BÌNH THƯỜNG (NORMAL)"
    assert res["risk_score"] <= 30.0
    assert res["alerts_count"] == 0


def test_evaluate_system_risk_critical():
    # Khi xuất hiện phân kỳ Basis cực đại (Z = 2.8) và sốc thanh khoản (Spread = 0.15)
    res = evaluate_system_risk(basis=18.5, z_basis=2.8, relative_spread=0.15, obi=0.7)
    assert "RỦI RO CAO" in res["status"]
    assert res["risk_score"] >= 65.0
    assert res["alerts_count"] >= 2
