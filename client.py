# client.py
import asyncio
import json
import aiohttp
import websockets
from PyQt6.QtCore import QThread, pyqtSignal

# -------------------- 接收消息线程 --------------------
class ClientRecvThread(QThread):
    recv_signal = pyqtSignal(dict)  # 永远只发 dict

    def __init__(self, uri):
        super().__init__()
        self.uri = uri
        self.ws = None
        self.running = True

    def run(self):
        asyncio.run(self.websocket_loop())

    async def websocket_loop(self):
        try:
            async with websockets.connect(self.uri) as websocket:
                self.ws = websocket
                while self.running:
                    msg_text = await websocket.recv()   # 一定是 JSON 字符串

                    # 尝试解析 JSON
                    try:
                        msg = json.loads(msg_text)
                        # 成功才 emit
                        self.recv_signal.emit(msg)
                    except Exception as e:
                        print(f"[客户端] JSON 解析失败: {e}, 内容: {msg_text}")
                        # 不 emit 字符串，避免 UI 显示 JSON 原文
                        continue

        except Exception as e:
            print(f"[客户端] 连接异常: {e}")

    def stop(self):
        self.running = False
        if self.ws:
            try:
                asyncio.run(self.ws.close())
            except RuntimeError:
                pass


# -------------------- 客户端管理类 --------------------
class ChatClient:
    """基于 WebSocket 的异步客户端"""
    def __init__(self):
        self.username = None
        self.password = None
        self.uri = None
        self.recv_thread = None
        self.recv_callback = None  # 收到消息时回调 UI

    # -------------------- 设置用户名和密码 --------------------
    def set_credentials(self, username, password):
        self.username = username
        self.password = password

    # -------------------- 注册 --------------------
    async def register(self, host, port):
        if not self.username or not self.password:
            raise ValueError("请先调用 set_credentials 设置用户名和密码")
        url = f"http://{host}:{port}/register"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"username": self.username, "password": self.password}) as resp:
                return await resp.json()

    # -------------------- 登录 --------------------
    async def login(self, host, port):
        if not self.username or not self.password:
            raise ValueError("请先调用 set_credentials 设置用户名和密码")
        url = f"http://{host}:{port}/login"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"username": self.username, "password": self.password}) as resp:
                return await resp.json()

    # -------------------- 连接 WebSocket --------------------
    def connect_ws(self, host, port):
        if not self.username:
            raise ValueError("请先调用 set_credentials 设置用户名")
        self.uri = f"ws://{host}:{port}/ws/{self.username}"
        self.recv_thread = ClientRecvThread(self.uri)
        if self.recv_callback:
            self.recv_thread.recv_signal.connect(self.recv_callback)
        self.recv_thread.start()
        print(f"[客户端] 已启动 WebSocket 接收线程，连接到 {self.uri}")

    # -------------------- 发送群聊消息 --------------------
    async def send_chat(self, text):
        if self.recv_thread and self.recv_thread.ws:
            msg = {"type": "chat", "text": text}
            await self.recv_thread.ws.send(json.dumps(msg))

    # -------------------- 发送私聊消息 --------------------
    async def send_private(self, to_user, text):
        if self.recv_thread and self.recv_thread.ws:
            msg = {"type": "private", "from": self.username, "to": to_user, "text": text}
            await self.recv_thread.ws.send(json.dumps(msg))

    # -------------------- 断开连接 --------------------
    async def disconnect(self):
        if self.recv_thread:
            self.recv_thread.stop()
            self.recv_thread = None
