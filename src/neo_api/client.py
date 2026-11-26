"""
Module giao tiếp với NEO API (VPBankS) qua giao thức REST.
Đặc điểm:
- Xác thực bằng mã truy cập JWT
- Giới hạn tần suất 5 yêu cầu/giây (Rate Limiter)
- Xử lý lỗi kết nối, lỗi IP Whitelist và Timeout
"""
import time
import requests
from typing import Dict, Any, Optional
from src.config import (
    NEO_API_BASE_URL,
    NEO_CLIENT_ID,
    NEO_CLIENT_SECRET,
    MAX_REQUESTS_PER_SECOND
)


class RateLimiter:
    """Giới hạn tần suất gọi API tuân thủ quy định tối đa 5 req/s của NEO API."""
    def __init__(self, max_per_second: int = 5):
        self.interval = 1.0 / max_per_second
        self.last_call = 0.0

    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.time()


class NeoApiClient:
    def __init__(self, client_id: str = None, client_secret: str = None, base_url: str = None):
        self.client_id = client_id or NEO_CLIENT_ID
        self.client_secret = client_secret or NEO_CLIENT_SECRET
        self.base_url = (base_url or NEO_API_BASE_URL).rstrip("/")
        self.rate_limiter = RateLimiter(MAX_REQUESTS_PER_SECOND)
        self.token: Optional[str] = None
        self.token_expiry: float = 0.0

    def authenticate(self) -> bool:
        """
        Xác thực lấy JWT Token từ NEO API.
        Lưu ý: Endpoint này yêu cầu địa chỉ IP đã được Whitelist trên hệ thống VPBankS.
        """
        if not self.client_id or not self.client_secret:
            return False
            
        url = f"{self.base_url}/auth/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        try:
            self.rate_limiter.wait()
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                self.token_expiry = time.time() + expires_in - 60
                return True
            else:
                return False
        except requests.exceptions.RequestException:
            return False

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get_market_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Lấy thông tin giá, 3 bước giá mua - bán và khối lượng của cổ phiếu / HĐTL.
        """
        if not self.token and not self.authenticate():
            return {"error": "AUTH_FAILED_OR_IP_NOT_WHITELISTED", "symbol": symbol}

        url = f"{self.base_url}/market/stock-detail"
        params = {"symbol": symbol}
        try:
            self.rate_limiter.wait()
            res = requests.get(url, headers=self._get_headers(), params=params, timeout=5)
            if res.status_code == 200:
                return res.json()
            return {"error": f"HTTP_{res.status_code}", "detail": res.text}
        except requests.exceptions.RequestException as e:
            return {"error": "CONNECTION_ERROR", "detail": str(e)}

    def get_index_quote(self, index_symbol: str = "VN30") -> Dict[str, Any]:
        """
        Lấy dữ liệu chỉ số cơ sở VN30.
        """
        if not self.token and not self.authenticate():
            return {"error": "AUTH_FAILED_OR_IP_NOT_WHITELISTED", "index": index_symbol}

        url = f"{self.base_url}/market/index-detail"
        params = {"index": index_symbol}
        try:
            self.rate_limiter.wait()
            res = requests.get(url, headers=self._get_headers(), params=params, timeout=5)
            if res.status_code == 200:
                return res.json()
            return {"error": f"HTTP_{res.status_code}", "detail": res.text}
        except requests.exceptions.RequestException as e:
            return {"error": "CONNECTION_ERROR", "detail": str(e)}
