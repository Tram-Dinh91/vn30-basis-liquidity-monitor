"""
Module tính toán các chỉ số thống kê mô tả chuỗi thời gian (Descriptive Statistics)
phục vụ báo cáo và phân tích 10 phiên giao dịch.
"""
import pandas as pd
from typing import Dict, Any


def calculate_descriptive_stats(df: pd.DataFrame, columns: list = None) -> pd.DataFrame:
    """
    Tính bảng thống kê mô tả chuẩn hóa cho các chuỗi chỉ số tài chính:
    - Trung bình (Mean)
    - Độ lệch chuẩn (Std)
    - Tối thiểu (Min)
    - Phân vị 25% (Q25)
    - Trung vị (Median / Q50)
    - Phân vị 75% (Q75)
    - Tối đa (Max)
    """
    if columns is None:
        columns = ["basis", "relative_spread", "obi"]
        
    valid_cols = [c for c in columns if c in df.columns]
    if not valid_cols:
        return pd.DataFrame()
        
    desc = df[valid_cols].describe().T
    desc = desc.rename(columns={
        "count": "Số lượng",
        "mean": "Trung bình (Mean)",
        "std": "Độ lệch chuẩn (Std)",
        "min": "Tối thiểu (Min)",
        "25%": "Phân vị 25%",
        "50%": "Trung vị (Median)",
        "75%": "Phân vị 75%",
        "max": "Tối đa (Max)"
    })
    return desc.round(4)
