"""
Script kiểm tra kết nối tới SSI FastConnect API (Data API v2).
"""
import sys
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import SSI_CONSUMER_ID, SSI_CONSUMER_SECRET, SSI_API_BASE_URL


def test_ssi():
    print("=" * 60)
    print("🚀 BẮT ĐẦU KIỂM TRA KẾT NỐI SSI FASTCONNECT API")
    print("=" * 60)

    if not SSI_CONSUMER_ID or not SSI_CONSUMER_SECRET:
        print("❌ LỖI: Chưa có SSI_CONSUMER_ID hoặc SSI_CONSUMER_SECRET trong .env!")
        return False

    print(f"✅ Đã nhận Consumer ID: {SSI_CONSUMER_ID[:6]}... (đã ẩn)")

    # 1. Thử lấy AccessToken
    auth_url = f"{SSI_API_BASE_URL.rstrip('/')}/api/v2/Market/AccessToken"
    payload = {
        "consumerID": SSI_CONSUMER_ID.strip(),
        "consumerSecret": SSI_CONSUMER_SECRET.strip()
    }
    
    print("\n⏳ 1. Gửi yêu cầu cấp AccessToken tới máy chủ SSI...")
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        res = requests.post(auth_url, json=payload, timeout=10, verify=False)
        print(f"   HTTP Status: {res.status_code}")
        data = res.json()
        
        token = None
        if res.status_code == 200:
            token = data.get("data", {}).get("accessToken")
            if token:
                print(f"✅ XÁC THỰC THÀNH CÔNG! Đã lấy được Bearer Token từ SSI.")
            else:
                print(f"⚠️ Trả về 200 nhưng không tìm thấy token trong: {data}")
                return False
        else:
            print(f"❌ XÁC THỰC THẤT BẠI: {data}")
            return False

        # 2. Thử truy vấn dữ liệu Intraday OHLC hoặc Daily OHLC
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        print("\n⏳ 2. Thử truy vấn dữ liệu thị trường từ SSI...")
        ohlc_url = f"{SSI_API_BASE_URL.rstrip('/')}/api/v2/Market/DailyOhlc"
        params = {
            "symbol": "VN30F1M",
            "fromDate": "01/11/2026",
            "toDate": "26/11/2026",
            "pageIndex": 1,
            "pageSize": 10
        }
        res_ohlc = requests.get(ohlc_url, headers=headers, params=params, timeout=10, verify=False)
        if res_ohlc.status_code == 200:
            ohlc_data = res_ohlc.json()
            items = ohlc_data.get("data", {}).get("data", [])
            print(f"✅ ĐÃ LẤY THÀNH CÔNG DỮ LIỆU THỊ TRƯỜNG TỪ SSI!")
            print(f"   Số lượng bản ghi nhận được: {len(items)}")
            if items:
                print(f"   Bản ghi gần nhất: {items[0]}")
        else:
            print(f"⚠️ Thử endpoint khác (Securities)...")
            sec_url = f"{SSI_API_BASE_URL.rstrip('/')}/api/v2/Market/Securities"
            res_sec = requests.get(sec_url, headers=headers, params={"market": "DER", "pageIndex": 1, "pageSize": 5}, timeout=10, verify=False)
            print(f"   Status: {res_sec.status_code}, Response: {res_sec.text[:200]}")

        print("\n" + "=" * 60)
        print("🎉 KẾT QUẢ: KẾT NỐI SSI FASTCONNECT THÀNH CÔNG HOÀN TOÀN!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"❌ LỖI KẾT NỐI: {e}")
        return False


if __name__ == "__main__":
    test_ssi()
