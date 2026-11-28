"""
Module đo lường Thanh khoản, Rủi ro thanh khoản nội ngày và Kịch bản Trượt giá cho HĐTL VN30F1M.
Bao gồm: Relative Bid-Ask Spread, Market Depth, Spread Shock, và Slippage Scenarios (Read-only).
"""
import numpy as np
import pandas as pd
from typing import List, Optional
from src.finance.orderbook import simulate_order_execution


def calculate_relative_spread(bid_price: float, ask_price: float) -> float:
    """
    Tính Độ giãn chênh lệch Mua - Bán tương đối (Relative Bid-Ask Spread in percentage):
    Spread (%) = (Ask - Bid) / Midpoint * 100
    """
    if bid_price is None or ask_price is None:
        return 0.0
    if bid_price <= 0 or ask_price <= 0 or ask_price < bid_price:
        return 0.0

    midpoint = (ask_price + bid_price) / 2.0
    if midpoint == 0:
        return 0.0

    spread_pct = ((ask_price - bid_price) / midpoint) * 100.0
    return float(spread_pct)


def calculate_market_depth(bid_volumes: List[float], ask_volumes: List[float]) -> dict:
    """
    Tính tổng độ sâu thanh khoản tại 3 mức giá mua và bán tốt nhất:
    Total_Depth = Sum(Bid_Vol_i) + Sum(Ask_Vol_i)
    """
    total_bid_vol = float(sum(v for v in bid_volumes if v is not None and v > 0))
    total_ask_vol = float(sum(v for v in ask_volumes if v is not None and v > 0))
    total_depth = total_bid_vol + total_ask_vol

    bid_ratio = (total_bid_vol / total_depth) if total_depth > 0 else 0.5
    ask_ratio = (total_ask_vol / total_depth) if total_depth > 0 else 0.5

    return {
        "total_bid_volume": total_bid_vol,
        "total_ask_volume": total_ask_vol,
        "total_market_depth": total_depth,
        "bid_depth_ratio": bid_ratio,
        "ask_depth_ratio": ask_ratio,
    }


def detect_spread_shock(
    spread_series: pd.Series,
    percentile_threshold: float = 95.0,
) -> pd.Series:
    """
    Nhận diện hiện tượng sốc rút cạn thanh khoản (Spread Shock):
    Độ giãn Spread vượt quá phân vị (percentile) lịch sử (mặc định 95%).
    """
    if spread_series.empty or len(spread_series.dropna()) < 5:
        return pd.Series(False, index=spread_series.index)

    cutoff = np.percentile(spread_series.dropna(), percentile_threshold)
    return spread_series > cutoff


def simulate_slippage_scenarios(
    row: pd.Series,
    quantities: Optional[List[int]] = None,
    side: str = "BUY",
) -> pd.DataFrame:
    """
    Chạy mô phỏng chi phí thực thi (Read-only) trên nhiều quy mô hợp đồng giả định (5, 20, 50, 100 HĐ).
    """
    if quantities is None:
        quantities = [5, 20, 50, 100]

    bid_prices = [row.get("bid_price_1", 0), row.get("bid_price_2", 0), row.get("bid_price_3", 0)]
    bid_vols = [row.get("bid_vol_1", 0), row.get("bid_vol_2", 0), row.get("bid_vol_3", 0)]
    ask_prices = [row.get("ask_price_1", 0), row.get("ask_price_2", 0), row.get("ask_price_3", 0)]
    ask_vols = [row.get("ask_vol_1", 0), row.get("ask_vol_2", 0), row.get("ask_vol_3", 0)]

    records = []
    for qty in quantities:
        sim = simulate_order_execution(
            side=side,
            quantity=qty,
            bid_prices=bid_prices,
            bid_volumes=bid_vols,
            ask_prices=ask_prices,
            ask_volumes=ask_vols,
        )
        records.append({
            "Quy mô (HĐ)": sim["quantity"],
            "Chiều lệnh": "MUA (Ask)" if sim["side"] == "BUY" else "BÁN (Bid)",
            "Giá tham chiếu": sim["reference_price"],
            "Giá khớp TB dự kiến": sim["avg_fill_price"],
            "Trượt giá (điểm)": sim["slippage_points"],
            "Trượt giá (%)": sim["slippage_pct"],
            "Chi phí vs Mid (điểm)": sim["total_cost_vs_mid_points"],
            "Độ phủ 3 bước giá (%)": sim["depth_coverage_pct"],
            "Ghi chú": sim["note"],
        })

    return pd.DataFrame(records)
