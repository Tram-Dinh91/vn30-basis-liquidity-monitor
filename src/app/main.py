"""
HỆ THỐNG GIÁM SÁT ĐỘ LỆCH PHÁI SINH – CƠ SỞ & RỦI RO THANH KHOẢN HỢP ĐỒNG TƯƠNG LAI VN30
(VN30 Futures Basis & Liquidity Risk Monitor)
Đồ án cuối kỳ môn: Gói phần mềm ứng dụng cho tài chính 1
Hạ tầng cốt lõi: VPBankS NEO API (Read-only) | Bổ trợ đối chiếu: SSI FastConnect
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import pytz

from src.config import (
    TIMEZONE,
    DEFAULT_FUTURE_SYMBOL,
    DEFAULT_UNDERLYING_SYMBOL,
    Z_SCORE_THRESHOLD,
    OBI_EXTREME_THRESHOLD,
    LOOKBACK_WINDOW_DAYS,
    SPREAD_SHOCK_PERCENTILE,
)
from src.data.storage import load_market_data_with_audit, get_available_sources
from src.data.ssi_client import sync_latest_ssi_data
from src.data.cross_check import cross_check_sources
from src.neo_api.client import NeoApiClient, parse_neo_quotes_to_tick
from src.finance.basis import (
    calculate_basis_series,
    calculate_z_score,
    get_expiry_date,
    calculate_dte,
    calculate_fair_basis,
)
from src.finance.liquidity import calculate_relative_spread, simulate_slippage_scenarios
from src.finance.orderbook import calculate_obi, simulate_order_execution
from src.analytics.risk_engine import evaluate_system_risk, classify_regime_series
from src.analytics.metrics import (
    calculate_descriptive_stats,
    classify_intraday_window,
    evaluate_out_of_sample_signals,
)
from src.app.components import (
    render_regime_banner,
    render_kpi_cards,
    render_basis_chart,
    render_orderbook_ladder,
    render_scatter_liquidity,
    render_risk_alert_panel,
)

# 1. Cấu hình Trang Streamlit
st.set_page_config(
    page_title="VN30 Basis & Liquidity Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

vn_tz = pytz.timezone(TIMEZONE)
now_vn = datetime.now(vn_tz)

# 2. Sidebar - Cấu hình Nguồn Dữ liệu & Tham số
st.sidebar.image("https://neoinvest.vpbanks.com.vn/favicon.ico", width=40)
st.sidebar.title("Bảng Điều Khiển")
st.sidebar.markdown("---")

available_sources = get_available_sources() + ["Trực tiếp (NEO API Live)"]
app_mode = st.sidebar.radio(
    "Chế độ Nguồn Dữ liệu:",
    available_sources,
    index=0,
    help="Ưu tiên NEO API làm hạ tầng cốt lõi; hỗ trợ dữ liệu thật SSI FastConnect và 10 phiên mô phỏng kiểm chứng.",
)

if st.sidebar.button("🔄 Cập nhật Dữ liệu Mới nhất (SSI API)", use_container_width=True):
    with st.spinner("Đang kết nối SSI FastConnect v3 (nguồn bổ trợ) & lưu trữ phiên mới..."):
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
spread_shock_thresh = st.sidebar.slider("Ngưỡng Sốc Spread (%)", 0.03, 0.20, 0.08, 0.01)

st.sidebar.markdown("---")
st.sidebar.info(
    "📌 **Đồ án Cuối kỳ:** Gói phần mềm ứng dụng tài chính 1\n"
    "- **Mã Hợp đồng:** VN30F1M | **Cơ sở:** VN30\n"
    "- **Hạ tầng cốt lõi:** VPBankS NEO API (Read-only)\n"
    "- **Nguồn bổ trợ:** SSI FastConnect v3"
)

# 3. Chặng 1: Kiểm tra trạng thái NEO API & Tải dữ liệu kèm Resilience Audit
neo_client = NeoApiClient()
neo_live_df = pd.DataFrame()
neo_status_msg = "Chờ kết nối / IP Whitelist"
if "NEO API Live" in app_mode:
    fut_q = neo_client.get_market_quote(DEFAULT_FUTURE_SYMBOL)
    idx_q = neo_client.get_index_quote(DEFAULT_UNDERLYING_SYMBOL)
    tick = parse_neo_quotes_to_tick(fut_q, idx_q, DEFAULT_FUTURE_SYMBOL, DEFAULT_UNDERLYING_SYMBOL)
    if tick:
        neo_live_df = pd.DataFrame([tick])
        neo_status_msg = "NEO API Live (OK)"
    else:
        neo_status_msg = f"NEO API Fallback ({neo_client.last_error or 'Chưa kết nối'})"

neo_health = neo_client.get_status()
source_type = "real" if ("Thị trường Thật" in app_mode or "NEO API Live" in app_mode) else "sample"
raw_df, is_real_data, resilience_log = load_market_data_with_audit(
    source=source_type,
    api_disconnects=neo_health["disconnect_count"],
)

# Tính toán chỉ số trên toàn bộ chuỗi (phục vụ OOS validation & thống kê đa phiên)
full_df = raw_df.copy()
full_df["basis"] = calculate_basis_series(full_df, "futures_price", "underlying_price")
full_df["z_basis"] = calculate_z_score(full_df["basis"], window=window_size)
full_df["relative_spread"] = [
    calculate_relative_spread(b, a) for b, a in zip(full_df["bid_price_1"], full_df["ask_price_1"])
]
full_df["obi"] = [
    calculate_obi([b1, b2, b3], [a1, a2, a3])
    for b1, b2, b3, a1, a2, a3 in zip(
        full_df["bid_vol_1"], full_df["bid_vol_2"], full_df["bid_vol_3"],
        full_df["ask_vol_1"], full_df["ask_vol_2"], full_df["ask_vol_3"],
    )
]
full_df["market_regime"] = classify_regime_series(
    full_df,
    z_threshold=z_thresh,
    spread_threshold=spread_shock_thresh,
    obi_threshold=obi_thresh,
)
full_df["intraday_window"] = classify_intraday_window(full_df["timestamp"])

# Chọn phiên & bộ lọc khung giờ
available_dates = sorted(full_df["session_date"].unique(), reverse=True)
selected_date = st.sidebar.selectbox("Chọn Phiên Giao dịch:", available_dates, index=0)
window_filter = st.sidebar.selectbox(
    "Lọc Khung giờ Nội ngày:",
    ["Toàn phiên", "Loại trừ ATO & ATC (Khớp liên tục)", "Phiên Sáng (09:15-11:30)", "Phiên Chiều (13:00-14:30)"],
    index=0,
)

df_session = full_df[full_df["session_date"] == selected_date].copy()
if window_filter == "Loại trừ ATO & ATC (Khớp liên tục)":
    filtered = df_session[df_session["intraday_window"].isin(["Phiên Sáng (09:15-11:30)", "Phiên Chiều (13:00-14:30)"])]
    if not filtered.empty:
        df_session = filtered.copy()
elif window_filter in ["Phiên Sáng (09:15-11:30)", "Phiên Chiều (13:00-14:30)"]:
    filtered = df_session[df_session["intraday_window"] == window_filter]
    if not filtered.empty:
        df_session = filtered.copy()

df_session = df_session.reset_index(drop=True)
df_session["rolling_mean_basis"] = df_session["basis"].rolling(window=window_size, min_periods=1).mean()
df_session["rolling_std_basis"] = df_session["basis"].rolling(window=window_size, min_periods=1).std().fillna(1.0)
df_session["upper_2sigma"] = df_session["rolling_mean_basis"] + z_thresh * df_session["rolling_std_basis"]
df_session["lower_2sigma"] = df_session["rolling_mean_basis"] - z_thresh * df_session["rolling_std_basis"]

latest = df_session.iloc[-1]
expiry = get_expiry_date(now_vn.year, now_vn.month)
dte = calculate_dte(now_vn.date(), expiry)
fair_basis = calculate_fair_basis(latest["underlying_price"], dte=dte)

risk_eval = evaluate_system_risk(
    basis=latest["basis"],
    z_basis=latest["z_basis"],
    relative_spread=latest["relative_spread"],
    obi=latest["obi"],
    spread_threshold=spread_shock_thresh,
    z_threshold=z_thresh,
    obi_threshold=obi_thresh,
)

# ==================== CHẶNG 1: TRẠNG THÁI HỆ THỐNG & DỮ LIỆU ====================
st.title("🛡️ VN30 Futures Basis & Liquidity Risk Monitor")
st.caption("Data Journal Giám sát Độ lệch Phái sinh – Cơ sở, Chế độ Thị trường & Chi phí Trượt giá (100% Read-only)")

h_col1, h_col2, h_col3, h_col4 = st.columns([2.2, 1.3, 1.2, 1.0])
with h_col1:
    st.write(f"🕒 **Cập nhật:** `{latest['timestamp']}` *(UTC+7)*")
with h_col2:
    if not neo_live_df.empty:
        st.markdown("🟢 **Nguồn:** `NEO API Live (OK)`")
    elif is_real_data:
        st.markdown("🟢 **Nguồn:** `SSI Real Saved (Bổ trợ NEO)`")
    else:
        st.markdown("🔵 **Nguồn:** `10 Phiên Mô phỏng Kiểm chứng`")
with h_col3:
    fut_display = latest.get("futures_symbol", DEFAULT_FUTURE_SYMBOL)
    st.markdown(f"🏷️ **Mã:** `{fut_display}` vs `{DEFAULT_UNDERLYING_SYMBOL}`")
with h_col4:
    st.markdown("🔒 **Chế độ:** `READ-ONLY`")

st.markdown("---")

# ==================== CHẶNG 2: CẢNH BÁO ƯU TIÊN & CHẾ ĐỘ THỊ TRƯỜNG ====================
render_regime_banner(risk_eval)
render_kpi_cards(
    basis=latest["basis"],
    z_basis=latest["z_basis"],
    spread=latest["relative_spread"],
    obi=latest["obi"],
    dte=dte,
    fair_basis=fair_basis,
)

st.markdown("---")

# ==================== CHẶNG 3: TRỰC QUAN HÓA, MÔ PHỎNG TRƯỢT GIÁ & KIỂM CHỨNG ====================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Giám sát Nội ngày & Mô phỏng Trượt giá",
    "📈 Kiểm chứng Ngoài mẫu & Thống kê Đa phiên",
    "🔍 Đối chiếu NEO/SSI & Nhật ký Sự cố",
    "📖 Phương pháp, Giới hạn & Miễn trừ",
])

# ----------------- TAB 1 -----------------
with tab1:
    col_left, col_right = st.columns([6.6, 3.4])

    with col_left:
        st.subheader("Biểu đồ Giá và Vùng Cực trị Basis")
        fig_basis = render_basis_chart(df_session, z_threshold=z_thresh)
        st.plotly_chart(fig_basis, use_container_width=True)

    with col_right:
        st.subheader("Cảnh báo Rủi ro Chi tiết")
        render_risk_alert_panel(risk_eval)
        st.markdown("---")
        st.subheader("Cấu trúc Sổ lệnh 3 Bước giá")
        fig_ladder = render_orderbook_ladder(latest)
        st.plotly_chart(fig_ladder, use_container_width=True)

    st.markdown("---")
    st.subheader("🧮 Mô phỏng Chi phí Thực thi & Trượt giá Nội ngày (Read-only Simulator)")
    sim_c1, sim_c2, sim_c3, sim_c4 = st.columns([1.2, 1.5, 1.5, 2.0])
    with sim_c1:
        sim_side = st.radio("Chiều lệnh giả định:", ["BUY", "SELL"], horizontal=True)
    with sim_c2:
        sim_qty = st.select_slider("Quy mô (Hợp đồng):", options=[5, 10, 20, 50, 100], value=20)
    sim_res = simulate_order_execution(
        side=sim_side,
        quantity=sim_qty,
        bid_prices=[latest["bid_price_1"], latest["bid_price_2"], latest["bid_price_3"]],
        bid_volumes=[latest["bid_vol_1"], latest["bid_vol_2"], latest["bid_vol_3"]],
        ask_prices=[latest["ask_price_1"], latest["ask_price_2"], latest["ask_price_3"]],
        ask_volumes=[latest["ask_vol_1"], latest["ask_vol_2"], latest["ask_vol_3"]],
    )
    with sim_c3:
        st.metric(
            "Giá khớp TB dự kiến",
            f"{sim_res['avg_fill_price']:.2f}",
            delta=f"Trượt {sim_res['slippage_points']:+.2f} pt ({sim_res['slippage_pct']:.3f}%)",
            delta_color="inverse" if sim_res["slippage_points"] > 0 else "normal",
        )
    with sim_c4:
        st.metric(
            "Chi phí vs Mid-price",
            f"{sim_res['total_cost_vs_mid_points']:.2f} pt ({sim_res['total_cost_vs_mid_pct']:.3f}%)",
            delta=f"Độ phủ 3 bước giá: {sim_res['depth_coverage_pct']:.0f}%",
        )
    st.caption(f"ℹ️ {sim_res['note']} *(Chỉ mô phỏng trên dữ liệu, tuyệt đối không phát sinh lệnh thật.)*")

    scenarios_df = simulate_slippage_scenarios(latest, quantities=[5, 20, 50, 100], side=sim_side)
    st.dataframe(scenarios_df, use_container_width=True, hide_index=True)

# ----------------- TAB 2 -----------------
with tab2:
    st.subheader("Kiểm chứng Ngoài mẫu (Out-of-sample Validation) & Thống kê Đa phiên")
    oos = evaluate_out_of_sample_signals(
        full_df,
        split_ratio=0.7,
        window=window_size,
        z_threshold=z_thresh,
        horizon_bars=5,
    )

    if oos.get("valid"):
        o1, o2, o3, o4 = st.columns(4)
        with o1:
            st.metric("Tập Train / Test", f"{oos['train_rows']} / {oos['test_rows']}", delta="Tách theo thời gian")
        with o2:
            st.metric("Ngưỡng Spread P95 (Train)", f"{oos['train_spread_p95']:.4f}%", delta=f"Test vượt ngưỡng: {oos['oos_thin_liquidity_count']}")
        with o3:
            rev = f"{oos['oos_reversion_rate_pct']}%" if oos["oos_reversion_rate_pct"] is not None else "N/A"
            st.metric("Tỷ lệ Hội tụ OOS", rev, delta=f"{oos['oos_signal_count']} tín hiệu |Z|≥{z_thresh:.1f}")
        with o4:
            clean_rev = f"{oos['clean_window_reversion_pct']}%" if oos["clean_window_reversion_pct"] is not None else "N/A"
            noisy_rev = f"{oos['noisy_window_reversion_pct']}%" if oos["noisy_window_reversion_pct"] is not None else "N/A"
            st.metric("Hội tụ Khớp liên tục vs Nhiễu", f"{clean_rev} / {noisy_rev}", delta="ATO/ATC/Mỏng tách riêng")

        st.info(f"📌 **Lưu ý độ tin cậy:** {oos['reliability_note']}")
        st.markdown("#### Phân tích Nhiễu Theo Khung Giờ Giao Dịch (Tập Test Ngoài mẫu)")
        st.dataframe(oos["window_stats_df"], use_container_width=True, hide_index=True)
    else:
        st.warning(oos.get("message", "Chưa đủ dữ liệu kiểm chứng ngoài mẫu."))

    st.markdown("---")
    t2_col1, t2_col2 = st.columns(2)
    with t2_col1:
        st.markdown("#### Phân tán: Độ giãn Spread vs Biến động Giá")
        fig_scatter = render_scatter_liquidity(df_session)
        st.plotly_chart(fig_scatter, use_container_width=True)
    with t2_col2:
        st.markdown("#### Bảng Thống kê Mô tả Chuỗi Basis, Spread & OBI (Toàn bộ phiên)")
        desc_df = calculate_descriptive_stats(full_df, ["basis", "relative_spread", "obi"])
        st.dataframe(desc_df, use_container_width=True)

        st.markdown("#### Phân bố Chế độ Thị trường (Market Regime)")
        regime_counts = full_df["market_regime"].value_counts().reset_index()
        regime_counts.columns = ["Market Regime", "Số quan sát"]
        st.dataframe(regime_counts, use_container_width=True, hide_index=True)

# ----------------- TAB 3 -----------------
with tab3:
    st.subheader("Nhật ký Sự cố Dữ liệu (Resilience Log) & Đối chiếu Chéo NEO API – SSI")

    r1, r2, r3, r4, r5 = st.columns(5)
    with r1:
        st.metric("Trạng thái Chất lượng", resilience_log["reliability_status"], delta=f"{resilience_log['total_raw_rows']} raw rows")
    with r2:
        st.metric("Giá trị thiếu (NaN)", resilience_log["missing_values_count"])
    with r3:
        st.metric("Bản ghi Trùng lặp", resilience_log["duplicate_timestamps_count"])
    with r4:
        st.metric("Lỗi Sổ lệnh (Ask<Bid / Âm)", resilience_log["crossed_book_count"] + resilience_log["negative_volume_count"])
    with r5:
        st.metric("Mất kết nối API / Fallback", f"{resilience_log['api_disconnects']} / {'Có' if resilience_log['fallback_used'] else 'Không'}")

    if resilience_log["zero_l2_depth_count"] > 0:
        st.warning(
            f"⚠️ Có **{resilience_log['zero_l2_depth_count']}/{resilience_log['total_raw_rows']}** bản ghi không có khối lượng sổ lệnh L2 "
            "(đặc thù của nến lịch sử OHLC 1m từ SSI FastConnect; mô phỏng trượt giá tự động dùng ước lượng bảo thủ theo Spread)."
        )

    st.markdown("#### Đối chiếu Chéo: VPBankS NEO API (Cốt lõi) vs SSI FastConnect (Bổ trợ)")
    cc_res = cross_check_sources(neo_live_df, raw_df if is_real_data else None)
    if cc_res["available"]:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Số bản ghi khớp", cc_res["matched_records"])
        c2.metric("Lệch giá HĐTL TB", f"{cc_res['mean_abs_futures_diff']:.3f} pt")
        c3.metric("Lệch Basis TB", f"{cc_res['mean_abs_basis_diff']:.3f} pt")
        c4.metric("Độ trễ đồng bộ TB", f"{cc_res['mean_lag_seconds']:.1f} s")
    else:
        st.info(
            f"ℹ️ **Trạng thái đối chiếu:** {cc_res['message']} "
            f"(NEO API Client: `Read-only={neo_health['read_only']}`, `RateLimit={neo_health['rate_limit_rps']} req/s`, "
            f"`LastError={neo_health['last_error'] or 'None'}`)."
        )

    st.markdown("#### Bảng Dữ liệu Nội ngày Đã Xử lý (50 bản ghi gần nhất)")
    st.dataframe(
        df_session[[
            "timestamp", "intraday_window", "underlying_price", "futures_price",
            "basis", "z_basis", "relative_spread", "obi", "market_regime", "matched_volume",
        ]].tail(50),
        use_container_width=True,
    )

# ----------------- TAB 4 (CHẶNG 4) -----------------
with tab4:
    st.subheader("Chặng 4: Cơ sở Lý thuyết, Nhật ký Giới hạn & Tuyên bố Miễn trừ")
    st.markdown("""
    ### 1. Chuỗi Xử lý Tích hợp 5 Lớp
    `Data Ingestion (NEO API / SSI) → Market Regime & Risk Scoring → Slippage Simulator (Read-only) → Out-of-sample Validation & Resilience Log → Streamlit Decision Flow`

    ### 2. Công thức Định lượng Cốt lõi
    * **Basis & Cost-of-Carry:** $\\text{Basis}_t = F_t - S_t$, $F^* = S \\cdot [1 + (r - q) \\cdot \\frac{\\text{DTE}}{365}]$, $Z_{\\text{Basis}, t} = \\frac{\\text{Basis}_t - \\mu_w}{\\sigma_w}$.
    * **Order Book Imbalance (3 bước giá):** $OBI_t = \\frac{\\sum_{i=1}^3 V_{\\text{Bid}, i} - \\sum_{i=1}^3 V_{\\text{Ask}, i}}{\\sum_{i=1}^3 V_{\\text{Bid}, i} + \\sum_{i=1}^3 V_{\\text{Ask}, i}} \\in [-1, 1]$.
    * **Relative Spread:** $\\text{Spread}_t (\\%) = \\frac{\\text{Ask}_{1,t} - \\text{Bid}_{1,t}}{\\frac{1}{2}(\\text{Ask}_{1,t} + \\text{Bid}_{1,t})} \\times 100$.

    ### 3. Giới hạn Trung thực của Sản phẩm
    * **Giới hạn nguồn dữ liệu:** VPBankS NEO API là trục kiến trúc cốt lõi (REST $\\le 5$ req/s + WebSocket, Read-only). Khi chưa cấp IP Whitelist trên máy cục bộ, hệ thống sử dụng dữ liệu thị trường thật từ SSI FastConnect v3 (nến 1 phút) làm nguồn bổ trợ hợp lệ; nến 1m không lưu độ sâu L2 nên khối lượng sổ lệnh bằng 0 và bộ mô phỏng trượt giá sử dụng ước lượng bảo thủ.
    * **Khung giờ nhiễu:** Các phiên định kỳ ATO (08:45–09:15) và ATC (14:30–14:45) có biến động vi cấu trúc phi tuyến, tín hiệu $Z$-score kém tin cậy hơn phiên khớp lệnh liên tục.

    ---
    > ⚠️ **Tuyên bố Miễn trừ Trách nhiệm Học thuật:**  
    > Sản phẩm này là **công cụ phân tích học thuật** phục vụ môn học *Gói phần mềm ứng dụng cho tài chính 1*, vận hành 100% ở chế độ **chỉ đọc (Read-only)**. Mọi chỉ số, chế độ thị trường và ước tính trượt giá chỉ mang tính chất nghiên cứu khoa học, **không phải khuyến nghị đầu tư**.
    """)
