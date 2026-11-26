# KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)
### Dự án: VN30 Futures Basis & Liquidity Risk Monitor

Theo yêu cầu tại Mục 5 của Đề thi cuối kỳ, hệ thống được thiết kế theo mô hình phân tầng chặt chẽ từ nguồn dữ liệu thô đến lớp tương tác của người dùng cuối:

```text
[ TẦNG 1: NGUỒN DỮ LIỆU CỐT LÕI ]
    ├── NEO API (VPBankS): REST API (Quote, Index) + WebSocket Stream (Ticks, 3-level Depth)
    └── SSI FastConnect API (Bổ trợ): Dữ liệu nến lịch sử phục vụ đối chiếu chéo (Cross-validation)
                                │
                                ▼
[ TẦNG 2: THU THẬP & GIAO TIẾP MẠNG ]
    ├── src/neo_api/client.py      -> Xác thực JWT, Rate Limiter (tối đa 5 req/s)
    ├── src/neo_api/stream.py      -> WebSocket Receiver, cơ chế Auto-reconnect với Exponential Backoff
    └── src/data/ssi_client.py     -> Bộ kéo nến lịch sử SSI
                                │
                                ▼
[ TẦNG 3: TIỀN XỬ LÝ & LƯU TRỮ DỮ LIỆU ]
    ├── src/data/storage.py        -> Chuẩn hóa múi giờ Asia/Ho_Chi_Minh (UTC+7), khử trùng lặp (Dedup)
    ├── data_sample/               -> Lưu trữ dữ liệu 10 phiên giao dịch (.parquet, .csv)
    └── src/data/generator.py      -> Bộ sinh dữ liệu mẫu giả lập phục vụ kiểm thử & chấm bài 24/7
                                │
                                ▼
[ TẦNG 4: LOGIC TÀI CHÍNH & MÔ HÌNH HỌA ]
    ├── src/finance/basis.py       -> Công thức Basis, Z-score, Fair Basis (Cost of carry), DTE
    ├── src/finance/liquidity.py   -> Relative Spread (%), Market Depth, Phát hiện sốc thanh khoản
    └── src/finance/orderbook.py   -> Order Book Imbalance (OBI), Micro-price
                                │
                                ▼
[ TẦNG 5: PHÂN TÍCH NÂNG CAO & CẢNH BÁO ]
    ├── src/analytics/risk_engine.py -> Đánh giá rủi ro tổng hợp (0 - 100), Phân loại tín hiệu
    └── src/analytics/metrics.py     -> Thống kê mô tả (Mean, Std, Median, Min, Max)
                                │
                                ▼
[ TẦNG 6: GIAO DIỆN & TƯƠNG TÁC NGƯỜI DÙNG ]
    ├── src/app/main.py            -> Streamlit Dashboard (Chế độ Playback 10 phiên vs Live NEO API)
    ├── src/app/components.py      -> 4 thẻ KPI, Biểu đồ giá & Basis Plotly, Tháp sổ lệnh nằm ngang
    └── Người dùng mục tiêu        -> Nhà đầu tư cá nhân, Nhà giao dịch phái sinh, Chuyên viên quản trị rủi ro
```

---

## Giải thích Nhiệm vụ Từng Tầng

1. **Tầng 1 & 2 (Thu thập dữ liệu):** Bảo đảm NEO API đóng vai trò nguồn dữ liệu chính. Có lớp kiểm soát tần suất gọi API (Rate Limiter) để không vượt quá ngưỡng 5 yêu cầu/giây của VPBankS.
2. **Tầng 3 (Lưu trữ):** Chuyển đổi và lưu trữ dưới định dạng Parquet để tối ưu tốc độ đọc ghi, lọc bỏ các bản ghi trùng lặp và đồng bộ hóa múi giờ Việt Nam.
3. **Tầng 4 & 5 (Logic Tài chính & Phân tích):** Tách biệt hoàn toàn khỏi giao diện để phục vụ việc viết Unit Test độc lập. Không phụ thuộc vào giao diện hiển thị.
4. **Tầng 6 (Giao diện):** Đảm bảo tính minh bạch, hiển thị rõ ràng thời gian cập nhật dữ liệu gần nhất, trạng thái kết nối và lời cảnh báo miễn trừ trách nhiệm học thuật.
