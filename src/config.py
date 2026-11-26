"""
Cấu hình tập trung cho toàn bộ hệ thống VN30 Futures Basis & Liquidity Risk Monitor.
Đọc các biến môi trường từ .env nếu có, fallback về cấu hình mặc định.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Tìm thư mục gốc của project
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data_sample"
CACHE_DIR = BASE_DIR / "data" / "live_cache"

# Load file .env nếu tồn tại
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# Thiết lập múi giờ Việt Nam
TIMEZONE = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")

# Mã tài sản mặc định
DEFAULT_FUTURE_SYMBOL = os.getenv("DEFAULT_FUTURE_SYMBOL", "VN30F1M")
DEFAULT_UNDERLYING_SYMBOL = os.getenv("DEFAULT_UNDERLYING_SYMBOL", "VN30")

# Tham số mô hình tài chính
LOOKBACK_WINDOW_DAYS = int(os.getenv("LOOKBACK_WINDOW_DAYS", "20"))
Z_SCORE_THRESHOLD = float(os.getenv("Z_SCORE_THRESHOLD", "2.0"))
SPREAD_SHOCK_PERCENTILE = float(os.getenv("SPREAD_SHOCK_PERCENTILE", "95.0"))
OBI_EXTREME_THRESHOLD = float(os.getenv("OBI_EXTREME_THRESHOLD", "0.6"))

# Cấu hình API
MAX_REQUESTS_PER_SECOND = int(os.getenv("MAX_REQUESTS_PER_SECOND", "5"))
NEO_API_BASE_URL = os.getenv("NEO_API_BASE_URL", "https://neoinvest.vpbanks.com.vn/neo-openapi")
NEO_WS_URL = os.getenv("NEO_WS_URL", "wss://neoinvest.vpbanks.com.vn/neo-openapi/ws")
NEO_CLIENT_ID = os.getenv("NEO_CLIENT_ID", "")
NEO_CLIENT_SECRET = os.getenv("NEO_CLIENT_SECRET", "")
NEO_ACCOUNT_NO = os.getenv("NEO_ACCOUNT_NO", "")

SSI_CONSUMER_ID = os.getenv("SSI_CONSUMER_ID", "")
SSI_CONSUMER_SECRET = os.getenv("SSI_CONSUMER_SECRET", "")
SSI_API_BASE_URL = os.getenv("SSI_API_BASE_URL", "https://fc-data.ssi.com.vn")
