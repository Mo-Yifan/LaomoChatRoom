import sys
import asyncio
import websockets
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog
from PyQt6.QtCore import QSettings
from qasync import QEventLoop, asyncSlot
from client import ChatClient
from login_ui import LoginWindow
from chat_ui import ChatWindow
from register_ui import RegisterWindow


class ClientApp:
    def __init__(self):
        self.app = QApplication(sys.argv)

        # ------------------- 输入服务器 IP 和端口 -------------------
        host, ok = QInputDialog.getText(None, "服务器 IP", "请输入服务器 IP:")
        if not ok or not host:
            sys.exit()
        port, ok = QInputDialog.getInt(None, "服务器端口", "请输入服务器端口:", 12345)
        if not ok:
            sys.exit()
        self.HOST = host
        self.PORT = port

        # ------------------- 初始化客户端和属性 -------------------
        self.client = ChatClient()
        self.username = None
        self.password = None
        self.running = True
        self.chat_ui = None

        # ------------------- 登录界面 -------------------
        self.login_ui = LoginWindow()
        self._connect_login_signals()
        self.login_ui.show()

        # ------------------- 注册界面 -------------------
        self.register_ui = RegisterWindow()
        self.register_ui.register_request.connect(self.on_register_request)

    # ------------------- 延迟绑定槽函数 -------------------
    def _connect_login_signals(self):
        self.on_login_request = asyncSlot(str, str)(self.on_login_request)
        self.on_register_request = asyncSlot(str, str)(self.on_register_request)
        self.login_ui.login_request.connect(self.on_login_request)
        self.login_ui.register_request.connect(self.on_register_request)

    # ============================================================
    # 登录按钮回调
    # ============================================================
    async def on_login_request(self, username: str, password: str):
        self.username = username
        self.password = password
        self.client.set_credentials(username, password)
        await self.async_login()

    # ============================================================
    # 异步登录（核心修复：移除轮询，改用 on_disconnect）
    # ============================================================
    @asyncSlot()
    async def async_login(self):
        try:
            # 1️⃣ HTTP 登录
            result = await self.client.login(self.HOST, self.PORT)
            if result.get("status") != "ok":
                QMessageBox.warning(
                    None, "错误",
                    result.get("reason", "用户名或密码错误")
                )
                return

            # 保存账号到本地历史（去重 + 最多保留10个）
            settings = QSettings("MyChatApp", "LoginHistory")
            history = settings.value("usernames", [], type=list)
            if self.username in history:
                history.remove(self.username)
            history.insert(0, self.username)
            history = history[:10]  # 只保留最近10个
            settings.setValue("usernames", history)
            print(f"[DEBUG] Saved login history: {history}")

            # 2️⃣ 切换 UI
            QMessageBox.information(None, "成功", "登录成功！")
            self.login_ui.close()

            self.chat_ui = ChatWindow(self.username)
            self.client.recv_callback = self.on_server_msg
            self.client.on_disconnect = self.on_ws_disconnect  # ← 关键：注册断开回调
            self.chat_ui.send_msg.connect(self.dispatch_send_message)
            self.chat_ui.show()

            # 3️⃣ 连接 WebSocket（含 login 认证）
            success = await self.client.connect_ws(self.HOST, self.PORT)
            if not success:
                QMessageBox.critical(None, "连接失败", "无法连接 WebSocket 服务器")
                self.chat_ui.close()
                self.login_ui.show()
                return

            # 🌟 不再轮询！等待连接自然断开（receive_loop 会触发 on_disconnect）
            # 主协程不阻塞，由 receive_loop + on_disconnect 驱动生命周期

        except Exception as e:
            QMessageBox.critical(None, "登录异常", f"{type(e).__name__}: {e}")
            if self.chat_ui and self.chat_ui.isVisible():
                self.chat_ui.close()
            if not self.login_ui.isVisible():
                self.login_ui.show()

    # ============================================================
    # WebSocket 断开回调（线程安全）
    # ============================================================
    def on_ws_disconnect(self, exc: websockets.ConnectionClosed):
        # 使用 call_soon_threadsafe 确保在主线程执行 UI 操作
        asyncio.get_event_loop().call_soon_threadsafe(self._handle_disconnect, exc)

    def _handle_disconnect(self, exc):
        if not self.running:
            return
        reason = exc.reason or f"代码 {exc.code}"
        QMessageBox.information(None, "连接断开", f"与服务器断开: {reason}")
        if self.chat_ui:
            self.chat_ui.close()
        self.login_ui.show()

    # ============================================================
    # 注册
    # ============================================================
    async def on_register_request(self, username: str, password: str):
        self.client.set_credentials(username, password)
        await self.async_register()

    @asyncSlot()
    async def async_register(self):
        try:
            result = await self.client.register(self.HOST, self.PORT)
            if result.get("status") == "ok":
                QMessageBox.information(None, "成功", "注册成功，请登录！")
            else:
                QMessageBox.warning(None, "注册失败", result.get("reason", "注册失败"))
        except Exception as e:
            QMessageBox.critical(None, "错误", f"注册异常: {e}")

    # ============================================================
    # 消息分发
    # ============================================================
    def dispatch_send_message(self, msg):
        if msg["type"] == "private":
            asyncio.create_task(self.client.send_private(msg["to"], msg["text"]))
        elif msg["type"] == "group":
            asyncio.create_task(self.client.send_group(msg["text"]))

    # ============================================================
    # 消息接收处理（UI 更新）
    # ============================================================
    def on_server_msg(self, msg):
        if self.chat_ui:
            self.chat_ui.handle_server_message(msg)

    # ============================================================
    # 启动（强化 loop 策略）
    # ============================================================
    def run(self):
        import asyncio
        import sys

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        qloop = QEventLoop(self.app, loop)
        asyncio.set_event_loop(qloop)

        try:
            qloop.run_forever()
        finally:
            qloop.close()


if __name__ == "__main__":
    ClientApp().run()