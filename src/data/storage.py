"""
Module Lưu trữ & Đọc Dữ liệu (Data Storage & Retrieval).
Hỗ trợ:
- Tách biệt rõ ràng giữa Dữ liệu mô phỏng (Sample) và Dữ liệu thật từ NEO API (Real)
- Lưu trữ Parquet hiệu năng cao và CSV
- Đảm bảo múi giờ chuẩn Asia/Ho_Chi_Minh (UTC+7)
- Xử lý giá trị thiếu (Missing values), trùng lặp (Deduplication)
"""
import pandas as pd
from pathlib import Path
from typing import Optional, List, Tuple, Union
from src.config import SAMPLE_DATA_DIR, REAL_DATA_DIR, CACHE_DIR, TIMEZONE
from src.data.generator import ensure_sample_data_exists


def get_available_sources() -> List[str]:
    """Kiểm tra các nguồn dữ liệu có sẵn trên máy."""
    sources = ["Dữ liệu Kiểm chứng (10 Phiên Mô phỏng)"]
    real_files = list(REAL_DATA_DIR.glob("*.parquet")) + list(REAL_DATA_DIR.glob("*.csv"))
    if real_files:
        sources.append("Dữ liệu Thị trường Thật (NEO API Đã Lưu)")
    return sources


def load_market_data(source: str = "sample", 
                     file_path: Optional[Path] = None, 
                     session_date: Optional[str] = None,
                     return_info: bool = False) -> Union[pd.DataFrame, Tuple[pd.DataFrame, bool]]:
    """
    Đọc dữ liệu thị trường từ file Parquet hoặc CSV.
    - source: 'sample' (dữ liệu mô phỏng 10 phiên) hoặc 'real' (dữ liệu thật từ NEO API)
    - Nếu return_info=True: trả về (DataFrame, is_real_data)
    - Mặc định return_info=False: trả về DataFrame
    """
    is_real = False
    
    if source == "real":
        real_files = sorted(list(REAL_DATA_DIR.glob("*.parquet")) + list(REAL_DATA_DIR.glob("*.csv")), reverse=True)
        if real_files:
            file_path = real_files[0]
            is_real = True
        else:
            # Fallback sang dữ liệu mẫu nếu chưa có dữ liệu thật
            file_path = ensure_sample_data_exists()
    elif file_path is None or not Path(file_path).exists():
        file_path = ensure_sample_data_exists()
        
    path = Path(file_path)
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Định dạng file không hỗ trợ: {path.suffix}")
        
    # Tiền xử lý & làm sạch
    # 1. Chuyển đổi timestamp sang datetime
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
    # 2. Loại bỏ dữ liệu trùng lặp
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    
    # 3. Điền giá trị thiếu (Forward Fill sau đó Backward Fill)
    df = df.ffill().bfill()
    
    # 4. Lọc theo ngày nếu có yêu cầu
    if session_date and "session_date" in df.columns:
        df = df[df["session_date"] == str(session_date)]
        
    df_clean = df.sort_values(by="timestamp").reset_index(drop=True)
    if return_info:
        return df_clean, is_real
    return df_clean


def save_real_ticks(df_ticks: pd.DataFrame, session_date: Optional[str] = None) -> Path:
    """
    Lưu trữ dữ liệu thật thu thập được từ NEO API (REST/WebSocket) vào thư mục data/real/.
    Được dùng để tích lũy đủ 5 - 10 phiên kiểm chứng thật theo yêu cầu đề bài.
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
