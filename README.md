# VN30 Futures Basis & Liquidity Risk Monitor
### Hệ thống Giám sát Độ lệch Phái sinh – Cơ sở & Rủi ro Thanh khoản Hợp đồng Tương lai VN30

**Đồ án Cá nhân Cuối kỳ**  
**Học phần:** Gói phần mềm ứng dụng cho tài chính 1 (261BFF401101, 261BFF401102)  
**Trường:** Đại học Kinh tế – Luật, Đại học Quốc gia TP.HCM (Khoa Tài chính – Ngân hàng)  
**Nền tảng dữ liệu cốt lõi:** NEO API (VPBankS) & Bổ trợ SSI FastConnect  

---

## 1. Giới thiệu Tổng quan
Dự án giải quyết 3 bài toán vi cấu trúc thị trường thực tế:
1. **Phân kỳ Basis cực trị:** Nhận diện các giai đoạn thị trường hưng phấn hoặc hoảng loạn quá đà ($|Z_{\text{Basis}}| > 2$).
2. **Rủi ro Thanh khoản & Trượt giá (Slippage):** Theo dõi độ giãn nở của chênh lệch Mua - Bán tương đối (*Relative Bid-Ask Spread*).
3. **Mất cân bằng Sổ lệnh (Order Book Imbalance - OBI):** Khai thác 3 bước giá mua - bán để đo áp lực cung cầu ngắn hạn trước khi giá biến động.

> ⚠️ **Tuân thủ quy định an toàn:** Sản phẩm vận hành 100% ở chế độ **Read-Only / Monitoring / Risk Alert**, tuyệt đối không phát sinh lệnh giao dịch tiền thật.

---

## 2. Kiến trúc Thư mục Dự án 

```text
du-an-neo-api/
├── README.md                 # Hướng dẫn cài đặt, cấu hình, chạy chương trình & giới hạn
├── requirements.txt          # Danh sách thư viện Python cần thiết
├── .env.example              # Mẫu cấu hình biến môi trường (Tuyệt đối không lưu khóa bí mật)
├── .gitignore                # Bỏ qua file nhạy cảm và cache
├── src/
│   ├── neo_api/              # Lớp giao tiếp trực tiếp với NEO API (REST & WebSocket)
│   │   ├── client.py         # Xác thực JWT, Rate Limiter 5 req/s
│   │   └── stream.py         # WebSocket receiver, tự động kết nối lại
│   ├── data/                 # Lớp tiền xử lý & lưu trữ dữ liệu
│   │   ├── storage.py        # Lưu trữ Parquet/CSV, chuẩn hóa UTC+7
│   │   ├── generator.py      # Bộ sinh dữ liệu mẫu 10 phiên phục vụ kiểm chứng 24/7
│   │   └── ssi_client.py     # Bổ trợ SSI FastConnect (đối chiếu chéo)
│   ├── finance/              # Lớp Logic Tài chính
│   │   ├── basis.py          # Tính Basis, Z-score, Fair Basis (Cost of carry), DTE
│   │   ├── liquidity.py      # Relative Spread, Market Depth, Spread Shock
│   │   └── orderbook.py      # Order Book Imbalance (OBI 3 bước giá), Micro-price
│   ├── analytics/            # Lớp Phân tích Nâng cao & Đánh giá Rủi ro
│   │   ├── risk_engine.py    # Hệ thống chấm điểm rủi ro tổng hợp (0 - 100) & Cảnh báo
│   │   └── metrics.py        # Thống kê mô tả chuỗi thời gian (Mean, Std, Median)
│   └── app/                  # Lớp Giao diện Người dùng
│       ├── main.py           # Dashboard tương tác Streamlit (Playback & Live)
│       └── components.py     # KPI cards, biểu đồ Plotly, tháp sổ lệnh nằm ngang
├── tests/                    # Thư mục kiểm thử tự động (Unit Tests đạt 16/16)
│   ├── test_basis.py         # Unit tests cho Basis & Z-score
│   ├── test_liquidity.py     # Unit tests cho Spread & Depth
│   ├── test_orderbook.py     # Unit tests cho OBI & Micro-price
│   ├── test_risk.py          # Unit tests cho hệ thống đánh giá rủi ro
│   └── test_storage.py       # Unit tests cho lưu trữ & đọc dữ liệu
├── data_sample/              # Bộ dữ liệu kiểm chứng 10 phiên (.parquet, .csv)
├── docs/                     # Tài liệu thiết kế & từ điển dữ liệu
│   ├── data_dictionary.md    # Từ điển dữ liệu chuẩn hóa
│   └── architecture.md       # Sơ đồ kiến trúc 6 tầng chi tiết
└── report/                   # Khung Báo cáo cuối kỳ 8-12 trang A4
    └── BAO_CAO_CUOI_KY_TEMPLATE.md # Báo cáo hoàn chỉnh theo 10 phần quy định của Khoa
```

