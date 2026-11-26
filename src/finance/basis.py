"""
Module tính toán Độ lệch Phái sinh - Cơ sở (Basis) & Chuẩn hóa thống kê Z-score.
Áp dụng lý thuyết Cost-of-Carry và phân tích chuỗi thời gian tài chính.
"""
import numpy as np
import pandas as pd
from datetime import datetime, date


def calculate_basis(futures_price: float, underlying_price: float) -> float:
    """
    Tính Basis tức thời giữa HĐTL VN30F1M và chỉ số VN30.
    Basis = P_Futures - P_Underlying
    """
    if futures_price is None or underlying_price is None:
        return 0.0
    return float(futures_price - underlying_price)


def calculate_basis_series(df: pd.DataFrame, 
                           futures_col: str = "futures_price", 
                           underlying_col: str = "underlying_price") -> pd.Series:
    """
    Tính chuỗi Basis từ DataFrame chứa giá HĐTL và chỉ số cơ sở.
    """
    if futures_col not in df.columns or underlying_col not in df.columns:
        raise ValueError(f"Thiếu cột {futures_col} hoặc {underlying_col} trong DataFrame")
    return df[futures_col] - df[underlying_col]


def calculate_z_score(series: pd.Series, window: int = 20) -> pd.Series:
    """
    Tính Z-score trượt của một chuỗi dữ liệu (ví dụ Basis) trên cửa sổ thời gian (window).
    Z = (X_t - Mean_window) / Std_window
    """
    rolling_mean = series.rolling(window=window, min_periods=1).mean()
    rolling_std = series.rolling(window=window, min_periods=1).std()
    
    # Tránh chia cho 0 khi độ lệch chuẩn bằng 0 hoặc rất nhỏ
    rolling_std_safe = rolling_std.replace(0.0, np.nan)
    z_score = (series - rolling_mean) / rolling_std_safe
    return z_score.fillna(0.0)


def get_expiry_date(year: int, month: int) -> date:
    """
    Xác định ngày đáo hạn của HĐTL chỉ số tại Việt Nam:
    Ngày thứ Năm tuần thứ 3 trong tháng đáo hạn.
    """
    # Tìm ngày đầu tiên của tháng
    first_day = date(year, month, 1)
    # Thứ của ngày 1 (0: Thứ 2, ..., 3: Thứ 5, ..., 6: Chủ nhật)
    first_weekday = first_day.weekday()
    
    # Tính ngày thứ Năm đầu tiên trong tháng
    days_to_first_thursday = (3 - first_weekday) % 7
    first_thursday = 1 + days_to_first_thursday
    
    # Thứ Năm tuần thứ 3 = Thứ Năm đầu tiên + 14 ngày
    third_thursday = first_thursday + 14
    return date(year, month, third_thursday)


def calculate_dte(current_date: date, expiry_date: date) -> int:
    """
    Tính số ngày còn lại đến khi đáo hạn (Days To Expiration - DTE).
    Nếu đã qua ngày đáo hạn, trả về 0.
    """
    delta = (expiry_date - current_date).days
    return max(0, delta)


def calculate_fair_basis(underlying_price: float, 
                         dte: int, 
                         risk_free_rate: float = 0.05, 
                         dividend_yield: float = 0.015) -> float:
    """
    Tính Basis lý thuyết (Fair Basis) theo mô hình Chi phí vốn nắm giữ (Cost-of-Carry Model):
    F* = S * [1 + (r - q) * (DTE / 365)]
    Fair_Basis = F* - S = S * (r - q) * (DTE / 365)
    
    Trong đó:
    - S: Giá chỉ số VN30
    - r: Lãi suất phi rủi ro (vd: 5%/năm)
    - q: Tỷ suất cổ tức trung bình rổ VN30 (vd: 1.5%/năm)
    - DTE: Số ngày đến khi đáo hạn
    """
    if dte <= 0:
        return 0.0
    carry_cost = (risk_free_rate - dividend_yield) * (dte / 365.0)
    fair_basis = underlying_price * carry_cost
    return float(fair_basis)
