from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QPushButton, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


class ChatWindow(QWidget):
    send_msg = pyqtSignal(dict)  # 信号：发送消息给主程序处理网络

    def __init__(self, username):
        super().__init__()

        self.username = username
        self.setWindowTitle(f"精美聊天界面 - {username}")
        self.resize(600, 500)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 消息显示区
        self.chat_area = QVBoxLayout()
        self.chat_area.addStretch()  # 用于让消息顶在上方

        scroll_widget = QWidget()
        scroll_widget.setLayout(self.chat_area)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_widget)
        scroll.setStyleSheet("background: #f0f0f0; border: none;")

        main_layout.addWidget(scroll)

        # 输入框 + 发送按钮
        bottom = QHBoxLayout()

        self.input = QLineEdit()
        self.input.setPlaceholderText("输入消息... (群聊直接输入，私聊格式 @username 消息)")
        self.input.setFixedHeight(40)
        self.input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #aaa;
                border-radius: 8px;
                padding-left: 10px;
                font-size: 16px;
            }
        """)

        send_btn = QPushButton("发送")
        send_btn.setFixedHeight(40)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 8px;
                font-size: 16px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)

        send_btn.clicked.connect(self.send_message)

        bottom.addWidget(self.input)
        bottom.addWidget(send_btn)

        main_layout.addLayout(bottom)
        self.setLayout(main_layout)

    def send_message(self):
        """将输入框内容发给主程序，由主程序发送给服务器"""
        text = self.input.text().strip()
        if not text:
            return

        # 支持私聊格式：@username 内容
        if text.startswith("@") and " " in text:
            to_user, msg_text = text[1:].split(" ", 1)
            msg = {
                "type": "private",
                "to": to_user.strip(),
                "text": msg_text.strip()
            }
            # 检查是否发送给自己
            if to_user == self.username:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "无效私聊", "不能给自己发送私聊消息")
                return  # 不发送消息到服务器

            msg = {
                "type": "private",
                "to": to_user,
                "text": msg_text
            }
        else:
            msg = {
                "type": "chat",
                "text": text
            }

        # 发送消息信号给主程序
        self.send_msg.emit(msg)

        # 立即显示自己消息
        display_text = f"[群聊] 我: {text}" if msg["type"] == "chat" else f"[私聊] 我 -> {msg['to']}: {msg['text']}"
        self.add_message(display_text, is_user=True)

        # 清空输入框
        self.input.clear()

    def add_message(self, text, is_user=False):
        """在聊天区域显示消息"""
        label = QLabel(text)
        label.setWordWrap(True)
        label.setFont(QFont("微软雅黑", 14))
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {'#d1f0ff' if is_user else 'white'};
                padding: 10px;
                border-radius: 10px;
                border: 1px solid #ccc;
            }}
        """)

        h = QHBoxLayout()
        if is_user:
            h.addStretch()
            h.addWidget(label)
        else:
            h.addWidget(label)
            h.addStretch()

        # 插入到聊天区域倒数第一个位置（保持最下面是 stretch）
        self.chat_area.insertLayout(self.chat_area.count() - 1, h)

    # ------------------- WebSocket 消息处理接口 -------------------
    def handle_server_message(self, msg: dict):
        """处理从服务器接收到的消息"""
        msg_type = msg.get("type")
        if msg_type == "chat":
            text = f"[群聊] {msg.get('from')}: {msg.get('text')}"
            self.add_message(text, is_user=False)
        elif msg_type == "private":
            text = f"[私聊] {msg.get('from')} -> 我: {msg.get('text')}"
            self.add_message(text, is_user=False)

    # ------------------- 消息渲染函数 -------------------
    def render_message(self, msg: dict) -> str:
        """
        将服务器发送的 JSON 消息渲染成纯文本显示
        支持群聊、私聊、系统消息
        """
        msg_type = msg.get("type")
        
        if msg_type == "system":
            return f"🌐 [系统] {msg.get('text', '')}"
        
        elif msg_type == "chat":
            sender = msg.get("from", "未知")
            content = msg.get("text", "")
            return f"[群聊] {sender}: {content}"
        
        elif msg_type == "private":
            sender = msg.get("from", "未知")
            to = msg.get("to", "你")
            content = msg.get("text", "")
            return f"[私聊] {sender} -> {to}: {content}"
        
        return f"[未知消息] {msg}"