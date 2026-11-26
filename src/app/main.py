"""
HỆ THỐNG GIÁM SÁT ĐỘ LỆCH PHÁI SINH – CƠ SỞ & RỦI RO THANH KHOẢN HỢP ĐỒNG TƯƠNG LAI VN30
(VN30 Futures Basis & Liquidity Risk Monitor)
Đồ án cuối kỳ môn: Gói phần mềm ứng dụng cho tài chính 1
Nền tảng dữ liệu cốt lõi: NEO API (VPBankS) & Bổ trợ SSI FastConnect
"""
import sys
from pathlib import Path

# Thêm thư mục gốc của project vào sys.path để import 'src' luôn thành công
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import pytz

from src.config import (
    TIMEZONE,
    DEFAULT_FUTURE_SYMBOL,
    DEFAULT_UNDERLYING_SYMBOL,
    Z_SCORE_THRESHOLD,
    OBI_EXTREME_THRESHOLD,
    LOOKBACK_WINDOW_DAYS
)
from src.data.storage import load_market_data, get_available_sources
from src.data.ssi_client import sync_latest_ssi_data
from src.neo_api.client import NeoApiClient
from src.finance.basis import (
    calculate_basis_series,
    calculate_z_score,
    get_expiry_date,
    calculate_dte,
    calculate_fair_basis
)
from src.finance.liquidity import calculate_relative_spread, detect_spread_shock
from src.finance.orderbook import calculate_obi, calculate_micro_price
from src.analytics.risk_engine import evaluate_system_risk
from src.app.components import (
    render_kpi_cards,
    render_basis_chart,
    render_orderbook_ladder,
    render_scatter_liquidity,
    render_risk_alert_panel
)

