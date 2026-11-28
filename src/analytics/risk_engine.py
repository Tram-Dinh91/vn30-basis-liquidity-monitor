"""
Module Đánh giá Rủi ro Tổng hợp, Phân loại Chế độ Thị trường (Market Regime)
và Hệ thống Cảnh báo Thông minh (Smart Alert System).
Kết hợp 3 chiều định lượng có cơ sở thống kê:
1. Độ lệch Basis chuẩn hóa (|Z-Basis| >= 2.0: phân vị cực trị 5% hai đầu phân phối chuẩn)
2. Rủi ro thanh khoản & trượt giá (Relative Spread >= ngưỡng phân vị 95% lịch sử hoặc >= 0.08%)
3. Áp lực mất cân bằng sổ lệnh 3 bước giá (|OBI| >= 0.6)
"""
from typing import Dict, Any, List
import pandas as pd


REGIME_DEFINITIONS = {
    "BASIS_EXTREME_ILLIQUID": {
        "label": "Basis Căng Cực Trị + Thanh Khoản Co Hẹp",
        "color": "#d32f2f",
        "description": "Độ lệch Basis vượt ngưỡng ±2σ đồng thời Bid-Ask Spread giãn rộng bất thường.",
        "guidance": "Hạn chế mở mới vị thế khối lượng lớn; ưu tiên lệnh giới hạn (LO) thay vì lệnh thị trường.",
    },
    "LIQUIDITY_STRESS": {
        "label": "Thanh Khoản Co Hẹp / Giãn Spread",
        "color": "#ff4b4b",
        "description": "Relative Spread vượt ngưỡng sốc thanh khoản (phân vị 95% lịch sử), rủi ro trượt giá cao.",
        "guidance": "Chia nhỏ quy mô lệnh giả định và kiểm tra kỹ độ sâu 3 bước giá trước khi khớp.",
    },
    "BASIS_EXTREME": {
        "label": "Phân Kỳ Basis Cực Trị (±2σ)",
        "color": "#f57c00",
        "description": "Chênh lệch Phái sinh – Cơ sở lệch ngoài vùng ±2σ lịch sử, dễ xảy ra rung lắc hội tụ.",
        "guidance": "Theo dõi áp lực đảo chiều mean-reversion và biến động chỉ số cơ sở VN30.",
    },
    "ORDERBOOK_IMBALANCE_PRESSURE": {
        "label": "Áp Lực Lệch Pha Sổ Lệnh Mạnh",
        "color": "#ffa000",
        "description": "Chỉ số mất cân bằng sổ lệnh |OBI| >= ngưỡng cực trị tại 3 bước giá tốt nhất.",
        "guidance": "Cung - cầu ngắn hạn mất cân xứng rõ rệt; chú ý rủi ro quét bước giá (price jump).",
    },
    "BASIS_STRETCH": {
        "label": "Basis Giãn Nhẹ (Vùng Theo Dõi)",
        "color": "#fbc02d",
        "description": "Độ lệch Basis nằm trong vùng 1.5σ – 2.0σ, chưa chạm ngưỡng cực trị nhưng cần quan sát.",
        "guidance": "Duy trì giám sát tốc độ giãn Spread và sự thay đổi OBI.",
    },
    "BALANCED_NORMAL": {
        "label": "Trạng Thái Cân Bằng Bình Thường",
        "color": "#00c853",
        "description": "Basis, Spread và OBI đều nằm trong vùng phân phối bình thường.",
        "guidance": "Điều kiện vi cấu trúc ổn định cho việc định giá và phòng hộ tiêu chuẩn.",
    },
}


def classify_market_regime(
    z_basis: float,
    relative_spread: float,
    obi: float,
    z_threshold: float = 2.0,
    spread_threshold: float = 0.08,
    obi_threshold: float = 0.6,
) -> Dict[str, str]:
    """
    Phân loại chế độ thị trường nội ngày dựa trên 3 biến số vi cấu trúc.
    Thứ tự ưu tiên phản ánh mức độ rủi ro thực thi từ cao xuống thấp.
    """
    abs_z = abs(z_basis)
    abs_obi = abs(obi)
    is_basis_extreme = abs_z >= z_threshold
    is_spread_shock = relative_spread >= spread_threshold
    is_obi_extreme = abs_obi >= obi_threshold

    if is_basis_extreme and is_spread_shock:
        code = "BASIS_EXTREME_ILLIQUID"
    elif is_spread_shock:
        code = "LIQUIDITY_STRESS"
    elif is_basis_extreme:
        code = "BASIS_EXTREME"
    elif is_obi_extreme:
        code = "ORDERBOOK_IMBALANCE_PRESSURE"
    elif abs_z >= 1.5:
        code = "BASIS_STRETCH"
    else:
        code = "BALANCED_NORMAL"

    info = REGIME_DEFINITIONS[code]
    return {
        "regime_code": code,
        "regime_label": info["label"],
        "regime_color": info["color"],
        "regime_description": info["description"],
        "action_guidance": info["guidance"],
    }


