"""
Module tính toán Thống kê Mô tả Chuỗi Thời gian, Kiểm chứng Ngoài mẫu (Out-of-sample Validation)
và Phân tích Độ tin cậy theo Khung giờ Nhiễu (ATO, ATC, Thanh khoản mỏng).
"""
import numpy as np
import pandas as pd
from typing import Dict, Any
from src.finance.basis import calculate_basis_series, calculate_z_score
from src.finance.liquidity import calculate_relative_spread


def calculate_descriptive_stats(df: pd.DataFrame, columns: list = None) -> pd.DataFrame:
    """
    Tính bảng thống kê mô tả chuẩn hóa cho các chuỗi chỉ số tài chính.
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
        "max": "Tối đa (Max)",
    })
    return desc.round(4)


def classify_intraday_window(ts_series: pd.Series) -> pd.Series:
    """
    Phân loại khung giờ giao dịch phái sinh Việt Nam (UTC+7):
    - ATO: 08:45 - 09:15 (Khớp lệnh định kỳ mở cửa, nhiễu cao)
    - MORNING_CONT: 09:15 - 11:30
    - AFTERNOON_CONT: 13:00 - 14:30
    - ATC: 14:30 - 14:45 (Khớp lệnh định kỳ đóng cửa, biến động mạnh)
    """
    ts = pd.to_datetime(ts_series)
    hhmm = ts.dt.hour * 100 + ts.dt.minute

    labels = np.where(
        (hhmm >= 845) & (hhmm < 915),
        "ATO (08:45-09:15)",
        np.where(
            (hhmm >= 1430) & (hhmm <= 1445),
            "ATC (14:30-14:45)",
            np.where(
                (hhmm >= 915) & (hhmm <= 1130),
                "Phiên Sáng (09:15-11:30)",
                "Phiên Chiều (13:00-14:30)",
            ),
        ),
    )
    return pd.Series(labels, index=ts_series.index, name="intraday_window")


def evaluate_out_of_sample_signals(
    df: pd.DataFrame,
    split_ratio: float = 0.7,
    window: int = 20,
    z_threshold: float = 2.0,
    horizon_bars: int = 5,
) -> Dict[str, Any]:
    """
    Kiểm chứng ngoài mẫu (Out-of-sample Validation) theo đúng trình tự thời gian,
    tuyệt đối tránh look-ahead bias:
    - Tập Train (70% đầu): ước lượng ngưỡng phân vị 95% của Relative Spread.
    - Tập Test (30% sau): đánh giá tỷ lệ hội tụ (mean-reversion) sau tín hiệu |Z_Basis| >= z_threshold
      trong `horizon_bars` bước kế tiếp, đồng thời tách riêng khung giờ nhiễu (ATO/ATC/thanh khoản mỏng).
    """
    if df is None or len(df) < max(30, window + horizon_bars + 5):
        return {
            "valid": False,
            "message": "Không đủ số lượng quan sát tối thiểu để kiểm chứng ngoài mẫu.",
        }

    work = df.sort_values("timestamp").reset_index(drop=True).copy()
    if "basis" not in work.columns:
        work["basis"] = calculate_basis_series(work)
    if "relative_spread" not in work.columns:
        work["relative_spread"] = [
            calculate_relative_spread(b, a) for b, a in zip(work["bid_price_1"], work["ask_price_1"])
        ]

    # Z-score trượt chỉ sử dụng dữ liệu quá khứ (causal rolling)
    work["z_basis"] = calculate_z_score(work["basis"], window=window)
    work["intraday_window"] = classify_intraday_window(work["timestamp"])

    split_idx = int(len(work) * split_ratio)
    train_df = work.iloc[:split_idx].copy()
    test_df = work.iloc[split_idx:].copy().reset_index(drop=True)

    # Ngưỡng Spread P95 chỉ học trên tập Train (in-sample)
    train_spread_p95 = float(np.percentile(train_df["relative_spread"].dropna(), 95.0))

    # Tính biến động Basis tương lai sau horizon_bars trên tập Test
    test_df["future_basis"] = test_df["basis"].shift(-horizon_bars)
    test_df["is_signal"] = test_df["z_basis"].abs() >= z_threshold
    test_df["is_thin_liquidity"] = test_df["relative_spread"] > train_spread_p95
    test_df["is_noisy_window"] = test_df["intraday_window"].isin(["ATO (08:45-09:15)", "ATC (14:30-14:45)"])

    # Hội tụ khi |Basis_{t+h}| < |Basis_t| hoặc tiến về phía trung bình trượt
    eval_df = test_df.dropna(subset=["future_basis"]).copy()
    signals = eval_df[eval_df["is_signal"]].copy()

    if signals.empty:
        reversion_rate = None
        clean_reversion_rate = None
        noisy_reversion_rate = None
    else:
        signals["reverted"] = signals["future_basis"].abs() < signals["basis"].abs()
        reversion_rate = round(float(signals["reverted"].mean() * 100.0), 1)

        clean_sigs = signals[~signals["is_noisy_window"] & ~signals["is_thin_liquidity"]]
        noisy_sigs = signals[signals["is_noisy_window"] | signals["is_thin_liquidity"]]

        clean_reversion_rate = round(float(clean_sigs["reverted"].mean() * 100.0), 1) if not clean_sigs.empty else None
        noisy_reversion_rate = round(float(noisy_sigs["reverted"].mean() * 100.0), 1) if not noisy_sigs.empty else None

    # Thống kê theo khung giờ trên tập Test
    window_stats = (
        test_df.groupby("intraday_window", as_index=False)
        .agg(
            so_quan_sat=("basis", "count"),
            basis_std=("basis", "std"),
            spread_tb_pct=("relative_spread", "mean"),
            so_tin_hieu_z=("is_signal", "sum"),
        )
        .round(4)
    )
    window_stats.columns = ["Khung giờ", "Số quan sát", "Độ lệch chuẩn Basis", "Spread TB (%)", "Số tín hiệu |Z|>=ngưỡng"]

    return {
        "valid": True,
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "train_spread_p95": round(train_spread_p95, 4),
        "oos_signal_count": int(len(signals)),
        "oos_reversion_rate_pct": reversion_rate,
        "clean_window_reversion_pct": clean_reversion_rate,
        "noisy_window_reversion_pct": noisy_reversion_rate,
        "oos_thin_liquidity_count": int(test_df["is_thin_liquidity"].sum()),
        "window_stats_df": window_stats,
        "reliability_note": (
            "Các khung giờ ATO (08:45-09:15), ATC (14:30-14:45) và giai đoạn Spread > P95_Train "
            "có độ nhiễu vi cấu trúc cao; tín hiệu Z-score ở các vùng này kém tin cậy hơn phiên khớp lệnh liên tục."
        ),
    }
