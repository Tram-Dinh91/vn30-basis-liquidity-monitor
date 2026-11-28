"""
Module xử lý luồng dữ liệu thời gian thực (WebSocket Streaming) từ NEO API.
Tính năng:
- Kết nối tới wss://neoinvest.vpbanks.com.vn/neo-openapi/ws (Read-only)
- Tự động bắt lại kết nối (Auto-reconnect with exponential backoff)
- Theo dõi sức khỏe luồng (reconnect_count, last_error, last_message_at)
"""
import asyncio
import json
import logging
from typing import Callable, Optional, Dict, Any
from src.config import NEO_WS_URL
from src.neo_api.client import normalize_timestamp_vn

logger = logging.getLogger(__name__)


class NeoWebSocketHandler:
    READ_ONLY = True

    def __init__(self, ws_url: str = None, token: str = None):
        self.ws_url = ws_url or NEO_WS_URL
        self.token = token
        self.is_running = False
        self.is_connected = False
        self.reconnect_count = 0
        self.last_error: Optional[str] = None
        self.last_message_at: Optional[str] = None
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
                    self.is_connected = True
                    self.last_error = None
                    retry_delay = 2

                    sub_msg = {
                        "action": "subscribe",
                        "channels": ["market_stream", "orderbook_stream"],
                        "symbols": symbols,
                    }
                    await ws.send(json.dumps(sub_msg))

                    while self.is_running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        self.last_message_at = normalize_timestamp_vn()
                        if self.callback:
                            self.callback(data)

            except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError) as e:
                self.is_connected = False
                self.reconnect_count += 1
                self.last_error = str(e)
                logger.warning(f"Mất kết nối WebSocket ({e}). Thử lại sau {retry_delay} giây...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
            except Exception as e:
                self.is_connected = False
                self.reconnect_count += 1
                self.last_error = str(e)
                logger.error(f"Lỗi không xác định trong luồng WebSocket: {e}")
                await asyncio.sleep(5)

    def stop(self):
        self.is_running = False
        self.is_connected = False

    def get_status(self) -> Dict[str, Any]:
        return {
            "ws_url": self.ws_url,
            "read_only": self.READ_ONLY,
            "is_running": self.is_running,
            "is_connected": self.is_connected,
            "reconnect_count": self.reconnect_count,
            "last_message_at": self.last_message_at,
            "last_error": self.last_error,
        }
