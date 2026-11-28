"""
Module đối chiếu chéo (Cross-Check) giữa nguồn dữ liệu cốt lõi VPBankS NEO API
và nguồn dữ liệu bổ trợ SSI FastConnect.
Giúp đo lường độ lệch giá, độ lệch Basis và độ trễ đồng bộ giữa hai nhà cung cấp.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional


def cross_check_sources(
    primary_df: Optional[pd.DataFrame],
    secondary_df: Optional[pd.DataFrame],
    primary_name: str = "NEO API",
    secondary_name: str = "SSI FastConnect",
    tolerance_seconds: int = 60,
) -> Dict[str, Any]:
    """
    Đối chiếu chéo hai chuỗi dữ liệu theo mốc thời gian gần nhất (merge_asof).
    Trả về bảng thống kê độ lệch giá HĐTL, chỉ số VN30, Basis và độ trễ thời gian.
    """
    if primary_df is None or primary_df.empty:
        return {
            "available": False,
            "primary_name": primary_name,
            "secondary_name": secondary_name,
            "matched_records": 0,
            "message": f"Chưa có dữ liệu từ {primary_name} để đối chiếu (đang dùng {secondary_name} làm nguồn thị trường thật).",
            "comparison_df": pd.DataFrame(),
        }

    if secondary_df is None or secondary_df.empty:
        return {
            "available": False,
            "primary_name": primary_name,
            "secondary_name": secondary_name,
            "matched_records": 0,
            "message": f"Chưa có dữ liệu từ {secondary_name} để đối chiếu.",
            "comparison_df": pd.DataFrame(),
        }

    p = primary_df.copy()
    s = secondary_df.copy()
    p["timestamp"] = pd.to_datetime(p["timestamp"])
    s["timestamp"] = pd.to_datetime(s["timestamp"])
    p = p.sort_values("timestamp").reset_index(drop=True)
    s = s.sort_values("timestamp").reset_index(drop=True)

    p["basis_primary"] = p["futures_price"] - p["underlying_price"]
    s["basis_secondary"] = s["futures_price"] - s["underlying_price"]
    s["timestamp_secondary"] = s["timestamp"]

    merged = pd.merge_asof(
        p[["timestamp", "futures_price", "underlying_price", "basis_primary"]].rename(
            columns={"futures_price": "futures_primary", "underlying_price": "underlying_primary"}
        ),
        s[["timestamp", "timestamp_secondary", "futures_price", "underlying_price", "basis_secondary"]].rename(
            columns={"futures_price": "futures_secondary", "underlying_price": "underlying_secondary"}
        ),
        on="timestamp",
        direction="nearest",
        tolerance=pd.Timedelta(seconds=tolerance_seconds),
    ).dropna(subset=["futures_secondary"])

    if merged.empty:
        return {
            "available": False,
            "primary_name": primary_name,
            "secondary_name": secondary_name,
            "matched_records": 0,
            "message": f"Không tìm thấy bản ghi trùng khớp trong ngưỡng ±{tolerance_seconds}s.",
            "comparison_df": pd.DataFrame(),
        }

    merged["futures_diff"] = merged["futures_primary"] - merged["futures_secondary"]
    merged["underlying_diff"] = merged["underlying_primary"] - merged["underlying_secondary"]
    merged["basis_diff"] = merged["basis_primary"] - merged["basis_secondary"]
    merged["lag_seconds"] = (merged["timestamp"] - merged["timestamp_secondary"]).abs().dt.total_seconds()

    return {
        "available": True,
        "primary_name": primary_name,
        "secondary_name": secondary_name,
        "matched_records": int(len(merged)),
        "mean_abs_futures_diff": round(float(merged["futures_diff"].abs().mean()), 4),
        "max_abs_futures_diff": round(float(merged["futures_diff"].abs().max()), 4),
        "mean_abs_underlying_diff": round(float(merged["underlying_diff"].abs().mean()), 4),
        "mean_abs_basis_diff": round(float(merged["basis_diff"].abs().mean()), 4),
        "mean_lag_seconds": round(float(merged["lag_seconds"].mean()), 2),
        "message": f"Đã đối chiếu thành công {len(merged)} bản ghi giữa {primary_name} và {secondary_name}.",
        "comparison_df": merged,
    }
