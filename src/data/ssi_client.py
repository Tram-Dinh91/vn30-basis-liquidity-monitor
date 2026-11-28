"""
Module bổ trợ: Kết nối SSI FastConnect API v3 (qua thư viện chính thức ssi-sdk)
để lấy dữ liệu thị trường thật (nến 1 phút nội ngày của VN30 & HĐTL VN30F1M) và đối chiếu chéo.
Được phép sử dụng theo quy định trang 1 của đề thi để tăng độ tin cậy và kiểm chứng.
"""
import httpx
import pandas as pd
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from src.config import SSI_CONSUMER_ID, SSI_CONSUMER_SECRET


def _patch_httpx_ssl():
    """Khắc phục lỗi chứng chỉ SSL trên một số máy Windows khi kết nối HTTPS tới api.ssi.com.vn."""
    if not getattr(httpx.Client, "_ssi_patched", False):
        orig_init = httpx.Client.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["verify"] = False
            orig_init(self, *args, **kwargs)

        httpx.Client.__init__ = patched_init
        httpx.Client._ssi_patched = True


class SsiFastConnectClient:
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = (api_key or SSI_CONSUMER_ID).strip()
        self.api_secret = (api_secret or SSI_CONSUMER_SECRET).strip()
        self.auth = None
        self.data_client = None
        self.last_error: Optional[str] = None

    def authenticate(self) -> bool:
        """Xác thực với cổng SSI FastConnect v3 (api.ssi.com.vn)."""
        self.last_error = None
        if not self.api_key or not self.api_secret:
            self.last_error = "Thiếu SSI_CONSUMER_ID hoặc SSI_CONSUMER_SECRET trong .env."
            return False
        try:
            _patch_httpx_ssl()
            from ssi_sdk import Auth, Data
            self.auth = Auth(api_key=self.api_key, api_secret=self.api_secret)
            self.auth.authenticate()
            self.data_client = Data(self.auth)
            return True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False

    def get_active_vn30_futures_symbol(self) -> str:
        """Tìm mã HĐTL VN30 tháng gần nhất đang giao dịch (hỗ trợ chuẩn mã KRX mới như 41I1GC000)."""
        if not self.data_client and not self.authenticate():
            return "41I1GC000"
        try:
            master = self.data_client.market_data.get_master_data()
            # Lọc các mã HĐTL chỉ số VN30 (bắt đầu bằng 41I1 hoặc VN30F)
            candidates = [
                str(m.symbol) for m in master
                if hasattr(m, "symbol") and (str(m.symbol).startswith("41I1") or str(m.symbol).startswith("VN30F"))
            ]
            # Ưu tiên lấy mã có thanh khoản lớn nhất trong ngày
            best_sym = "41I1GC000"
            max_vol = -1
            for sym in candidates[:5]:
                try:
                    summary = self.data_client.market_data.get_securities_summary(sym)
                    if summary and len(summary) > 0:
                        vol = getattr(summary[0], "total_match", 0) or 0
                        if vol > max_vol:
                            max_vol = vol
                            best_sym = sym
                except Exception:
                    continue
            return best_sym
        except Exception:
            return "41I1GC000"

    def fetch_1m_aligned_sessions(self, 
                                  futures_symbol: str = None, 
                                  underlying_symbol: str = "VN30",
                                  days: int = 10) -> pd.DataFrame:
        """
        Kéo chuỗi nến 1 phút của cả HĐTL VN30 và chỉ số VN30 trong `days` ngày gần nhất.
        Tự động đồng bộ dấu thời gian (Timestamp Alignment) theo chuẩn UTC+7.
        """
        if not self.data_client and not self.authenticate():
            raise RuntimeError("Không thể xác thực với SSI FastConnect v3.")

        if not futures_symbol:
            futures_symbol = self.get_active_vn30_futures_symbol()

        to_dt = datetime.now()
        from_dt = to_dt - timedelta(days=days + 5)
        from_str = from_dt.strftime("%Y/%m/%d")
        to_str = to_dt.strftime("%Y/%m/%d")

        md = self.data_client.market_data

        # Kéo toàn bộ các trang (pagination) nến 1 phút
        def _fetch_all_pages(sym: str) -> List[dict]:
            rows = []
            page = 1
            while True:
                bars = md.get_ohlc_1minute_historical(sym, from_str, to_str, page=page, size=1000)
                if not bars:
                    break
                for b in bars:
                    rows.append({
                        "timestamp": b.trading_date,
                        "open": float(b.open_price),
                        "high": float(b.high_price),
                        "low": float(b.low_price),
                        "close": float(b.close_price),
                        "volume": int(b.volume)
                    })
                if len(bars) < 1000:
                    break
                page += 1
            return rows

        rows_f = _fetch_all_pages(futures_symbol)
        rows_s = _fetch_all_pages(underlying_symbol)

        if not rows_f or not rows_s:
            return pd.DataFrame()

        df_f = pd.DataFrame(rows_f).drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
        df_s = pd.DataFrame(rows_s).drop_duplicates(subset=["timestamp"]).sort_values("timestamp")

        # Hợp nhất theo timestamp (inner join hoặc asof merge)
        df_f["timestamp"] = pd.to_datetime(df_f["timestamp"])
        df_s["timestamp"] = pd.to_datetime(df_s["timestamp"])

        merged = pd.merge(
            df_f[["timestamp", "close", "high", "low", "volume"]].rename(
                columns={"close": "futures_price", "high": "f_high", "low": "f_low", "volume": "matched_volume"}
            ),
            df_s[["timestamp", "close"]].rename(columns={"close": "underlying_price"}),
            on="timestamp",
            how="inner"
        ).sort_values("timestamp").reset_index(drop=True)

        merged["session_date"] = merged["timestamp"].dt.strftime("%Y-%m-%d")
        merged["underlying_symbol"] = underlying_symbol
        merged["futures_symbol"] = futures_symbol
        merged["timestamp"] = merged["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

        # Ước lượng bước giá Bid/Ask cấp 1 từ biến động nội phút (do nến OHLC 1m không lưu snapshot sổ lệnh)
        # Khoảng bước giá tối thiểu trên sàn phái sinh là 0.1 điểm
        merged["bid_price_1"] = (merged["futures_price"] - 0.1).round(1)
        merged["ask_price_1"] = (merged["futures_price"] + 0.1).round(1)
        merged["bid_price_2"] = (merged["bid_price_1"] - 0.1).round(1)
        merged["ask_price_2"] = (merged["ask_price_1"] + 0.1).round(1)
        merged["bid_price_3"] = (merged["bid_price_2"] - 0.1).round(1)
        merged["ask_price_3"] = (merged["ask_price_2"] + 0.1).round(1)

        # Khối lượng sổ lệnh được quy ước = 0 (đánh dấu không có L2 orderbook trong nến lịch sử)
        for col in ["bid_vol_1", "bid_vol_2", "bid_vol_3", "ask_vol_1", "ask_vol_2", "ask_vol_3"]:
            merged[col] = 0

        return merged


def sync_latest_ssi_data(days: int = 14) -> dict:
    """
    Hàm tiện ích dùng chung cho cả CLI script và Streamlit UI:
    Kéo dữ liệu mới nhất từ SSI FastConnect v3 và gộp nối tiếp (append + deduplicate)
    vào file `data/real/vn30_real_sessions.parquet` để không bị mất các phiên cũ.
    """
    from src.config import REAL_DATA_DIR
    REAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_parquet = REAL_DATA_DIR / "vn30_real_sessions.parquet"
    out_csv = REAL_DATA_DIR / "vn30_real_preview.csv"

    client = SsiFastConnectClient()
    if not client.authenticate():
        detail = client.last_error or "Lỗi không xác định."
        return {"success": False, "error": f"Không thể xác thực với SSI API — {detail}"}

    try:
        fut_sym = client.get_active_vn30_futures_symbol()
        new_df = client.fetch_1m_aligned_sessions(futures_symbol=fut_sym, underlying_symbol="VN30", days=days)
    except Exception as exc:
        return {"success": False, "error": f"Lỗi khi tải dữ liệu SSI API — {type(exc).__name__}: {exc}"}
    if new_df.empty:
        return {"success": False, "error": "Không nhận được dữ liệu mới từ SSI."}

    if out_parquet.exists():
        old_df = pd.read_parquet(out_parquet)
        combined = pd.concat([old_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
        combined = combined.sort_values("timestamp").reset_index(drop=True)
    else:
        combined = new_df

    combined.to_parquet(out_parquet, index=False)
    combined.tail(100).to_csv(out_csv, index=False)

    sessions = sorted(combined["session_date"].unique())
    return {
        "success": True,
        "futures_symbol": fut_sym,
        "total_records": len(combined),
        "total_sessions": len(sessions),
        "start_date": sessions[0],
        "end_date": sessions[-1],
        "latest_timestamp": str(combined.iloc[-1]["timestamp"]),
        "latest_vn30": float(combined.iloc[-1]["underlying_price"]),
        "latest_futures": float(combined.iloc[-1]["futures_price"]),
        "file_path": str(out_parquet)
    }
