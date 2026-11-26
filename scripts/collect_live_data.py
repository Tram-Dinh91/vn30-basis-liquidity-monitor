"""
Script tự động thu thập & lưu trữ dữ liệu thật từ NEO API (VPBankS).
Mục đích:
- Thu thập liên tục trong phiên giao dịch (hoặc theo chu kỳ 5 giây/lần tuân thủ rate limit).
- Lưu trữ vào data/real/vn30_real_YYYYMMDD.parquet để tích lũy đủ 5 - 10 phiên kiểm chứng.
"""
import time
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import pytz

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import (
    TIMEZONE,
    DEFAULT_FUTURE_SYMBOL,
    DEFAULT_UNDERLYING_SYMBOL
)
from src.neo_api.client import NeoApiClient
from src.data.storage import save_real_ticks


def parse_snapshot(quote_f: dict, quote_s: dict, tz_str: str) -> dict:
    """Chuẩn hóa dữ liệu thô từ API về schema chuẩn của hệ thống."""
    vn_tz = pytz.timezone(tz_str)
    now_ts = datetime.now(vn_tz).strftime("%Y-%m-%d %H:%M:%S")
    session_date = datetime.now(vn_tz).strftime("%Y-%m-%d")

    # Trích xuất giá (có fallback qua các trường thường gặp của NEO API)
    p_f = float(quote_f.get("lastPrice") or quote_f.get("matchPrice") or quote_f.get("closePrice") or 0.0)
    p_s = float(quote_s.get("indexValue") or quote_s.get("lastIndex") or quote_s.get("currentIndex") or 0.0)

    return {
        "timestamp": now_ts,
        "session_date": session_date,
        "underlying_symbol": DEFAULT_UNDERLYING_SYMBOL,
        "underlying_price": p_s,
        "futures_symbol": DEFAULT_FUTURE_SYMBOL,
        "futures_price": p_f,
        "bid_price_1": float(quote_f.get("bidPrice1") or 0.0),
        "bid_vol_1": int(quote_f.get("bidVol1") or 0),
        "bid_price_2": float(quote_f.get("bidPrice2") or 0.0),
        "bid_vol_2": int(quote_f.get("bidVol2") or 0),
        "bid_price_3": float(quote_f.get("bidPrice3") or 0.0),
        "bid_vol_3": int(quote_f.get("bidVol3") or 0),
        "ask_price_1": float(quote_f.get("askPrice1") or 0.0),
        "ask_vol_1": int(quote_f.get("askVol1") or 0),
        "ask_price_2": float(quote_f.get("askPrice2") or 0.0),
        "ask_vol_2": int(quote_f.get("askVol2") or 0),
        "ask_price_3": float(quote_f.get("askPrice3") or 0.0),
        "ask_vol_3": int(quote_f.get("askVol3") or 0),
        "matched_volume": int(quote_f.get("totalMatchVol") or quote_f.get("accumulatedVol") or 0)
    }


def start_collector(interval_seconds: int = 5, max_records: int = 1000):
    client = NeoApiClient()
    if not client.authenticate():
        print("❌ Không thể kết nối hoặc xác thực NEO API. Hãy chạy scripts/test_neo_connection.py trước.")
        return

    print(f"📡 Đang bắt đầu ghi nhận dữ liệu thật...")
    print(f"⏱️ Chu kỳ lấy mẫu: {interval_seconds}s/lần (Tuân thủ Rate Limit 5 req/s)")
    print(f"🛑 Bấm Ctrl + C để dừng thu thập bất kỳ lúc nào.\n")

    records = []
    count = 0

    try:
        while count < max_records:
            quote_f = client.get_market_quote(DEFAULT_FUTURE_SYMBOL)
            quote_s = client.get_index_quote(DEFAULT_UNDERLYING_SYMBOL)

            if "error" not in quote_f and "error" not in quote_s:
                row = parse_snapshot(quote_f, quote_s, TIMEZONE)
                records.append(row)
                count += 1
                basis = row["futures_price"] - row["underlying_price"]
                print(f"[{row['timestamp']}] VN30: {row['underlying_price']} | VN30F: {row['futures_price']} | Basis: {basis:+.2f} | Đã ghi: {count} ticks")

                # Cứ 10 ticks thì lưu tự động vào file parquet một lần
                if len(records) >= 10:
                    df_chunk = pd.DataFrame(records)
                    saved_path = save_real_ticks(df_chunk, session_date=row["session_date"].replace("-", ""))
                    records.clear()
            else:
                print(f"⚠️ Cảnh báo lấy dữ liệu: F={quote_f.get('error')}, S={quote_s.get('error')}")

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n⏹️ Đã dừng thu thập thủ công bởi người dùng.")
    finally:
        if records:
            df_chunk = pd.DataFrame(records)
            saved_path = save_real_ticks(df_chunk)
            print(f"💾 Đã lưu toàn bộ dữ liệu phiên vào: {saved_path}")


if __name__ == "__main__":
    start_collector(interval_seconds=5)
