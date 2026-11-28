"""
Module giao tiếp với NEO API (VPBankS) qua giao thức REST.
Đặc điểm:
- Xác thực bằng mã truy cập JWT (tự động làm mới khi hết hạn)
- Giới hạn tần suất <= 5 yêu cầu/giây (Rate Limiter)
- Chế độ Read-Only tuyệt đối (chỉ gọi endpoint đọc dữ liệu thị trường)
- Chuẩn hóa dấu thời gian về múi giờ Việt Nam (Asia/Ho_Chi_Minh, UTC+7)
- Ghi nhận nhật ký lỗi kết nối phục vụ Resilience Log
"""
import time
import threading
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, List
from src.config import (
    NEO_API_BASE_URL,
    NEO_CLIENT_ID,
    NEO_CLIENT_SECRET,
    MAX_REQUESTS_PER_SECOND,
    TIMEZONE,
)


def normalize_timestamp_vn(ts: Any = None) -> str:
    """Chuẩn hóa dấu thời gian về chuỗi YYYY-MM-DD HH:MM:SS theo múi giờ UTC+7."""
    if ts is None:
        dt = pd.Timestamp.now(tz=TIMEZONE)
    else:
        dt = pd.to_datetime(ts)
        if dt.tzinfo is None:
            dt = dt.tz_localize(TIMEZONE)
        else:
            dt = dt.tz_convert(TIMEZONE)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class RateLimiter:
    """Giới hạn tần suất gọi API tuân thủ quy định tối đa 5 req/s của NEO API."""

    def __init__(self, max_per_second: int = 5):
        max_per_second = max(1, min(int(max_per_second), 5))
        self.max_per_second = max_per_second
        self.interval = 1.0 / max_per_second
        self.last_call = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            elapsed = time.time() - self.last_call
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_call = time.time()


class NeoApiClient:
    """Client REST chỉ đọc (Read-only) cho VPBankS NEO API."""

    READ_ONLY = True

    def __init__(self, client_id: str = None, client_secret: str = None, base_url: str = None):
        self.client_id = client_id if client_id is not None else NEO_CLIENT_ID
        self.client_secret = client_secret if client_secret is not None else NEO_CLIENT_SECRET
        self.base_url = (base_url or NEO_API_BASE_URL).rstrip("/")
        self.rate_limiter = RateLimiter(MAX_REQUESTS_PER_SECOND)
        self.token: Optional[str] = None
        self.token_expiry: float = 0.0
        self.last_error: Optional[str] = None
        self.disconnect_count: int = 0
        self.error_log: List[Dict[str, str]] = []

    def _record_error(self, code: str, detail: str):
        self.last_error = f"{code}: {detail}"
        if code in {"CONNECTION_ERROR", "TIMEOUT", "AUTH_FAILED"}:
            self.disconnect_count += 1
        self.error_log.append({
            "timestamp": normalize_timestamp_vn(),
            "code": code,
            "detail": detail,
        })
        if len(self.error_log) > 50:
            self.error_log = self.error_log[-50:]

    def _is_token_valid(self) -> bool:
        return bool(self.token) and time.time() < self.token_expiry

    def authenticate(self) -> bool:
        """
        Xác thực lấy JWT Token từ NEO API.
        Lưu ý: Endpoint này yêu cầu địa chỉ IP đã được Whitelist trên hệ thống VPBankS.
        """
        if not self.client_id or not self.client_secret:
            self._record_error("AUTH_MISSING_CREDENTIALS", "Thiếu NEO_CLIENT_ID hoặc NEO_CLIENT_SECRET trong .env.")
            return False

        url = f"{self.base_url}/auth/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }
        try:
            self.rate_limiter.wait()
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                self.token_expiry = time.time() + max(60, int(expires_in)) - 60
                self.last_error = None
                return bool(self.token)
            self._record_error("AUTH_FAILED", f"HTTP {response.status_code}")
            return False
        except requests.exceptions.RequestException as exc:
            self._record_error("CONNECTION_ERROR", str(exc))
            return False

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get_market_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Lấy thông tin giá, 3 bước giá mua - bán và khối lượng của cổ phiếu / HĐTL (Read-only).
        """
        if not self._is_token_valid() and not self.authenticate():
            return {"error": "AUTH_FAILED_OR_IP_NOT_WHITELISTED", "symbol": symbol, "detail": self.last_error}

        url = f"{self.base_url}/market/stock-detail"
        params = {"symbol": symbol}
        try:
            self.rate_limiter.wait()
            res = requests.get(url, headers=self._get_headers(), params=params, timeout=5)
            if res.status_code == 200:
                return res.json()
            self._record_error(f"HTTP_{res.status_code}", res.text[:200])
            return {"error": f"HTTP_{res.status_code}", "detail": res.text}
        except requests.exceptions.RequestException as e:
            self._record_error("CONNECTION_ERROR", str(e))
            return {"error": "CONNECTION_ERROR", "detail": str(e)}

    def get_index_quote(self, index_symbol: str = "VN30") -> Dict[str, Any]:
        """
        Lấy dữ liệu chỉ số cơ sở VN30 (Read-only).
        """
        if not self._is_token_valid() and not self.authenticate():
            return {"error": "AUTH_FAILED_OR_IP_NOT_WHITELISTED", "index": index_symbol, "detail": self.last_error}

        url = f"{self.base_url}/market/index-detail"
        params = {"index": index_symbol}
        try:
            self.rate_limiter.wait()
            res = requests.get(url, headers=self._get_headers(), params=params, timeout=5)
            if res.status_code == 200:
                return res.json()
            self._record_error(f"HTTP_{res.status_code}", res.text[:200])
            return {"error": f"HTTP_{res.status_code}", "detail": res.text}
        except requests.exceptions.RequestException as e:
            self._record_error("CONNECTION_ERROR", str(e))
            return {"error": "CONNECTION_ERROR", "detail": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Trả về trạng thái kết nối, chế độ Read-only và nhật ký lỗi gần nhất."""
        return {
            "provider": "VPBankS NEO API",
            "read_only": self.READ_ONLY,
            "rate_limit_rps": self.rate_limiter.max_per_second,
            "timezone": TIMEZONE,
            "authenticated": self._is_token_valid(),
            "disconnect_count": self.disconnect_count,
            "last_error": self.last_error,
            "recent_errors": self.error_log[-5:],
        }


