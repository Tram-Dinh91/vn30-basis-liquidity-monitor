# TỪ ĐIỂN DỮ LIỆU (DATA DICTIONARY)
### Dự án: VN30 Futures Basis & Liquidity Risk Monitor

Tài liệu này chuẩn hóa và định nghĩa chi tiết mọi biến dữ liệu thu thập từ **NEO API (VPBankS)** và các chỉ số tài chính phái sinh được tính toán trong hệ thống.

---

## 1. Dữ liệu Thu thập từ NEO API (Raw Data)

| Tên biến | Kiểu dữ liệu | Đơn vị | Múi giờ / Định dạng | Mô tả kinh tế / tài chính | Endpoint / Nguồn |
| :--- | :---: | :---: | :---: | :--- | :--- |
| `timestamp` | Datetime | - | `YYYY-MM-DD HH:MM:SS` (Asia/Ho_Chi_Minh, UTC+7) | Dấu thời gian ghi nhận bản ghi | WebSocket / REST |
| `session_date` | String | - | `YYYY-MM-DD` | Ngày của phiên giao dịch | Hệ thống |
| `underlying_symbol`| String | - | `VN30` | Mã chỉ số cơ sở đại diện rổ 30 cổ phiếu lớn | `/market/index-detail` |
| `underlying_price` | Float | Điểm | 2 chữ số thập phân | Giá trị chỉ số VN30 hiện tại | `/market/index-detail` |
| `futures_symbol` | String | - | `VN30F1M` | Mã hợp đồng tương lai tháng gần nhất | `/market/stock-detail` |
| `futures_price` | Float | Điểm | 1 chữ số thập phân | Giá khớp gần nhất của HĐTL VN30F1M | `/market/stock-detail` |
| `bid_price_1,2,3` | Float | Điểm | 1 chữ số thập phân | 3 mức giá đặt mua tốt nhất (Level 1, 2, 3) | Sổ lệnh Order Book |
| `bid_vol_1,2,3` | Integer | HĐ | Số nguyên dương | Khối lượng đặt mua tương ứng tại 3 mức giá | Sổ lệnh Order Book |
| `ask_price_1,2,3` | Float | Điểm | 1 chữ số thập phân | 3 mức giá đặt bán tốt nhất (Level 1, 2, 3) | Sổ lệnh Order Book |
| `ask_vol_1,2,3` | Integer | HĐ | Số nguyên dương | Khối lượng đặt bán tương ứng tại 3 mức giá | Sổ lệnh Order Book |
| `matched_volume` | Integer | HĐ | Số nguyên dương | Khối lượng khớp của tick giao dịch | Khớp lệnh thị trường |

---

## 2. Các Biến số Phân tích Tài chính (Calculated Financial Metrics)

| Tên biến | Công thức tính | Miền giá trị | Ý nghĩa tài chính & Ứng dụng |
| :--- | :--- | :---: | :--- |
| `basis` | $P_{\text{VN30F1M}} - P_{\text{VN30}}$ | $(-\infty, +\infty)$ (Điểm) | Độ lệch giá giữa phái sinh và cơ sở. Đo lường kỳ vọng thị trường và chi phí vốn ngắn hạn. |
| `z_basis` | $\frac{\text{Basis}_t - \mu_{20}}{\sigma_{20}}$ | Chuẩn hóa $(\sigma)$ | $Z$-score trượt 20 phiên. Khi $|Z| > 2.0$, thị trường rơi vào trạng thái hưng phấn hoặc hoảng loạn cực độ. |
| `relative_spread` | $\frac{\text{Ask}_1 - \text{Bid}_1}{\frac{1}{2}(\text{Ask}_1 + \text{Bid}_1)} \times 100$ | $[0\%, +\infty)$ | Chênh lệch Mua - Bán tương đối. Đo lường chi phí giao dịch ẩn và rủi ro trượt giá (slippage). |
| `obi` (Order Book Imbalance) | $\frac{\sum_{i=1}^3 V_{\text{Bid},i} - \sum_{i=1}^3 V_{\text{Ask},i}}{\sum_{i=1}^3 V_{\text{Bid},i} + \sum_{i=1}^3 V_{\text{Ask},i}}$ | $[-1.0, 1.0]$ | Mất cân bằng sổ lệnh 3 bước giá. Nhận diện áp lực dồn lệnh mua ($> +0.6$) hoặc xả bán ($< -0.6$). |
| `micro_price` | $\frac{P_{\text{Bid},1} \cdot V_{\text{Ask},1} + P_{\text{Ask},1} \cdot V_{\text{Bid},1}}{V_{\text{Bid},1} + V_{\text{Ask},1}}$ | Điểm | Giá vi mô có trọng số khối lượng, dự báo chiều hướng biến động của tick tiếp theo. |
| `dte` | $\text{Expiry Date} - \text{Current Date}$ | $[0, 31]$ (Ngày) | Số ngày còn lại đến thứ Năm tuần thứ 3 (ngày đáo hạn hợp đồng). |
| `fair_basis` | $S \cdot (r - q) \cdot \frac{\text{DTE}}{365}$ | Điểm | Basis lý thuyết theo mô hình Chi phí vốn nắm giữ (Cost-of-Carry Model). |
| `risk_score` | Chấm điểm rủi ro tổng hợp | $[0, 100]$ | Thang đo định lượng mức độ rủi ro hệ thống: Bình thường ($<35$), Chú ý ($35-65$), Rủi ro cao ($>65$). |
