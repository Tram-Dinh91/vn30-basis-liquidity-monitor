"""
Module phân tích Vi cấu trúc Sổ lệnh 3 bước giá (Order Book Microstructure)
và Mô phỏng Chi phí Thực thi / Trượt giá (Read-only Execution & Slippage Simulator).
"""
from typing import List, Tuple, Dict, Any


def calculate_obi(bid_volumes: List[float], ask_volumes: List[float]) -> float:
    """
    Tính chỉ số Mất cân bằng Sổ lệnh 3 mức giá (Order Book Imbalance - OBI):
    OBI = (Sum(V_bid) - Sum(V_ask)) / (Sum(V_bid) + Sum(V_ask))
    """
    total_bid_vol = float(sum(v for v in bid_volumes if v is not None and v > 0))
    total_ask_vol = float(sum(v for v in ask_volumes if v is not None and v > 0))

    total_vol = total_bid_vol + total_ask_vol
    if total_vol <= 0:
        return 0.0

    obi = (total_bid_vol - total_ask_vol) / total_vol
    return float(round(obi, 4))


def calculate_micro_price(
    bid_price1: float,
    bid_vol1: float,
    ask_price1: float,
    ask_vol1: float,
) -> float:
    """
    Tính Giá Vi mô (Micro-price) tại bước giá tốt nhất (Level 1):
    P_micro = (P_bid * V_ask + P_ask * V_bid) / (V_bid + V_ask)
    """
    if bid_vol1 <= 0 and ask_vol1 <= 0:
        return (bid_price1 + ask_price1) / 2.0 if (bid_price1 and ask_price1) else 0.0

    total_vol = bid_vol1 + ask_vol1
    if total_vol <= 0:
        return (bid_price1 + ask_price1) / 2.0

    micro_p = (bid_price1 * ask_vol1 + ask_price1 * bid_vol1) / total_vol
    return float(round(micro_p, 2))


def classify_obi_signal(obi: float, extreme_threshold: float = 0.6) -> Tuple[str, str]:
    """
    Phân loại trạng thái và mức độ cảnh báo của OBI.
    """
    if obi >= extreme_threshold:
        return "BULLISH_PRESSURE", f"Áp lực Mua áp đảo (OBI = {obi:+.2f})"
    elif obi <= -extreme_threshold:
        return "BEARISH_PRESSURE", f"Áp lực Bán áp đảo (OBI = {obi:+.2f})"
    else:
        return "NEUTRAL", f"Sổ lệnh cân bằng (OBI = {obi:+.2f})"


