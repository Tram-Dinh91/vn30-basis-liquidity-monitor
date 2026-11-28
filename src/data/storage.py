"""
Module Lưu trữ, Kiểm toán Chất lượng Dữ liệu & Nhật ký Sự cố (Resilience Log).
Hỗ trợ:
- Tách biệt rõ ràng giữa Dữ liệu mô phỏng (Sample) và Dữ liệu thật từ NEO API / SSI (Real)
- Lưu trữ Parquet hiệu năng cao và CSV
- Đảm bảo múi giờ chuẩn Asia/Ho_Chi_Minh (UTC+7)
- Ghi nhận Resilience Log trước khi làm sạch: NaN, trùng lặp, crossed book (Ask1 < Bid1), khối lượng âm
"""
import pandas as pd
from pathlib import Path
from typing import Optional, List, Tuple, Union, Dict, Any
from src.config import SAMPLE_DATA_DIR, REAL_DATA_DIR, CACHE_DIR, TIMEZONE
from src.data.generator import ensure_sample_data_exists


def get_available_sources() -> List[str]:
    """Kiểm tra các nguồn dữ liệu có sẵn trên máy. Ưu tiên Dữ liệu Thật lên đầu nếu đã thu thập."""
    sources = []
    real_files = list(REAL_DATA_DIR.glob("*.parquet")) + list(REAL_DATA_DIR.glob("*.csv"))
    if real_files:
        sources.append("Dữ liệu Thị trường Thật (API Saved)")
    sources.append("Dữ liệu Kiểm chứng (10 Phiên Mô phỏng)")
    return sources


def audit_data_resilience(
    raw_df: pd.DataFrame,
    source_label: str = "sample",
    fallback_used: bool = False,
    api_disconnects: int = 0,
) -> Dict[str, Any]:
    """
    Kiểm toán chất lượng dữ liệu thô để ghi nhận Resilience Log:
    - Số bản ghi thiếu (NaN)
    - Số bản ghi trùng lặp timestamp
    - Số bản ghi bất thường sổ lệnh (Ask_1 < Bid_1 hoặc giá <= 0)
    - Số bản ghi khối lượng âm
    - Số bản ghi thiếu độ sâu L2 (tổng khối lượng 3 bước giá = 0)
    """
    if raw_df is None or raw_df.empty:
        return {
            "source_label": source_label,
            "total_raw_rows": 0,
            "missing_values_count": 0,
            "duplicate_timestamps_count": 0,
            "crossed_book_count": 0,
            "negative_volume_count": 0,
            "zero_l2_depth_count": 0,
            "fallback_used": fallback_used,
            "api_disconnects": api_disconnects,
            "timezone": TIMEZONE,
            "reliability_status": "WARNING",
        }

    missing_count = int(raw_df.isnull().sum().sum())
    dup_count = int(raw_df.duplicated(subset=["timestamp"]).sum()) if "timestamp" in raw_df.columns else 0

    crossed_count = 0
    if "bid_price_1" in raw_df.columns and "ask_price_1" in raw_df.columns:
        crossed_mask = (
            (raw_df["ask_price_1"] < raw_df["bid_price_1"])
            | (raw_df["bid_price_1"] <= 0)
            | (raw_df["ask_price_1"] <= 0)
        )
        crossed_count = int(crossed_mask.fillna(False).sum())

    vol_cols = [
        c for c in ["bid_vol_1", "bid_vol_2", "bid_vol_3", "ask_vol_1", "ask_vol_2", "ask_vol_3", "matched_volume"]
        if c in raw_df.columns
    ]
    neg_vol_count = int((raw_df[vol_cols] < 0).any(axis=1).sum()) if vol_cols else 0

    l2_cols = [c for c in ["bid_vol_1", "bid_vol_2", "bid_vol_3", "ask_vol_1", "ask_vol_2", "ask_vol_3"] if c in raw_df.columns]
    zero_l2_count = int((raw_df[l2_cols].sum(axis=1) <= 0).sum()) if l2_cols else len(raw_df)

    if fallback_used or crossed_count > 0 or neg_vol_count > 0 or api_disconnects > 0:
        status = "DEGRADED"
    elif missing_count > 0 or dup_count > 0:
        status = "CLEANED_OK"
    else:
        status = "GOOD"

    return {
        "source_label": source_label,
        "total_raw_rows": int(len(raw_df)),
        "missing_values_count": missing_count,
        "duplicate_timestamps_count": dup_count,
        "crossed_book_count": crossed_count,
        "negative_volume_count": neg_vol_count,
        "zero_l2_depth_count": zero_l2_count,
        "fallback_used": fallback_used,
        "api_disconnects": api_disconnects,
        "timezone": TIMEZONE,
        "reliability_status": status,
    }


