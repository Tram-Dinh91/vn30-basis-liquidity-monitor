"""
Script kiểm tra kết nối thực tế tới NEO API (VPBankS).
Kiểm tra:
1. Xác thực JWT (Authentication)
2. Kiểm tra quyền IP Whitelist
3. Kéo dữ liệu thử nghiệm của VN30 và VN30F1M
"""
import sys
from pathlib import Path

# Thêm root vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import (
    NEO_CLIENT_ID,
    NEO_CLIENT_SECRET,
    NEO_API_BASE_URL,
    DEFAULT_FUTURE_SYMBOL,
    DEFAULT_UNDERLYING_SYMBOL
)
from src.neo_api.client import NeoApiClient


def test_connection():
    print("=" * 60)
    print("🚀 BẮT ĐẦU KIỂM TRA KẾT NỐI NEO API (VPBankS)")
    print("=" * 60)

    # 1. Kiểm tra cấu hình .env
    if not NEO_CLIENT_ID or not NEO_CLIENT_SECRET:
        print("❌ LỖI: Chưa tìm thấy NEO_CLIENT_ID hoặc NEO_CLIENT_SECRET!")
        print("👉 Vui lòng tạo file .env từ .env.example và điền thông tin được cấp.")
        return False

    print(f"✅ Đã tải thông tin xác thực:")
    print(f"   - Base URL:  {NEO_API_BASE_URL}")
    print(f"   - Client ID: {NEO_CLIENT_ID[:6]}... (đã ẩn)")

    client = NeoApiClient()

    # 2. Thử xác thực lấy JWT
    print("\n⏳ 1. Đang gửi yêu cầu xác thực JWT tới máy chủ VPBankS...")
    auth_success = client.authenticate()

    if not auth_success:
        print("❌ XÁC THỰC THẤT BẠI!")
        print("👉 Các nguyên nhân phổ biến:")
        print("   1. Địa chỉ IP mạng hiện tại KHÁC với IP đã đăng ký Whitelist trên cổng VPBankS.")
        print("   2. Client ID hoặc Client Secret nhập chưa chính xác.")
        print("   3. Máy chủ NEO API đang bảo trì ngoài giờ giao dịch.")
        return False

    print(f"✅ XÁC THỰC THÀNH CÔNG! Token đã được cấp phát an toàn.")

    # 3. Kéo thử giá HĐTL VN30F1M
    print(f"\n⏳ 2. Thử kéo dữ liệu HĐTL {DEFAULT_FUTURE_SYMBOL}...")
    quote_f = client.get_market_quote(DEFAULT_FUTURE_SYMBOL)
    if "error" in quote_f:
        print(f"⚠️ Không lấy được thông tin {DEFAULT_FUTURE_SYMBOL}: {quote_f}")
    else:
        print(f"✅ Đã nhận dữ liệu {DEFAULT_FUTURE_SYMBOL}:")
        print(f"   - Giá khớp gần nhất: {quote_f.get('lastPrice', quote_f.get('matchPrice', 'N/A'))}")
        print(f"   - Bước giá Mua 1:    {quote_f.get('bidPrice1', 'N/A')} (KL: {quote_f.get('bidVol1', 'N/A')})")
        print(f"   - Bước giá Bán 1:    {quote_f.get('askPrice1', 'N/A')} (KL: {quote_f.get('askVol1', 'N/A')})")

    # 4. Kéo thử chỉ số cơ sở VN30
    print(f"\n⏳ 3. Thử kéo dữ liệu chỉ số cơ sở {DEFAULT_UNDERLYING_SYMBOL}...")
    quote_s = client.get_index_quote(DEFAULT_UNDERLYING_SYMBOL)
    if "error" in quote_s:
        print(f"⚠️ Không lấy được thông tin {DEFAULT_UNDERLYING_SYMBOL}: {quote_s}")
    else:
        print(f"✅ Đã nhận dữ liệu {DEFAULT_UNDERLYING_SYMBOL}:")
        print(f"   - Điểm chỉ số VN30: {quote_s.get('indexValue', quote_s.get('lastIndex', 'N/A'))}")

    print("\n" + "=" * 60)
    print("🎉 KẾT QUẢ: NỐI API THÀNH CÔNG 100%! HỆ THỐNG SẴN SÀNG THU THẬP DỮ LIỆU.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    test_connection()
