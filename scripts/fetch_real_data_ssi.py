"""
Script kéo dữ liệu THẬT 10+ phiên giao dịch gần nhất từ cổng SSI FastConnect API v3.
Tự động gộp nối tiếp vào file data/real/vn30_real_sessions.parquet (không ghi đè mất phiên cũ).
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.data.ssi_client import sync_latest_ssi_data


def main():
    print("=" * 60)
    print("📡 ĐANG ĐỒNG BỘ DỮ LIỆU THỊ TRƯỜNG THẬT TỪ SSI FASTCONNECT v3")
    print("=" * 60)

    res = sync_latest_ssi_data(days=14)
    if not res.get("success"):
        print(f"❌ LỖI: {res.get('error')}")
        return

    basis = res["latest_futures"] - res["latest_vn30"]
    print("\n🎉 HOÀN TẤT ĐỒNG BỘ DỮ LIỆU THẬT!")
    print(f"📁 Đã lưu tại: {res['file_path']}")
    print(f"🔎 Mã HĐTL VN30: {res['futures_symbol']}")
    print(f"📊 Tổng số bản ghi tích lũy: {res['total_records']} nến 1 phút")
    print(f"📅 Tổng số phiên giao dịch: {res['total_sessions']} phiên ({res['start_date']} -> {res['end_date']})")
    print("\nBản ghi mới nhất:")
    print(f"   - Thời gian: {res['latest_timestamp']}")
    print(f"   - Chỉ số VN30: {res['latest_vn30']} điểm")
    print(f"   - HĐTL {res['futures_symbol']}: {res['latest_futures']} điểm")
    print(f"   - Basis thực tế: {basis:+.2f} điểm")


if __name__ == "__main__":
    main()