def classify_regime_series(
    df: pd.DataFrame,
    z_threshold: float = 2.0,
    spread_threshold: float = 0.08,
    obi_threshold: float = 0.6,
) -> pd.Series:
    """Gắn nhãn Market Regime cho từng dòng trong DataFrame chuỗi thời gian."""
    if df.empty:
        return pd.Series(dtype=str)

    regimes = [
        classify_market_regime(
            z_basis=float(z),
            relative_spread=float(sp),
            obi=float(ob),
            z_threshold=z_threshold,
            spread_threshold=spread_threshold,
            obi_threshold=obi_threshold,
        )["regime_code"]
        for z, sp, ob in zip(
            df.get("z_basis", pd.Series(0.0, index=df.index)),
            df.get("relative_spread", pd.Series(0.0, index=df.index)),
            df.get("obi", pd.Series(0.0, index=df.index)),
        )
    ]
    return pd.Series(regimes, index=df.index, name="market_regime")


def evaluate_system_risk(
    basis: float,
    z_basis: float,
    relative_spread: float,
    obi: float,
    spread_threshold: float = 0.08,
    z_threshold: float = 2.0,
    obi_threshold: float = 0.6,
) -> Dict[str, Any]:
    """
    Chấm điểm rủi ro tổng hợp thang 100, phân loại Market Regime và sinh danh sách cảnh báo chi tiết.
    - Risk Score: 0 - 34 (Bình thường), 35 - 64 (Chú ý), 65 - 100 (Rủi ro cao)
    """
    risk_score = 10.0  # Điểm cơ sở
    alerts: List[Dict[str, str]] = []

    # 1. Đánh giá Basis Z-Score
    abs_z = abs(z_basis)
    if abs_z >= z_threshold:
        risk_score += 35.0
        direction = "DƯƠNG QUÁ ĐÀ (Hưng phấn cực độ)" if z_basis > 0 else "ÂM QUÁ ĐÀ (Hoảng loạn bán tháo)"
        alerts.append({
            "level": "CRITICAL" if abs_z > 2.5 else "HIGH",
            "type": "BASIS_DIVERGENCE",
            "message": f"Phân kỳ Basis cực trị: Z-score = {z_basis:+.2f} ({direction}). Nguy cơ rung lắc hội tụ mạnh!",
        })
    elif abs_z >= 1.5:
        risk_score += 15.0
        alerts.append({
            "level": "MEDIUM",
            "type": "BASIS_STRETCH",
            "message": f"Basis đang lệch khỏi vùng cân bằng trung bình: Z-score = {z_basis:+.2f}.",
        })

    # 2. Đánh giá Thanh khoản & Trượt giá (Spread)
    if relative_spread >= spread_threshold:
        risk_score += 35.0
        alerts.append({
            "level": "HIGH",
            "type": "LIQUIDITY_SHOCK",
            "message": f"Cảnh báo Trượt giá: Chênh lệch Mua-Bán giãn rộng ({relative_spread:.3f}%). Rủi ro slippage cao!",
        })

    # 3. Đánh giá Mất cân bằng Sổ lệnh (OBI)
    abs_obi = abs(obi)
    if abs_obi >= obi_threshold:
        risk_score += 20.0
        side = "MUA ÁP ĐẢO" if obi > 0 else "BÁN ÁP ĐẢO"
        alerts.append({
            "level": "MEDIUM",
            "type": "ORDERBOOK_IMBALANCE",
            "message": f"Mất cân bằng sổ lệnh cấp độ cao ({side}, OBI = {obi:+.2f}).",
        })

    risk_score = min(100.0, risk_score)

    # Phân loại trạng thái hệ thống
    if risk_score >= 65:
        status = "RỦI RO CAO (HIGH RISK)"
        color = "#ff4b4b"
    elif risk_score >= 35:
        status = "CHÚ Ý THEO DÕI (CAUTION)"
        color = "#ffa500"
    else:
        status = "BÌNH THƯỜNG (NORMAL)"
        color = "#00c853"

    regime = classify_market_regime(
        z_basis=z_basis,
        relative_spread=relative_spread,
        obi=obi,
        z_threshold=z_threshold,
        spread_threshold=spread_threshold,
        obi_threshold=obi_threshold,
    )

    return {
        "risk_score": round(risk_score, 1),
        "status": status,
        "color": color,
        "regime_code": regime["regime_code"],
        "regime_label": regime["regime_label"],
        "regime_color": regime["regime_color"],
        "regime_description": regime["regime_description"],
        "action_guidance": regime["action_guidance"],
        "basis_value": round(basis, 2),
        "z_basis": round(z_basis, 2),
        "relative_spread": round(relative_spread, 4),
        "obi_value": round(obi, 3),
        "alerts_count": len(alerts),
        "alerts": alerts,
    }
