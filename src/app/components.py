"""
Các thành phần giao diện (UI Components) cho Dashboard Streamlit.
Tổ chức theo luồng Data Journal 4 chặng với Plotly tương tác.
"""
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict, Any


def render_regime_banner(risk_eval: Dict[str, Any]):
    """Chặng 2: Thẻ tóm tắt Market Regime & Cảnh báo ưu tiên ngay đầu trang."""
    regime_color = risk_eval.get("regime_color", risk_eval["color"])
    regime_label = risk_eval.get("regime_label", risk_eval["status"])
    regime_desc = risk_eval.get("regime_description", "")
    guidance = risk_eval.get("action_guidance", "")

    st.markdown(
        f"""
        <div style="border-left: 6px solid {regime_color}; background-color: rgba(128,128,128,0.08);
                    padding: 14px 18px; border-radius: 6px; margin-bottom: 12px;">
            <div style="font-size: 0.85rem; opacity: 0.8; text-transform: uppercase;">
                Chế độ Thị trường Hiện tại (Market Regime) | Điểm Rủi ro: <b>{risk_eval['risk_score']}/100</b> ({risk_eval['status']})
            </div>
            <div style="font-size: 1.35rem; font-weight: 700; color: {regime_color}; margin: 4px 0;">
                {regime_label}
            </div>
            <div style="font-size: 0.95rem; margin-bottom: 4px;">{regime_desc}</div>
            <div style="font-size: 0.88rem; opacity: 0.9;">💡 <i>Gợi ý vận hành (Read-only):</i> {guidance}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if risk_eval["alerts"]:
        top_cols = st.columns(min(3, len(risk_eval["alerts"])))
        for idx, alert in enumerate(risk_eval["alerts"][:3]):
            with top_cols[idx]:
                if alert["level"] in ["CRITICAL", "HIGH"]:
                    st.error(f"🚨 **[{alert['type']}]** {alert['message']}")
                else:
                    st.warning(f"⚠️ **[{alert['type']}]** {alert['message']}")


def render_kpi_cards(basis: float, z_basis: float, spread: float, obi: float, dte: int, fair_basis: float):
    """Hiển thị hàng thẻ chỉ số KPI tổng hợp."""
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        delta_str = f"Fair: {fair_basis:+.2f} pt"
        st.metric(
            label="Độ lệch Basis (F - S)",
            value=f"{basis:+.2f} pt",
            delta=delta_str,
            help="Chênh lệch giữa giá HĐTL VN30F1M và chỉ số VN30",
        )

    with c2:
        z_color = "normal" if abs(z_basis) < 2.0 else "inverse"
        st.metric(
            label="Z-score Basis",
            value=f"{z_basis:+.2f} σ",
            delta="Phân kỳ cực trị" if abs(z_basis) >= 2.0 else "Vùng cân bằng",
            delta_color=z_color,
            help="Độ lệch chuẩn hóa so với cửa sổ trượt lịch sử",
        )

    with c3:
        st.metric(
            label="Chênh lệch Mua-Bán (Spread)",
            value=f"{spread:.3f}%",
            delta="Mỏng/Trượt giá" if spread > 0.05 else "Dày/Ổn định",
            delta_color="inverse" if spread > 0.05 else "normal",
            help="Relative Bid-Ask Spread đo lường chi phí giao dịch ẩn",
        )

    with c4:
        st.metric(
            label="Mất cân bằng Sổ lệnh (OBI)",
            value=f"{obi:+.2f}",
            delta=f"Đáo hạn: {dte} ngày",
            help="Chỉ số OBI từ -1.0 (Bán áp đảo) đến +1.0 (Mua áp đảo)",
        )


def render_basis_chart(df: pd.DataFrame, z_threshold: float = 2.0) -> go.Figure:
    """
    Vẽ biểu đồ tương tác: Diễn biến Giá VN30 vs VN30F1M và Chuỗi Basis kèm dải băng +/- Z-threshold.
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            "Diễn biến VN30F1M vs Chỉ số Cơ sở VN30",
            f"Độ lệch Basis & Vùng Cực trị ±{z_threshold:.1f}σ",
        ),
        row_heights=[0.58, 0.42],
    )

    fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["underlying_price"], name="Chỉ số VN30", line=dict(color="#1f77b4", width=2)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["futures_price"], name="HĐTL VN30F1M", line=dict(color="#ff7f0e", width=2)),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["basis"], name="Basis (pt)", line=dict(color="#2ca02c", width=1.5)),
        row=2,
        col=1,
    )

    if "rolling_mean_basis" in df.columns:
        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["rolling_mean_basis"], name="Mean Basis", line=dict(color="gray", dash="dash")),
            row=2,
            col=1,
        )
    if "upper_2sigma" in df.columns and "lower_2sigma" in df.columns:
        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["upper_2sigma"], name=f"+{z_threshold:.1f}σ", line=dict(color="red", dash="dot")),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["lower_2sigma"], name=f"-{z_threshold:.1f}σ", line=dict(color="red", dash="dot")),
            row=2,
            col=1,
        )

    fig.update_layout(
        height=540,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def render_orderbook_ladder(row: pd.Series) -> go.Figure:
    """
    Vẽ tháp sổ lệnh 3 bước giá (Order Book Depth Ladder).
    """
    bid_prices = [row.get("bid_price_3", 0), row.get("bid_price_2", 0), row.get("bid_price_1", 0)]
    bid_vols = [row.get("bid_vol_3", 0), row.get("bid_vol_2", 0), row.get("bid_vol_1", 0)]

    ask_prices = [row.get("ask_price_1", 0), row.get("ask_price_2", 0), row.get("ask_price_3", 0)]
    ask_vols = [row.get("ask_vol_1", 0), row.get("ask_vol_2", 0), row.get("ask_vol_3", 0)]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=[f"Giá {p:.1f}" for p in bid_prices],
            x=bid_vols,
            name="Dư Mua (Bid)",
            orientation="h",
            marker=dict(color="#00c853"),
            text=[f"{v} HĐ" for v in bid_vols],
            textposition="auto",
        )
    )
    fig.add_trace(
        go.Bar(
            y=[f"Giá {p:.1f}" for p in ask_prices],
            x=ask_vols,
            name="Dư Bán (Ask)",
            orientation="h",
            marker=dict(color="#ff5252"),
            text=[f"{v} HĐ" for v in ask_vols],
            textposition="auto",
        )
    )

    fig.update_layout(
        title="Độ sâu Sổ lệnh 3 Bước giá (Depth of Market)",
        barmode="group",
        height=310,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="Khối lượng (Hợp đồng)",
        yaxis_title="Mức giá",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def render_scatter_liquidity(df: pd.DataFrame) -> go.Figure:
    """Biểu đồ phân tán giữa Độ giãn Spread và Biên độ dao động giá."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["relative_spread"],
            y=df["futures_price"].diff().abs(),
            mode="markers",
            marker=dict(size=6, color=df["obi"], colorscale="RdYlGn", showscale=True, colorbar=dict(title="OBI")),
            text=[f"Time: {t}<br>Spread: {s:.3f}%" for t, s in zip(df["timestamp"], df["relative_spread"])],
        )
    )
    fig.update_layout(
        title="Quan hệ giữa Độ giãn Spread (%) và Biên độ dao động giá",
        xaxis_title="Relative Bid-Ask Spread (%)",
        yaxis_title="|Δ Giá HĐTL| (Điểm)",
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def render_risk_alert_panel(risk_eval: Dict[str, Any]):
    """Hiển thị bảng trạng thái và thông báo cảnh báo thông minh."""
    st.markdown(
        f"### Trạng thái: <span style='color:{risk_eval['color']}; font-weight:bold;'>{risk_eval['status']}</span>",
        unsafe_allow_html=True,
    )
    st.progress(min(100, int(risk_eval["risk_score"])))
    st.caption(f"Điểm số rủi ro hệ thống: **{risk_eval['risk_score']} / 100**")

    if risk_eval["alerts"]:
        for alert in risk_eval["alerts"]:
            if alert["level"] in ["CRITICAL", "HIGH"]:
                st.error(f"🚨 **[{alert['type']}]**: {alert['message']}")
            else:
                st.warning(f"⚠️ **[{alert['type']}]**: {alert['message']}")
    else:
        st.success("✅ **Hệ thống ổn định**: Không phát hiện phân kỳ cực trị hoặc bất thường thanh khoản.")