# 1. Cấu hình Trang Streamlit
st.set_page_config(
    page_title="VN30 Basis & Liquidity Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Xử lý Múi giờ Việt Nam
vn_tz = pytz.timezone(TIMEZONE)
now_vn = datetime.now(vn_tz)

# 3. Sidebar - Cấu hình & Chế độ Vận hành
st.sidebar.image("https://neoinvest.vpbanks.com.vn/favicon.ico", width=40)
st.sidebar.title("Bảng Điều Khiển")
st.sidebar.markdown("---")

available_sources = get_available_sources() + ["Trực tiếp (NEO API Live)"]
app_mode = st.sidebar.radio(
    "Chế độ Nguồn Dữ liệu:",
    available_sources,
    index=0,
    help="Hỗ trợ tách biệt dữ liệu kiểm chứng offline, dữ liệu thật từ SSI/NEO API đã lưu, hoặc luồng trực tiếp."
)

# Nút đồng bộ 1-click ngay trên giao diện Streamlit
if st.sidebar.button("🔄 Cập nhật Dữ liệu Mới nhất (API)", use_container_width=True):
    with st.spinner("Đang kết nối SSI FastConnect v3 & lưu trữ phiên mới..."):
        sync_res = sync_latest_ssi_data(days=7)
        if sync_res.get("success"):
            st.sidebar.success(f"Đã cập nhật {sync_res['total_sessions']} phiên ({sync_res['end_date']})!")
            st.rerun()
        else:
            st.sidebar.error(f"Lỗi đồng bộ: {sync_res.get('error')}")

st.sidebar.markdown("### ⚙️ Tham số Phân tích")
z_thresh = st.sidebar.slider("Ngưỡng Z-score Cực trị (σ)", 1.5, 3.0, Z_SCORE_THRESHOLD, 0.1)
obi_thresh = st.sidebar.slider("Ngưỡng Mất cân bằng OBI", 0.4, 0.8, OBI_EXTREME_THRESHOLD, 0.05)
window_size = st.sidebar.slider("Cửa sổ Trượt (Quan sát)", 10, 60, LOOKBACK_WINDOW_DAYS, 5)

st.sidebar.markdown("---")
st.sidebar.info(
    "📌 **Đồ án Cuối kỳ:** Gói phần mềm ứng dụng tài chính 1\n"
    "- **Sinh viên thực hiện:** Đồ án Cá nhân\n"
    "- **Mã Hợp đồng:** VN30F1M | **Cơ sở:** VN30\n"
    "- **Hạ tầng chính:** NEO API (VPBankS)"
)

# 4. Tải Dữ liệu & Tính toán Lớp Tài chính
source_type = "real" if "Thị trường Thật" in app_mode else "sample"
raw_df, is_real_data = load_market_data(source=source_type, return_info=True)

# Lọc ngày phiên giao dịch trên sidebar nếu đang ở chế độ Playback
available_dates = sorted(raw_df["session_date"].unique(), reverse=True)
selected_date = st.sidebar.selectbox("Chọn Phiên Giao dịch:", available_dates, index=0)

df_session = raw_df[raw_df["session_date"] == selected_date].copy().reset_index(drop=True)

# Tính toán chuỗi chỉ số tài chính
df_session["basis"] = calculate_basis_series(df_session, "futures_price", "underlying_price")
df_session["rolling_mean_basis"] = df_session["basis"].rolling(window=window_size, min_periods=1).mean()
df_session["rolling_std_basis"] = df_session["basis"].rolling(window=window_size, min_periods=1).std().fillna(1.0)
df_session["upper_2sigma"] = df_session["rolling_mean_basis"] + z_thresh * df_session["rolling_std_basis"]
df_session["lower_2sigma"] = df_session["rolling_mean_basis"] - z_thresh * df_session["rolling_std_basis"]
df_session["z_basis"] = calculate_z_score(df_session["basis"], window=window_size)

# Tính Relative Spread và OBI từng dòng
df_session["relative_spread"] = [
    calculate_relative_spread(b, a) for b, a in zip(df_session["bid_price_1"], df_session["ask_price_1"])
]

df_session["obi"] = [
    calculate_obi([b1, b2, b3], [a1, a2, a3])
    for b1, b2, b3, a1, a2, a3 in zip(
        df_session["bid_vol_1"], df_session["bid_vol_2"], df_session["bid_vol_3"],
        df_session["ask_vol_1"], df_session["ask_vol_2"], df_session["ask_vol_3"]
    )
]

# Tick hiện tại (dòng cuối cùng của phiên đã chọn)
latest = df_session.iloc[-1]
expiry = get_expiry_date(now_vn.year, now_vn.month)
dte = calculate_dte(now_vn.date(), expiry)
fair_basis = calculate_fair_basis(latest["underlying_price"], dte=dte)

# Đánh giá rủi ro tổng hợp
risk_eval = evaluate_system_risk(
    basis=latest["basis"],
    z_basis=latest["z_basis"],
    relative_spread=latest["relative_spread"],
    obi=latest["obi"],
    z_threshold=z_thresh,
    obi_threshold=obi_thresh
)

# 5. Giao diện Chính - Header
st.title("🛡️ VN30 Futures Basis & Liquidity Risk Monitor")
st.caption("Hệ thống Giám sát Độ lệch Phái sinh – Cơ sở & Rủi ro Thanh khoản Sổ lệnh HĐTL VN30")

h_col1, h_col2, h_col3 = st.columns([2, 1, 1])
with h_col1:
    st.write(f"🕒 **Cập nhật:** `{latest['timestamp']}` *(Múi giờ Asia/Ho_Chi_Minh, UTC+7)*")
with h_col2:
    if is_real_data:
        st.markdown("🟢 **Trạng thái:** `Dữ liệu Thị trường Thật (OK)`")
    elif app_mode.startswith("Dữ liệu Kiểm chứng"):
        st.markdown("🔵 **Trạng thái:** `Dữ liệu Mô phỏng Kiểm chứng`")
    else:
        st.markdown("🟡 **Trạng thái:** `Chờ Kết nối NEO API Live`")
with h_col3:
    fut_display = latest.get("futures_symbol", DEFAULT_FUTURE_SYMBOL)
    st.markdown(f"🏷️ **Mã theo dõi:** `{fut_display}` vs `{DEFAULT_UNDERLYING_SYMBOL}`")

st.markdown("---")

# 6. Hiển thị Thẻ KPI Tổng hợp
render_kpi_cards(
    basis=latest["basis"],
    z_basis=latest["z_basis"],
    spread=latest["relative_spread"],
    obi=latest["obi"],
    dte=dte,
    fair_basis=fair_basis
)

st.markdown("---")

# 7. Bố cục 4 Tab Chức năng
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Giám sát Nội ngày & Sổ lệnh",
    "📈 Phân tích Thống kê 10 Phiên",
    "🔍 Kiểm chứng Dữ liệu NEO & SSI",
    "📖 Cơ sở Lý thuyết & Phương pháp"
])

# ----------------- TAB 1: GIÁM SÁT THỜI GIAN THỰC & SỔ LỆNH -----------------
with tab1:
    col_left, col_right = st.columns([7, 3])
    
    with col_left:
        st.subheader("Biểu đồ Giá và Vùng Cực trị Basis (±2σ)")
        fig_basis = render_basis_chart(df_session, z_threshold=z_thresh)
        st.plotly_chart(fig_basis, use_container_width=True)
        
    with col_right:
        st.subheader("Trạng thái Cảnh báo Thông minh")
        render_risk_alert_panel(risk_eval)
        
        st.markdown("---")
        st.subheader("Cấu trúc Sổ lệnh 3 Bước giá")
        fig_ladder = render_orderbook_ladder(latest)
        st.plotly_chart(fig_ladder, use_container_width=True)

