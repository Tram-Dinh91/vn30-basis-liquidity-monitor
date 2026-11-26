"""
Module sinh dữ liệu mẫu (Mock/Sample Generator) cho 5 - 10 phiên giao dịch.
Mục đích:
1. Đảm bảo ứng dụng chạy mượt mà ngay cả khi thị trường đóng cửa hoặc chưa có IP Whitelist.
2. Cung cấp bộ dữ liệu kiểm chứng chuẩn hóa múi giờ Asia/Ho_Chi_Minh (UTC+7).
3. Đúng quy cách schema của NEO API (VN30F1M và VN30).
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, time
from pathlib import Path
from src.config import DATA_DIR, TIMEZONE


def generate_sample_session_data(num_days: int = 10, ticks_per_day: int = 240) -> pd.DataFrame:
    """
    Sinh chuỗi dữ liệu giả lập thực tế gồm 10 phiên giao dịch gần nhất:
    - VN30 cơ sở: biến động ngẫu nhiên theo mô hình Geometric Brownian Motion quanh mốc 1250 - 1300 điểm.
    - VN30F1M: bám sát VN30 với độ lệch Basis thực tế dao động từ -15 đến +12 điểm, đôi lúc có sốc phân kỳ Z > 2.
    - Sổ lệnh 3 bước giá (Bid1-3, Ask1-3, Vol1-3) phục vụ tính OBI và Relative Spread.
    """
    np.random.seed(42)
    records = []
    
    # Bắt đầu từ 10 ngày trước
    start_date = datetime.now().date() - timedelta(days=num_days + 4)
    valid_days = []
    curr = start_date
    while len(valid_days) < num_days:
        # Bỏ qua Thứ 7, Chủ Nhật
        if curr.weekday() < 5:
            valid_days.append(curr)
        curr += timedelta(days=1)
        
    base_vn30 = 1260.0
    
    for session_date in valid_days:
        session_vn30 = base_vn30 + np.random.normal(0, 10.0)
        # Giả lập thời gian từ 09:00:00 đến 14:30:00
        start_time = datetime.combine(session_date, time(9, 0, 0))
        
        # Bước nhảy thời gian giữa các tick/nến (khoảng 1 phút = 60s)
        time_deltas = [timedelta(minutes=i) for i in range(ticks_per_day)]
        
        # Tạo chuỗi giá VN30 trong phiên
        daily_drift = np.cumsum(np.random.normal(0, 0.4, ticks_per_day))
        vn30_prices = session_vn30 + daily_drift
        
        # Tạo chuỗi Basis (có tính mean-reverting nhưng đôi lúc xuất hiện spike)
        basis_shocks = np.random.normal(0, 1.2, ticks_per_day)
        # Tạo vài nhịp phân kỳ đột biến (Spike)
        if np.random.rand() > 0.6 and ticks_per_day > 30:
            low_idx = min(10, ticks_per_day // 4)
            high_idx = max(low_idx + 1, ticks_per_day - 15)
            spike_idx = np.random.randint(low_idx, high_idx)
            spike_len = min(15, ticks_per_day - spike_idx)
            basis_shocks[spike_idx:spike_idx+spike_len] += np.random.choice([8.5, -9.0])
            
        basis_series = -1.5 + np.cumsum(basis_shocks * 0.2)
        vn30f_prices = vn30_prices + basis_series
        
        for i in range(ticks_per_day):
            timestamp = start_time + time_deltas[i]
            p_vn30 = round(float(vn30_prices[i]), 2)
            p_vn30f = round(float(vn30f_prices[i]), 2)
            
            # Giả lập 3 bước giá HĐTL
            # Bước giá phái sinh tối thiểu 0.1 - 0.2 điểm
            step = 0.2
            # Đôi khi có hiện tượng giãn Spread (Liquidity shock)
            is_shock = (i > 100 and i < 110 and np.random.rand() > 0.5)
            spread_gap = 1.0 if is_shock else step
            
            mid = p_vn30f
            bid1 = round(mid - spread_gap / 2.0, 1)
            ask1 = round(mid + spread_gap / 2.0, 1)
            bid2 = round(bid1 - step, 1)
            ask2 = round(ask1 + step, 1)
            bid3 = round(bid2 - step, 1)
            ask3 = round(ask2 + step, 1)
            
            # Khối lượng 3 bước giá
            bid_vol1 = int(np.random.exponential(50) + 10)
            bid_vol2 = int(np.random.exponential(40) + 10)
            bid_vol3 = int(np.random.exponential(35) + 10)
            
            ask_vol1 = int(np.random.exponential(50) + 10)
            ask_vol2 = int(np.random.exponential(40) + 10)
            ask_vol3 = int(np.random.exponential(35) + 10)
            
            # Tạo mất cân bằng OBI có chủ đích khi giá sắp tăng/giảm
            if i % 30 == 0:
                bid_vol1 *= 4
            elif i % 45 == 0:
                ask_vol1 *= 4
                
            trade_vol = int(np.random.poisson(30) + 5)
            
            records.append({
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "session_date": str(session_date),
                "underlying_symbol": "VN30",
                "underlying_price": p_vn30,
                "futures_symbol": "VN30F1M",
                "futures_price": p_vn30f,
                "bid_price_1": bid1,
                "bid_vol_1": bid_vol1,
                "bid_price_2": bid2,
                "bid_vol_2": bid_vol2,
                "bid_price_3": bid3,
                "bid_vol_3": bid_vol3,
                "ask_price_1": ask1,
                "ask_vol_1": ask_vol1,
                "ask_price_2": ask2,
                "ask_vol_2": ask_vol2,
                "ask_price_3": ask3,
                "ask_vol_3": ask_vol3,
                "matched_volume": trade_vol
            })
            
        base_vn30 = vn30_prices[-1]
        
    df = pd.DataFrame(records)
    return df


def ensure_sample_data_exists() -> Path:
    """Tạo và lưu trữ file parquet mẫu nếu chưa tồn tại."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sample_path = DATA_DIR / "vn30_futures_10sessions.parquet"
    if not sample_path.exists():
        df = generate_sample_session_data(num_days=10, ticks_per_day=240)
        df.to_parquet(sample_path, index=False)
        # Lưu thêm file csv nhỏ để tiện inspect nếu cần
        df.head(100).to_csv(DATA_DIR / "vn30_sample_preview.csv", index=False)
    return sample_path


if __name__ == "__main__":
    path = ensure_sample_data_exists()
    print(f"Đã tạo file dữ liệu mẫu: {path}")
