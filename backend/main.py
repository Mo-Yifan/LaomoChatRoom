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

        # 获取服务器地址
        host, ok = QInputDialog.getText(None, "服务器 IP", "请输入服务器 IP:")
        if not ok or not host:
            sys.exit()
        port, ok = QInputDialog.getInt(None, "服务器端口", "请输入服务器端口:", 12345)
        if not ok:
            sys.exit()
        self.HOST = host
        self.PORT = port

        # 初始化客户端
        self.client = ChatClient()
        self.username = None
        self.password = None
        self.running = True
        self.chat_ui = None

        # 创建 UI
        self.login_ui = LoginWindow()
        self.register_ui = RegisterWindow()

        # 连接信号
        self._connect_login_signals()

        # 显示登录界面
        self.login_ui.show()

    # ------------------- 延迟绑定槽函数 -------------------
    def _connect_login_signals(self):
        # 包装异步槽
        self.on_login_request = asyncSlot(str, str)(self.on_login_request)
        self.on_register_request = asyncSlot(str, str)(self.on_register_request)

        # 登录信号
        self.login_ui.login_request.connect(self.on_login_request)
        self.login_ui.open_register_window.connect(self.show_register_window)

        # 注册信号
        self.register_ui.register_request.connect(self.on_register_request)

    # ============================================================
    # 登录按钮回调
    # ============================================================
    async def on_login_request(self, username: str, password: str):
        self.username = username
        self.password = password
        self.client.set_credentials(username, password)
        await self.async_login()

    # ============================================================
    # 异步登录（核心）
    # ============================================================
    @asyncSlot()
    async def async_login(self):
        try:
            # 1️⃣ HTTP 登录
            result = await self.client.login(self.HOST, self.PORT)
            if result.get("status") != "ok":
                QMessageBox.warning(
                    None, "错误", result.get("reason", "用户名或密码错误")
                )
                return

            real_username = result.get("username")
            user_id = result.get("user_id")
            print(f"[DEBUG] 登录成功，真实用户名：{real_username}，账号：{user_id}")

            # 保存历史记录
            settings = QSettings("MyChatApp", "LoginHistory")
            history = settings.value("usernames", [], type=list)
            if real_username in history:
                history.remove(real_username)
            history.insert(0, real_username)
            history = history[:10]
            settings.setValue("usernames", history)

            # 2️⃣ 切换 UI
            QMessageBox.information(None, "成功", "登录成功！")
            self.login_ui.close()
            self.chat_ui = ChatWindow(real_username, user_id)
            self.client.recv_callback = self.on_server_msg
            self.client.on_disconnect = self.on_ws_disconnect
            self.chat_ui.send_msg.connect(self.dispatch_send_message)
            self.chat_ui.show()
            # 在登录成功后（self.chat_ui 创建之后）
            # 获取所有用户
            all_users = await self.client.fetch_all_users(self.HOST, self.PORT)
            self.chat_ui.set_all_users(all_users)
            # 获取初始在线用户（可通过 manager.active_connections.keys()，但客户端不知道）
            # 所以我们依赖后续的 system 消息来填充 online_users

            # 3️⃣ 连接 WebSocket（含 login 认证）
            success = await self.client.connect_ws(self.HOST, self.PORT)
            if not success:
                QMessageBox.critical(None, "连接失败", "无法连接 WebSocket 服务器")
                self.chat_ui.close()
                self.login_ui.show()
                return

        except Exception as e:
            QMessageBox.critical(None, "登录异常", f"{type(e).__name__}: {e}")
            if self.chat_ui and self.chat_ui.isVisible():
                self.chat_ui.close()
            if not self.login_ui.isVisible():
                self.login_ui.show()

    # ============================================================
    # WebSocket 断开回调
    # ============================================================
    def on_ws_disconnect(self, exc: websockets.ConnectionClosed):
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
                user_id = result.get("user_id", "未知")
                QMessageBox.information(None, "注册成功", f"注册成功！您的账号 ID 是：\n\n{user_id}\n\n请妥善保存！")
                self.register_ui.close()
            else:
                QMessageBox.warning(None, "注册失败", result.get("reason", "注册失败"))
        except Exception as e:
            QMessageBox.critical(None, "错误", f"注册异常: {e}")

    def show_register_window(self):
        self.register_ui.show()
        self.register_ui.raise_()
        self.register_ui.activateWindow()

    # ============================================================
    # 【关键】消息分发：处理所有 send_msg 信号
    # 支持：group / private / create_group / join_group
    # ============================================================
    def dispatch_send_message(self, msg_dict: dict):
        """统一入口：根据 type 分发不同操作"""
        msg_type = msg_dict.get("type")

        if msg_type == "create_group":
            group_name = msg_dict.get("group_name", "").strip()
            if group_name:
                asyncio.create_task(self.client.create_group(group_name))
            else:
                QMessageBox.warning(self.chat_ui, "提示", "群名称不能为空")

        elif msg_type == "join_group":
            group_id = msg_dict.get("group_id", "").strip()
            if group_id:
                asyncio.create_task(self.client.join_group(group_id))
            else:
                QMessageBox.warning(self.chat_ui, "提示", "群ID无效")

        elif msg_type == "private":
            to_user = msg_dict.get("to")
            text = msg_dict.get("text")
            if to_user and text:
                asyncio.create_task(self.client.send_private(to_user, text))

        elif msg_type == "group":
            to_group = msg_dict.get("to")
            text = msg_dict.get("text")
            if to_group and text:
                asyncio.create_task(self.client.send_group(text, to_group))

        else:
            print(f"[WARN] 未知消息类型: {msg_type}")

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