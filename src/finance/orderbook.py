"""
Module phân tích Vi cấu trúc Sổ lệnh 3 bước giá (Order Book Microstructure).
Bao gồm:
- Chỉ số Mất cân bằng Sổ lệnh (Order Book Imbalance - OBI)
- Giá vi mô có trọng số khối lượng (Micro-price / Weighted Midprice)
- Phân loại tín hiệu áp lực đặt lệnh
"""
from typing import List, Tuple


def calculate_obi(bid_volumes: List[float], ask_volumes: List[float]) -> float:
    """
    Tính chỉ số Mất cân bằng Sổ lệnh 3 mức giá (Order Book Imbalance - OBI):
    OBI = (Sum(V_bid) - Sum(V_ask)) / (Sum(V_bid) + Sum(V_ask))
    
    Giá trị nằm trong khoảng [-1.0, 1.0]:
    - OBI -> +1.0: Áp lực dư mua áp đảo hoàn toàn (Buy Pressure dồn nén).
    - OBI -> -1.0: Áp lực dư bán áp đảo hoàn toàn (Sell Pressure xả dồn).
    - OBI quanh 0: Cân bằng cung cầu ngắn hạn.
    """
    total_bid_vol = float(sum(v for v in bid_volumes if v is not None and v > 0))
    total_ask_vol = float(sum(v for v in ask_volumes if v is not None and v > 0))
    
    total_vol = total_bid_vol + total_ask_vol
    if total_vol <= 0:
        return 0.0
    
    obi = (total_bid_vol - total_ask_vol) / total_vol
    return float(round(obi, 4))


def calculate_micro_price(bid_price1: float, bid_vol1: float, 
                          ask_price1: float, ask_vol1: float) -> float:
    """
    Tính Giá Vi mô (Micro-price) tại bước giá tốt nhất (Level 1):
    P_micro = (P_bid * V_ask + P_ask * V_bid) / (V_bid + V_ask)
    
    Lý thuyết Vi cấu trúc: Khi dư mua lớn hơn dư bán, xác suất giá khớp đẩy lên phía Ask cao hơn,
    nên Micro-price sẽ lệch gần về phía giá Ask so với Midpoint thông thường.
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
    Phân loại trạng thái và mức độ cảnh báo của OBI:
    - OBI >= extreme_threshold: 'BULLISH_PRESSURE' (Cung mỏng, cầu dồn)
    - OBI <= -extreme_threshold: 'BEARISH_PRESSURE' (Cầu mỏng, cung xả)
    - Còn lại: 'NEUTRAL' (Cân bằng)
    """
    if obi >= extreme_threshold:
        return "BULLISH_PRESSURE", f"Áp lực Mua áp đảo (OBI = {obi:+.2f})"
    elif obi <= -extreme_threshold:
        return "BEARISH_PRESSURE", f"Áp lực Bán áp đảo (OBI = {obi:+.2f})"
    else:
        return "NEUTRAL", f"Sổ lệnh cân bằng (OBI = {obi:+.2f})"
