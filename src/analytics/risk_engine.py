"""
Module Đánh giá Rủi ro Tổng hợp & Hệ thống Cảnh báo Thông minh (Smart Alert System).
Kết hợp 3 chiều:
1. Độ lệch Basis & Phân kỳ cực trị (Z-Basis > 2 hoặc < -2)
2. Rủi ro trượt giá & Rút cạn thanh khoản (Spread shock)
3. Áp lực mất cân bằng sổ lệnh (OBI Extreme)
"""
from typing import Dict, Any, List


def evaluate_system_risk(basis: float, 
                         z_basis: float, 
                         relative_spread: float, 
                         obi: float,
                         spread_threshold: float = 0.08,
                         z_threshold: float = 2.0,
                         obi_threshold: float = 0.6) -> Dict[str, Any]:
    """
    Chấm điểm rủi ro tổng hợp thang 100 và sinh danh sách cảnh báo chi tiết.
    - Risk Score: 0 - 30 (Thấp / Bình thường), 31 - 60 (Trung bình / Chú ý), 61 - 100 (Cao / Cực kỳ rủi ro)
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
            "message": f"Phân kỳ Basis cực trị: Z-score = {z_basis:+.2f} ({direction}). Nguy cơ rung lắc hội tụ mạnh!"
        })
    elif abs_z >= 1.5:
        risk_score += 15.0
        alerts.append({
            "level": "MEDIUM",
            "type": "BASIS_STRETCH",
            "message": f"Basis đang lệch khỏi vùng cân bằng trung bình: Z-score = {z_basis:+.2f}."
        })
        
    # 2. Đánh giá Thanh khoản & Trượt giá (Spread)
    if relative_spread >= spread_threshold:
        risk_score += 35.0
        alerts.append({
            "level": "HIGH",
            "type": "LIQUIDITY_SHOCK",
            "message": f"Cảnh báo Trượt giá: Chênh lệch Mua-Bán giãn rộng ({relative_spread:.3f}%). Rủi ro slippage cao!"
        })
        
    # 3. Đánh giá Mất cân bằng Sổ lệnh (OBI)
    abs_obi = abs(obi)
    if abs_obi >= obi_threshold:
        risk_score += 20.0
        side = "MUA ÁP ĐẢO" if obi > 0 else "BÁN ÁP ĐẢO"
        alerts.append({
            "level": "MEDIUM",
            "type": "ORDERBOOK_IMBALANCE",
            "message": f"Mất cân bằng sổ lệnh cấp độ cao ({side}, OBI = {obi:+.2f})."
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
        
    return {
        "risk_score": round(risk_score, 1),
        "status": status,
        "color": color,
        "basis_value": round(basis, 2),
        "z_basis": round(z_basis, 2),
        "relative_spread": round(relative_spread, 4),
        "obi_value": round(obi, 3),
        "alerts_count": len(alerts),
        "alerts": alerts
    }