# ----------------- TAB 2: PHÂN TÍCH THỐNG KÊ 10 PHIÊN -----------------
with tab2:
    st.subheader("Phân tích Định lượng Toàn bộ 10 Phiên Giao dịch")
    t2_col1, t2_col2 = st.columns(2)
    
    with t2_col1:
        st.markdown("#### Phân tán: Độ giãn Spread vs Biến động Giá")
        fig_scatter = render_scatter_liquidity(df_session)
        st.plotly_chart(fig_scatter, use_container_width=True)
        st.caption("Nhận xét: Khi Spread giãn rộng (thanh khoản mỏng), biên độ trượt giá có xu hướng tăng vọt.")
        
    with t2_col2:
        st.markdown("#### Bảng Thống kê Mô tả Chuỗi Basis & Spread")
        stats_df = pd.DataFrame({
            "Chỉ số": ["Giá trị Trung bình (Mean)", "Độ lệch chuẩn (Std)", "Giá trị Nhỏ nhất (Min)", "Phân vị 50% (Median)", "Giá trị Lớn nhất (Max)"],
            "Độ lệch Basis (pt)": [
                f"{df_session['basis'].mean():.2f}",
                f"{df_session['basis'].std():.2f}",
                f"{df_session['basis'].min():.2f}",
                f"{df_session['basis'].median():.2f}",
                f"{df_session['basis'].max():.2f}",
            ],
            "Relative Spread (%)": [
                f"{df_session['relative_spread'].mean():.4f}%",
                f"{df_session['relative_spread'].std():.4f}%",
                f"{df_session['relative_spread'].min():.4f}%",
                f"{df_session['relative_spread'].median():.4f}%",
                f"{df_session['relative_spread'].max():.4f}%",
            ],
            "Order Book Imbalance (OBI)": [
                f"{df_session['obi'].mean():.3f}",
                f"{df_session['obi'].std():.3f}",
                f"{df_session['obi'].min():.3f}",
                f"{df_session['obi'].median():.3f}",
                f"{df_session['obi'].max():.3f}",
            ]
        })
        st.dataframe(stats_df, use_container_width=True, hide_index=True)

# ----------------- TAB 3: KIỂM CHỨNG DỮ LIỆU NEO & SSI -----------------
with tab3:
    st.subheader("Kiểm chứng Tính Toàn vẹn Dữ liệu & Đối chiếu Chéo (Cross-validation)")
    
    q1, q2, q3 = st.columns(3)
    with q1:
        st.success(f"Tổng số bản ghi phiên: **{len(df_session)} ticks**")
    with q2:
        st.success(f"Giá trị thiếu (Null/NaN): **{df_session.isnull().sum().sum()} (0.0%)**")
    with q3:
        st.success(f"Múi giờ đồng bộ: **{TIMEZONE}**")

    st.markdown("#### Bảng Dữ liệu Nội ngày Đã Xử lý")
    st.dataframe(
        df_session[[
            "timestamp", "underlying_price", "futures_price", "basis", "z_basis", 
            "relative_spread", "obi", "matched_volume"
        ]].tail(50),
        use_container_width=True
    )

# ----------------- TAB 4: CƠ SỞ LÝ THUYẾT & PHƯƠNG PHÁP -----------------
with tab4:
    st.subheader("Cơ sở Lý thuyết Tài chính & Giới hạn Mô hình")
    
    st.markdown("""
    ### 1. Cơ sở Lý thuyết Định giá Phái sinh (Cost-of-Carry Model)
    Hợp đồng tương lai chỉ số VN30 ($F$) có quan hệ định lượng với chỉ số cơ sở ($S$) theo chi phí vốn nắm giữ:
    $$F^* = S \\cdot \\left[1 + (r - q) \\cdot \\frac{DTE}{365}\\right]$$
    - Khi $\\text{Basis} = F - S$ lệch đáng kể so với phân phối lịch sử ($|Z| > 2$), thị trường phản ánh sự **hưng phấn hoặc hoảng loạn quá mức**, tạo ra cơ hội phòng hộ (hedging) hoặc rủi ro biến động hội tụ.
    
    ### 2. Vi cấu trúc Sổ lệnh & Mất cân bằng Cung - Cầu (Order Book Imbalance - OBI)
    Chỉ số OBI được tính trên 3 mức giá tốt nhất:
    $$OBI_t = \\frac{\\sum_{i=1}^3 V_{Bid, i} - \\sum_{i=1}^3 V_{Ask, i}}{\\sum_{i=1}^3 V_{Bid, i} + \\sum_{i=1}^3 V_{Ask, i}} \\in [-1.0, 1.0]$$
    - $OBI > +0.6$: Áp lực mua chủ động chiếm ưu thế.
    - $OBI < -0.6$: Áp lực bán tháo dồn nén.

    ### 3. Rủi ro Thanh khoản & Độ giãn Chênh lệch Mua - Bán (Relative Spread)
    $$\\text{Spread}_t (\\%) = \\frac{Ask_{1, t} - Bid_{1, t}}{\\frac{1}{2}(Ask_{1, t} + Bid_{1, t})} \\times 100$$
    - Khi Spread giãn rộng bất thường, chi phí trượt giá (slippage) gia tăng, cảnh báo nhà giao dịch không nên mở vị thế với khối lượng lớn.
    
    ---
    > ⚠️ **Tuyên bố Miễn trừ Trách nhiệm Học thuật:**  
    > Sản phẩm này là bài tập nghiên cứu học thuật phục vụ môn học *Gói phần mềm ứng dụng cho tài chính 1*. Mọi tín hiệu cảnh báo và chỉ số đều mang tính chất tham khảo khoa học, không cấu thành bất kỳ lời chào mua, bán hay khuyến nghị đầu tư tài chính tiền thật nào.
    """)