def simulate_order_execution(
    side: str,
    quantity: int,
    bid_prices: List[float],
    bid_volumes: List[float],
    ask_prices: List[float],
    ask_volumes: List[float],
) -> Dict[str, Any]:
    """
    Mô phỏng chi phí thực thi và trượt giá (100% Read-only, không gửi lệnh thật).
    - side: 'BUY' (khớp vào sổ Ask từ mức 1 -> 3) hoặc 'SELL' (khớp vào sổ Bid từ mức 1 -> 3).
    - quantity: Số lượng hợp đồng giả định (vd: 5, 20, 50, 100).
    """
    side_norm = str(side).upper().strip()
    if side_norm not in {"BUY", "SELL"}:
        raise ValueError("side phải là 'BUY' hoặc 'SELL'.")
    if quantity <= 0:
        raise ValueError("quantity phải lớn hơn 0.")

    bid1 = float(bid_prices[0]) if bid_prices and bid_prices[0] else 0.0
    ask1 = float(ask_prices[0]) if ask_prices and ask_prices[0] else 0.0
    mid_price = (bid1 + ask1) / 2.0 if (bid1 > 0 and ask1 > 0) else max(bid1, ask1)

    target_prices = ask_prices if side_norm == "BUY" else bid_prices
    target_vols = ask_volumes if side_norm == "BUY" else bid_volumes

    ref_price = float(target_prices[0]) if target_prices and target_prices[0] else mid_price
    total_visible_vol = float(sum(max(0.0, float(v or 0)) for v in target_vols))

    if total_visible_vol <= 0:
        # Trường hợp nến lịch sử OHLC 1m không có khối lượng L2:
        # Ước lượng bảo thủ dựa trên nửa Spread hiện hành + tác động bước giá 0.1 điểm theo quy mô lệnh
        half_spread = abs(ask1 - bid1) / 2.0 if (ask1 > 0 and bid1 > 0) else 0.1
        est_impact = round(0.1 * max(0, (quantity - 10) // 25), 2)
        est_fill = (ref_price + est_impact) if side_norm == "BUY" else (ref_price - est_impact)
        slip_pts = abs(est_fill - ref_price)
        slip_pct = (slip_pts / ref_price * 100.0) if ref_price > 0 else 0.0
        cost_vs_mid_pts = abs(est_fill - mid_price) if mid_price > 0 else half_spread + slip_pts
        cost_vs_mid_pct = (cost_vs_mid_pts / mid_price * 100.0) if mid_price > 0 else 0.0
        return {
            "read_only": True,
            "side": side_norm,
            "quantity": int(quantity),
            "reference_price": round(ref_price, 2),
            "mid_price": round(mid_price, 2),
            "avg_fill_price": round(est_fill, 2),
            "filled_qty": 0,
            "unfilled_qty": int(quantity),
            "depth_coverage_pct": 0.0,
            "slippage_points": round(slip_pts, 4),
            "slippage_pct": round(slip_pct, 4),
            "total_cost_vs_mid_points": round(cost_vs_mid_pts, 4),
            "total_cost_vs_mid_pct": round(cost_vs_mid_pct, 4),
            "is_l2_depth_available": False,
            "note": "Nguồn OHLC 1m không có khối lượng L2; ước lượng bảo thủ theo Bid-Ask Spread & bước giá 0.1 điểm.",
        }

    remaining = float(quantity)
    filled = 0.0
    notional = 0.0
    for p, v in zip(target_prices, target_vols):
        price = float(p or 0)
        vol = max(0.0, float(v or 0))
        if price <= 0 or vol <= 0 or remaining <= 0:
            continue
        take = min(remaining, vol)
        notional += take * price
        filled += take
        remaining -= take

    avg_fill = (notional / filled) if filled > 0 else ref_price
    slip_pts = (avg_fill - ref_price) if side_norm == "BUY" else (ref_price - avg_fill)
    slip_pts = max(0.0, slip_pts)
    slip_pct = (slip_pts / ref_price * 100.0) if ref_price > 0 else 0.0
    cost_vs_mid_pts = abs(avg_fill - mid_price) if mid_price > 0 else slip_pts
    cost_vs_mid_pct = (cost_vs_mid_pts / mid_price * 100.0) if mid_price > 0 else 0.0
    coverage = (filled / quantity * 100.0) if quantity > 0 else 0.0

    note = "Khớp đủ trong 3 bước giá." if remaining <= 0 else f"Vượt độ sâu 3 bước giá (thiếu {int(remaining)} HĐ)."

    return {
        "read_only": True,
        "side": side_norm,
        "quantity": int(quantity),
        "reference_price": round(ref_price, 2),
        "mid_price": round(mid_price, 2),
        "avg_fill_price": round(avg_fill, 2),
        "filled_qty": int(filled),
        "unfilled_qty": int(max(0.0, remaining)),
        "depth_coverage_pct": round(coverage, 1),
        "slippage_points": round(slip_pts, 4),
        "slippage_pct": round(slip_pct, 4),
        "total_cost_vs_mid_points": round(cost_vs_mid_pts, 4),
        "total_cost_vs_mid_pct": round(cost_vs_mid_pct, 4),
        "is_l2_depth_available": True,
        "note": note,
    }
