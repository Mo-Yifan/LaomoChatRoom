import sys
import asyncio
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog
from qasync import QEventLoop
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
        # ------------------------------------------------------------

        # 初始化客户端
        self.client = ChatClient()
        self.username = None

        # 登录界面
        self.login_ui = LoginWindow()
        # 用普通槽绑定信号，再在槽内启动异步任务
        self.login_ui.login_request.connect(self.on_login_request)
        self.login_ui.register_request.connect(self.on_register_request)
        self.login_ui.show()

        # 注册界面
        self.register_ui = RegisterWindow()
        self.register_ui.register_request.connect(self.on_register_request)

        # 聊天界面
        self.chat_ui = None

    # ------------------- 登录槽 -------------------
    def on_login_request(self, username, password):
        self.username = username
        self.client.set_credentials(username, password)
        # 在事件循环中执行异步登录
        asyncio.create_task(self.async_login())

    async def async_login(self):
        try:
            result = await self.client.login(self.HOST, self.PORT)
            if result.get("status") == "ok":
                QMessageBox.information(None, "成功", "登录成功！")
                self.login_ui.close()

                # 建立 WebSocket 收消息线程
                self.client.connect_ws(self.HOST, self.PORT)
                if self.client.recv_thread:
                    self.client.recv_thread.recv_signal.connect(self.on_server_msg)

                # 打开聊天界面
                self.chat_ui = ChatWindow(self.username)
                # 将 ChatWindow 的 handle_server_message 注册给客户端的回调
                self.client.recv_callback = self.chat_ui.handle_server_message
                # 将 send_msg 信号绑定到客户端发送方法
                self.chat_ui.send_msg.connect(lambda msg: asyncio.create_task(
                    self.client.send_chat(msg['text']) if msg['type']=='chat' else self.client.send_private(msg['to'], msg['text'])
                ))
                self.chat_ui.show()

            else:
                QMessageBox.warning(None, "错误", result.get("reason", "用户名或密码错误"))
        except Exception as e:
            QMessageBox.critical(None, "错误", f"登录异常: {e}")

    # ------------------- 注册槽 -------------------
    def on_register_request(self, username, password):
        self.client.set_credentials(username, password)
        asyncio.create_task(self.async_register())

    async def async_register(self):
        try:
            result = await self.client.register(self.HOST, self.PORT)
            if result.get("status") == "ok":
                QMessageBox.information(None, "成功", "注册成功，请登录！")
            else:
                QMessageBox.warning(None, "注册失败", result.get("reason", "注册失败"))
        except Exception as e:
            QMessageBox.critical(None, "错误", f"注册异常: {e}")

    # ------------------- 接收服务器消息 -------------------
    def on_server_msg(self, msg):
        if not self.chat_ui:
            return
        msg_type = msg.get("type")
        if msg_type == "chat":
            is_user = msg.get("from") == self.username
            text = msg.get("text", "")
            self.chat_ui.add_message(f"[群聊] {msg.get('from')}: {text}", is_user=is_user)
        elif msg_type == "private":
            is_user = msg.get("from") == self.username
            text = msg.get("text", "")
            self.chat_ui.add_message(f"[私聊] {msg.get('from')} -> 你: {text}", is_user=is_user)

    # ------------------- 启动应用 -------------------
    def run(self):
        loop = QEventLoop(self.app)
        asyncio.set_event_loop(loop)
        with loop:
            loop.run_forever()

if __name__ == "__main__":
    ClientApp().run()
