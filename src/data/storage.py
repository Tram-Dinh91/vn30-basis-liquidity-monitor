"""
Module Lưu trữ & Đọc Dữ liệu (Data Storage & Retrieval).
Hỗ trợ:
- Lưu trữ Parquet hiệu năng cao và CSV
- Đảm bảo múi giờ chuẩn Asia/Ho_Chi_Minh (UTC+7)
- Xử lý giá trị thiếu (Missing values), trùng lặp (Deduplication)
"""
import pandas as pd
from pathlib import Path
from typing import Optional
from src.config import DATA_DIR, CACHE_DIR, TIMEZONE
from src.data.generator import ensure_sample_data_exists


def load_market_data(file_path: Optional[Path] = None, session_date: Optional[str] = None) -> pd.DataFrame:
    """
    Đọc dữ liệu thị trường từ file Parquet hoặc CSV.
    Nếu file_path là None, tự động load file mẫu 10 phiên.
    """
    if file_path is None or not Path(file_path).exists():
        file_path = ensure_sample_data_exists()
        
    path = Path(file_path)
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Định dạng file không hỗ trợ: {path.suffix}")
        
    # Tiền xử lý & làm sạch
    # 1. Chuyển đổi timestamp sang múi giờ VN
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
    # 2. Loại bỏ dữ liệu trùng lặp
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    
    # 3. Điền giá trị thiếu nếu có
    df = df.ffill().bfill()
    
    # 4. Lọc theo ngày nếu có yêu cầu
    if session_date and "session_date" in df.columns:
        df = df[df["session_date"] == str(session_date)]
        
    return df.sort_values(by="timestamp").reset_index(drop=True)


def save_live_ticks(df_ticks: pd.DataFrame, filename: str = "live_ticks.parquet") -> Path:
    """
    Lưu trữ các tick nhận được từ WebSocket hoặc REST API vào cache.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target_path = CACHE_DIR / filename
    
    if target_path.exists():
        existing_df = pd.read_parquet(target_path)
        combined = pd.concat([existing_df, df_ticks]).drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
        combined.to_parquet(target_path, index=False)
    else:
        df_ticks.to_parquet(target_path, index=False)
        
    return target_path
