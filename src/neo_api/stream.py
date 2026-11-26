"""
Module xử lý luồng dữ liệu thời gian thực (WebSocket Streaming) từ NEO API.
Tính năng:
- Kết nối tới wss://neoinvest.vpbanks.com.vn/neo-openapi/ws
- Tự động bắt lại kết nối (Auto-reconnect with exponential backoff)
- Phân tích gói tin sổ lệnh VN30F1M và chỉ số VN30
- Lưu trữ các tick nhận được vào bộ đệm cache
"""
import asyncio
import json
import logging
from typing import Callable, Optional
from src.config import NEO_WS_URL

logger = logging.getLogger(__name__)


class NeoWebSocketHandler:
    def __init__(self, ws_url: str = None, token: str = None):
        self.ws_url = ws_url or NEO_WS_URL
        self.token = token
        self.is_running = False
        self.callback: Optional[Callable] = None

    def register_callback(self, cb: Callable):
        self.callback = cb

    async def connect_and_listen(self, symbols: list):
        """
        Lắng nghe luồng dữ liệu WebSocket và dispatch tới hàm callback.
        """
        import websockets
        
        self.is_running = True
        retry_delay = 2
        
        while self.is_running:
            try:
                headers = {}
                if self.token:
                    headers["Authorization"] = f"Bearer {self.token}"
                    
                async with websockets.connect(self.ws_url, extra_headers=headers, timeout=10) as ws:
                    logger.info("Đã kết nối thành công tới NEO WebSocket.")
                    retry_delay = 2  # Reset delay khi kết nối thành công
                    
                    # Gửi bản tin đăng ký (Subscribe) các mã cần theo dõi
                    sub_msg = {
                        "action": "subscribe",
                        "channels": ["market_stream", "orderbook_stream"],
                        "symbols": symbols
                    }
                    await ws.send(json.dumps(sub_msg))
                    
                    while self.is_running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if self.callback:
                            self.callback(data)
                            
            except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError) as e:
                logger.warning(f"Mất kết nối WebSocket ({e}). Thử lại sau {retry_delay} giây...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
            except Exception as e:
                logger.error(f"Lỗi không xác định trong luồng WebSocket: {e}")
                await asyncio.sleep(5)

    def stop(self):
        self.is_running = False