def parse_neo_quotes_to_tick(
    futures_quote: Dict[str, Any],
    index_quote: Dict[str, Any],
    futures_symbol: str = "VN30F1M",
    underlying_symbol: str = "VN30",
) -> Optional[Dict[str, Any]]:
    """
    Chuẩn hóa cặp phản hồi REST/WS từ NEO API về cấu trúc tick thống nhất (UTC+7).
    Trả về None nếu thiếu giá hợp lệ.
    """
    if not futures_quote or not index_quote:
        return None
    if "error" in futures_quote or "error" in index_quote:
        return None

    f_price = futures_quote.get("lastPrice") or futures_quote.get("close") or futures_quote.get("matchPrice")
    u_price = index_quote.get("indexValue") or index_quote.get("lastPrice") or index_quote.get("close")
    if f_price is None or u_price is None:
        return None

    ts_raw = futures_quote.get("timestamp") or index_quote.get("timestamp")
    ts_vn = normalize_timestamp_vn(ts_raw)
    session_date = ts_vn[:10]

    return {
        "timestamp": ts_vn,
        "session_date": session_date,
        "underlying_symbol": underlying_symbol,
        "futures_symbol": futures_symbol,
        "underlying_price": float(u_price),
        "futures_price": float(f_price),
        "bid_price_1": float(futures_quote.get("bidPrice1", f_price)),
        "bid_vol_1": float(futures_quote.get("bidVol1", 0)),
        "bid_price_2": float(futures_quote.get("bidPrice2", f_price)),
        "bid_vol_2": float(futures_quote.get("bidVol2", 0)),
        "bid_price_3": float(futures_quote.get("bidPrice3", f_price)),
        "bid_vol_3": float(futures_quote.get("bidVol3", 0)),
        "ask_price_1": float(futures_quote.get("askPrice1", f_price)),
        "ask_vol_1": float(futures_quote.get("askVol1", 0)),
        "ask_price_2": float(futures_quote.get("askPrice2", f_price)),
        "ask_vol_2": float(futures_quote.get("askVol2", 0)),
        "ask_price_3": float(futures_quote.get("askPrice3", f_price)),
        "ask_vol_3": float(futures_quote.get("askVol3", 0)),
        "matched_volume": int(futures_quote.get("totalVol", 0) or 0),
        "data_source": "NEO_API",
    }
