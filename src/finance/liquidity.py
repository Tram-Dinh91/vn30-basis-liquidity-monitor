"""
Module đo lường Thanh khoản và Rủi ro thanh khoản nội ngày cho HĐTL VN30F1M.
Bao gồm: Relative Bid-Ask Spread, Market Depth, và phát hiện đột biến thanh khoản (Spread Shock).
"""
import numpy as np
import pandas as pd
from typing import List, Union


def calculate_relative_spread(bid_price: float, ask_price: float) -> float:
    """
    Tính Độ giãn chênh lệch Mua - Bán tương đối (Relative Bid-Ask Spread in percentage):
    Spread (%) = (Ask - Bid) / Midpoint * 100
    Trong đó Midpoint = (Ask + Bid) / 2
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


def detect_spread_shock(spread_series: pd.Series, 
                        percentile_threshold: float = 95.0) -> pd.Series:
    """
    Nhận diện hiện tượng sốc rút cạn thanh khoản (Spread Shock):
    Độ giãn Spread vượt quá phân vị (percentile) lịch sử (mặc định 95%).
    Trả về chuỗi Boolean (True khi xuất hiện rủi ro thanh khoản cao).
    """
    if spread_series.empty or len(spread_series.dropna()) < 5:
        return pd.Series(False, index=spread_series.index)
    
    cutoff = np.percentile(spread_series.dropna(), percentile_threshold)
    return spread_series > cutoff
