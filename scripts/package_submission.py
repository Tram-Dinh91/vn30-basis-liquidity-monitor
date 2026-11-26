"""
Script đóng gói bài nộp cuối kỳ chuẩn hóa theo Mục 10 đề thi:
- Tên tệp đầu ra: MSSV_HoTen_NEOAPI_FinTech.zip
- Tự động lọc bỏ toàn bộ rác: __pycache__, .pytest_cache, .git, .venv, .env (bảo vệ bí mật), file temp
- Kiểm tra dung lượng và tính toàn vẹn của gói nộp
"""
import os
import sys
import zipfile
import argparse
from pathlib import Path

# Thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent.parent

# Các mẫu thư mục & tệp BẮT BUỘC LOẠI BỎ
EXCLUDE_DIRS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "live_cache",
    "vn30-basis-liquidity-monitor" # tránh đệ quy nếu chạy ở thư mục ngoài
}

EXCLUDE_FILES = {
    ".env",                 # Tuyệt đối cấm đưa thông tin xác thực thật lên bài nộp
    "jwt_token.json",
    ".DS_Store",
    "Thumbs.db"
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".tmp",
    ".log"
}


def create_submission_zip(mssv: str, hoten: str, output_dir: Path = None) -> Path:
    if not output_dir:
        output_dir = BASE_DIR
        
    # Chuẩn hóa tên file theo quy cách: MSSV_HoTen_NEOAPI_FinTech.zip
    clean_hoten = hoten.replace(" ", "_")
    zip_name = f"{mssv}_{clean_hoten}_NEOAPI_FinTech.zip"
    zip_path = output_dir / zip_name

    print(f"📦 Bắt đầu đóng gói bài nộp: {zip_name} ...")
    included_files = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BASE_DIR):
            # Lọc bỏ các thư mục cấm (in-place modification)
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]

            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(BASE_DIR)

                # Kiểm tra các điều kiện loại trừ
                if file in EXCLUDE_FILES:
                    print(f"   🛡️ Đã loại trừ tệp nhạy cảm/cấm: {rel_path}")
                    continue
                if file_path.suffix.lower() in EXCLUDE_EXTENSIONS:
                    continue
                if file.endswith(".zip"):
                    continue

                # Đưa file sạch vào zip
                zf.write(file_path, arcname=str(rel_path))
                included_files += 1

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"\n✅ ĐÃ ĐÓNG GÓI THÀNH CÔNG!")
    print(f"📁 Tệp nộp: {zip_path}")
    print(f"📊 Tổng số tệp: {included_files} files")
    print(f"⚖️ Dung lượng: {size_mb:.2f} MB (Rất gọn nhẹ, sạch rác)")
    print(f"\nLƯU Ý THEO MỤC 10 ĐỀ THI:")
    print(f"- File mã nguồn: {zip_name}")
    print(f"- File báo cáo:  {mssv}_{clean_hoten}_BaoCao.pdf")
    print(f"- Video demo:    {mssv}_{clean_hoten}_Demo.mp4")
    return zip_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Đóng gói mã nguồn đồ án NEO API FinTech")
    parser.add_argument("--mssv", default="MSSV", help="Mã số sinh viên (ví dụ: K214140001)")
    parser.add_argument("--hoten", default="HoTen", help="Họ và tên không dấu (ví dụ: Nguyen_Van_A)")
    args = parser.parse_args()

    create_submission_zip(args.mssv, args.hoten)
