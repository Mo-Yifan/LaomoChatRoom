# client.py - 完全适配 websockets >=15.0 + qasync
import asyncio
import websockets
import json
import aiohttp
from typing import Optional, Callable
from websockets import State  # ← 新增：用于状态判断


class ChatClient:
    def __init__(self):
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.recv_callback: Optional[Callable[[dict], None]] = None
        self.on_disconnect: Optional[Callable[[websockets.ConnectionClosed], None]] = None

    def set_credentials(self, username: str, password: str):
        self.username = username
        self.password = password

    # -----------------------------
    # WebSocket 连接（核心：无 extra_headers）
    # -----------------------------
    async def connect_ws(self, host: str, port: int) -> bool:
        ws_url = f"ws://{host}:{port}/ws"
        try:
            # ✅ websockets 15.x 不再需要 extra_headers
            self.ws = await websockets.connect(ws_url)
            print(f"[客户端] 已连接服务器: {ws_url}")

            # 🌟 发送 login 消息完成认证
            await self.send_packet({
                "type": "login",
                "username": self.username,
                "password": self.password
            })

            # 启动接收循环（它会处理消息 + 断开）
            asyncio.create_task(self.receive_loop())
            return True

        except Exception as e:
            print(f"[客户端] 连接失败: {e}")
            return False

    # -----------------------------
    # HTTP API
    # -----------------------------
    async def register(self, host: str, port: int) -> dict:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{host}:{port}/register",
                    json={"username": self.username, "password": self.password}
                ) as resp:
                    return await resp.json()
        except Exception as e:
            return {"status": "fail", "reason": str(e)}

    async def login(self, host: str, port: int) -> dict:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{host}:{port}/login",
                    json={"username": self.username, "password": self.password}
                ) as resp:
                    return await resp.json()
        except Exception as e:
            return {"status": "fail", "reason": str(e)}

    # -----------------------------
    # 发送
    # -----------------------------
    async def send_packet(self, data: dict):
        print(f"[DEBUG] self.ws = {self.ws}")
        print(f"[DEBUG] type(self.ws) = {type(self.ws)}")
        if hasattr(self.ws, 'state'):
            print(f"[DEBUG] self.ws.state = {self.ws.state} (repr: {repr(self.ws.state)})")
        else:
            print("[DEBUG] self.ws has no 'state' attribute!")

        if not self.ws or self.ws.state != State.OPEN:
            print("[客户端] 连接未就绪，无法发送")
            return

        raw = json.dumps(data, ensure_ascii=False)
        print(f"[客户端] 尝试发送: {raw}")
        try:
            await self.ws.send(raw)
            print("[客户端] 发送完成（无异常）")
        except Exception as e:
            print(f"[客户端] 发送失败: {e}")
            import traceback
            traceback.print_exc()

    async def send_group(self, text: str):
        if text.strip():
            await self.send_packet({"type": "group", "text": text})

    async def send_private(self, to_user: str, text: str):
        if to_user and to_user != self.username and text.strip():
            await self.send_packet({"type": "private", "to": to_user, "text": text})

    # -----------------------------
    # 接收循环（监听关闭事件）
    # -----------------------------
    async def receive_loop(self):
        if not self.ws:
            return
        try:
            async for raw_data in self.ws:
                try:
                    msg = json.loads(raw_data)
                    if self.recv_callback:
                        self.recv_callback(msg)
                except json.JSONDecodeError:
                    print(f"[客户端] 无效 JSON: {raw_data}")
        except websockets.ConnectionClosed as e:
            print(f"[客户端] 连接关闭: {e.code} - {e.reason}")
            # 🌟 触发断开回调
            if self.on_disconnect:
                try:
                    self.on_disconnect(e)
                except Exception as exc:
                    print(f"[客户端] on_disconnect 回调异常: {exc}")
        except Exception as e:
            print(f"[客户端] 接收异常: {e}")
            # 非 ConnectionClosed 异常也视为断开
            if self.on_disconnect and isinstance(e, websockets.WebSocketException):
                self.on_disconnect(websockets.ConnectionClosed(1006, "异常断开"))

    # -----------------------------
    # 关闭（可选）
    # -----------------------------
    async def close(self):
        if self.ws and self.ws.state == State.OPEN:
            await self.ws.close()
        self.ws = None