---

## 3. Hướng dẫn Cài đặt & Khởi chạy

### Bước 1: Kích hoạt Thư mục & Môi trường Ảo
```powershell
cd "C:\Users\LENOVO\Downloads\gói 2 - giữa kì"
```

### Bước 2: Cài đặt Thư viện
```powershell
pip install -r requirements.txt
```

### Bước 3: Cấu hình Biến môi trường (Khi kết nối NEO API Live)
1. Sao chép tệp mẫu `.env.example` thành `.env`:
   ```powershell
   copy .env.example .env
   ```
2. Điền `NEO_CLIENT_ID`, `NEO_CLIENT_SECRET`, `NEO_ACCOUNT_NO`.

### Bước 4: Chạy Kiểm thử Tự động (Unit Tests)
```powershell
py -m pytest -v tests/
```

### Bước 5: Khởi chạy Ứng dụng Bảng điều khiển Streamlit
```powershell
py -m streamlit run src/app/main.py
```
*Truy cập bảng điều khiển trên trình duyệt tại: `http://localhost:8501`*

---

## 4. Cấu trúc Dữ liệu & Chế độ Chạy Kiểm chứng (Playback Mode)
Nhằm phục vụ công tác chấm thi và kiểm tra độc lập 24/7 (kể cả khi ngoài giờ giao dịch hoặc chưa bật WebSocket live), ứng dụng tích hợp sẵn **Chế độ Playback 10 Phiên** sử dụng **dữ liệu mô phỏng chuẩn hóa**:
- Tệp dữ liệu mẫu: `data_sample/vn30_futures_10sessions.parquet` (2.400 bản ghi nội ngày qua 10 phiên, múi giờ `Asia/Ho_Chi_Minh`, UTC+7).
- Các trường chính: `timestamp`, `underlying_price` (VN30), `futures_price` (VN30F1M), 3 bước giá Mua - Bán (`bid_price_1..3`, `ask_price_1..3`, `bid_vol_1..3`, `ask_vol_1..3`), `matched_volume`.
- Thể hiện rõ các đợt sốc phân kỳ Basis ($|Z| > 2$) và giãn Spread thực tế để kiểm chứng hệ thống cảnh báo.
- Chi tiết xem tại [docs/data_dictionary.md](docs/data_dictionary.md).

---

## 5. Giới hạn Đã biết (Known Limitations)
1. **Độ sâu sổ lệnh giới hạn 3 bước giá:** Dữ liệu thị trường công khai chỉ cung cấp 3 mức giá Mua/Bán tốt nhất (Level 1–3), chưa phản ánh toàn bộ độ sâu sổ lệnh (Full Order Book).
2. **Ràng buộc IP Whitelist & Giờ giao dịch:** Luồng dữ liệu thật từ NEO API yêu cầu chạy từ địa chỉ IP đã đăng ký với VPBankS và trong giờ giao dịch của HOSE/HNX; ngoài điều kiện này ứng dụng chạy bằng dữ liệu mô phỏng kiểm chứng.
3. **Hiệu ứng ngày đáo hạn (DTE):** Trong tuần đáo hạn HĐTL (thứ Năm tuần thứ 3), Basis hội tụ về 0 theo quy tắc thanh toán nên biến động Z-score có thể bị nhiễu nếu cửa sổ trượt dùng chung với đầu kỳ hạn.
4. **Phạm vi Read-Only:** Hệ thống chỉ giám sát và cảnh báo rủi ro, không hỗ trợ đặt lệnh giao dịch thật.

---

## 6. Tuyên bố Miễn trừ Trách nhiệm
Toàn bộ mã nguồn, dữ liệu và tín hiệu trong đồ án này phục vụ mục đích nghiên cứu học thuật trong khuôn khổ môn học tại Trường ĐH Kinh tế – Luật. Mọi thông tin không cấu thành lời khuyên đầu tư tài chính.