def load_market_data_with_audit(
    source: str = "sample",
    file_path: Optional[Path] = None,
    session_date: Optional[str] = None,
    api_disconnects: int = 0,
) -> Tuple[pd.DataFrame, bool, Dict[str, Any]]:
    """
    Đọc dữ liệu, thực hiện kiểm toán Resilience Log trên dữ liệu thô, sau đó làm sạch.
    Trả về: (df_clean, is_real_data, resilience_log)
    """
    is_real = False
    fallback_used = False

    if source == "real":
        real_files = sorted(list(REAL_DATA_DIR.glob("*.parquet")) + list(REAL_DATA_DIR.glob("*.csv")), reverse=True)
        if real_files:
            file_path = real_files[0]
            is_real = True
        else:
            file_path = ensure_sample_data_exists()
            fallback_used = True
    elif file_path is None or not Path(file_path).exists():
        file_path = ensure_sample_data_exists()

    path = Path(file_path)
    if path.suffix == ".parquet":
        df_raw = pd.read_parquet(path)
    elif path.suffix == ".csv":
        df_raw = pd.read_csv(path)
    else:
        raise ValueError(f"Định dạng file không hỗ trợ: {path.suffix}")

    resilience_log = audit_data_resilience(
        df_raw,
        source_label="real" if is_real else "sample",
        fallback_used=fallback_used,
        api_disconnects=api_disconnects,
    )

    df = df_raw.copy()
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.ffill().bfill()

    if session_date and "session_date" in df.columns:
        df = df[df["session_date"] == str(session_date)]

    df_clean = df.sort_values(by="timestamp").reset_index(drop=True)
    resilience_log["total_clean_rows"] = int(len(df_clean))
    return df_clean, is_real, resilience_log


def load_market_data(
    source: str = "sample",
    file_path: Optional[Path] = None,
    session_date: Optional[str] = None,
    return_info: bool = False,
) -> Union[pd.DataFrame, Tuple[pd.DataFrame, bool]]:
    """
    Đọc dữ liệu thị trường từ file Parquet hoặc CSV (tương thích ngược).
    """
    df_clean, is_real, _ = load_market_data_with_audit(
        source=source,
        file_path=file_path,
        session_date=session_date,
    )
    if return_info:
        return df_clean, is_real
    return df_clean


def save_real_ticks(df_ticks: pd.DataFrame, session_date: Optional[str] = None) -> Path:
    """
    Lưu trữ dữ liệu thật thu thập được từ NEO API (REST/WebSocket) vào thư mục data/real/.
    """
    REAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if session_date is None:
        session_date = pd.Timestamp.now(tz=TIMEZONE).strftime("%Y%m%d")

    target_path = REAL_DATA_DIR / f"vn30_real_{session_date}.parquet"

    if target_path.exists():
        existing_df = pd.read_parquet(target_path)
        combined = pd.concat([existing_df, df_ticks]).drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
        combined.to_parquet(target_path, index=False)
    else:
        df_ticks.to_parquet(target_path, index=False)

    return target_path


def save_live_cache_ticks(df_ticks: pd.DataFrame, filename: str = "live_cache.parquet") -> Path:
    """Lưu tạm các tick realtime vào cache trong lúc ứng dụng đang chạy."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target_path = CACHE_DIR / filename

    if target_path.exists():
        existing_df = pd.read_parquet(target_path)
        combined = pd.concat([existing_df, df_ticks]).drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
        combined.to_parquet(target_path, index=False)
    else:
        df_ticks.to_parquet(target_path, index=False)

    return target_path
