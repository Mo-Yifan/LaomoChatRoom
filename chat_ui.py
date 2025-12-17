from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QPushButton, QLabel, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from datetime import datetime


class ChatWindow(QWidget):
    send_msg = pyqtSignal(dict)  # 发送到主程序（主线程→网络线程）

    def __init__(self, username, user_id):
        super().__init__()

        self.username = username
        self.user_id = user_id  # ← 保存 user_id
        self.setWindowTitle(f"老莫聊天室-当前用户{username}（{user_id}）")  # ← 新标题格式
        self.resize(600, 500)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ====== 消息显示区 ======
        self.chat_area = QVBoxLayout()
        self.chat_area.addStretch()

        scroll_widget = QWidget()
        scroll_widget.setLayout(self.chat_area)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_widget)
        scroll.setStyleSheet("background: #f0f0f0; border: none;")

        main_layout.addWidget(scroll)

        # ====== 输入栏 ======
        bottom = QHBoxLayout()

        self.input = QLineEdit()
        self.input.setPlaceholderText("输入消息...(群聊直接输入，私聊 @用户 内容)")
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
        
    # =============================================================
    # 发送消息
    # =============================================================
    def send_message(self):
        text = self.input.text().strip()
        if not text:
            return

        # 构造消息对象（和服务器返回的结构一致）
        if text.startswith("@") and " " in text:
            to_user, msg_text = text[1:].split(" ", 1)
            to_user = to_user.strip()
            msg_text = msg_text.strip()
            if to_user == self.username:
                QMessageBox.warning(self, "无效私聊", "不能给自己发送私聊消息")
                return
            msg = {
                "type": "private",
                "from": self.username,
                "to": to_user,
                "text": msg_text,
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            }
        else:
            msg = {
                "type": "group",
                "from": self.username,
                "to": "__GROUP__",
                "text": text,
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            }

        # 发送给服务器
        self.send_msg.emit(msg)

        # 本地显示：使用 render_message 统一格式！
        display_text = self.render_message(msg)
        print(">>> 发送消息时渲染结果:", repr(display_text))
        self.add_message(display_text, is_user=True)
        self.input.clear()

    # =============================================================
    # 添加消息到 UI
    # =============================================================
    def add_message(self, text, is_user=False):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setFont(QFont("微软雅黑", 14))

        # 设置最小宽度（例如 300px）
        label.setMinimumWidth(300)
        label.setMaximumWidth(800)  # 防止过宽

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

        self.chat_area.insertLayout(self.chat_area.count() - 1, h)

    # =============================================================
    # 服务器推来的消息
    # =============================================================
    def handle_server_message(self, msg):
        print(f"[SERVER MSG] 收到服务器消息: {msg}")
        msg_type = msg.get("type")

        # ===== 新增：处理系统上线提示 =====
        if msg_type == "system":
            # 注意：event 和 username 在 msg 顶层，不在 extra 里！
            event = msg.get("event")
            username = msg.get("username")

            if event == "user_join":
                if username == self.username:
                    self.show_system_notification("欢迎回来")
                else:
                    self.show_system_notification(f"{username} 上线了")
            elif event == "user_leave":
                self.show_system_notification(f"{username} 下线了")
        
        if msg_type == "auth_success":
            username = msg.get("username")
            if username == self.username:
                self.show_system_notification("欢迎回来，看看你的朋友给你发了什么吧")
    
        elif msg_type == "history":
            print(f"[DEBUG] 收到历史消息，共 {len(msg.get('messages', []))} 条")
            for i, m in enumerate(msg.get("messages", [])):
                print(f"  [{i}] type={type(m)}, content={repr(m)}")
                if isinstance(m, str):
                    print("  ⚠️ 警告：历史消息是字符串！应该为 dict！")
                    self.add_message(m, is_user=False)
                else:
                    rendered = self.render_message(m)
                    sender = m.get("from", "")
                    is_user = (sender == self.username)
                    self.add_message(rendered, is_user=is_user)

        elif msg_type == "group":
            rendered = self.render_message(msg)
            self.add_message(rendered, is_user=(msg.get("from") == self.username))

        elif msg_type == "private":
            rendered = self.render_message(msg)
            self.add_message(rendered, is_user=(msg.get("from") == self.username))

        else:
            unknown_text = f"[未知消息类型: {msg_type}] {msg}"
            self.add_message(unknown_text, is_user=False)

    # =============================================================
    # 渲染服务器消息（统一格式）
    # =============================================================
    def render_message(self, msg: dict) -> str:
        ts_str = msg.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts_str)
        except Exception:
            return f"[无效时间] {msg.get('text', '')}"

        now = datetime.now()
        if dt.date() == now.date():
            display_time = dt.strftime("%H:%M:%S")
        else:
            display_time = dt.strftime("%Y年%m月%d日 %H:%M:%S")

        msg_type = msg.get("type")
        sender = msg.get("from", "未知")
        content = msg.get("text", "")

        if msg_type == "system":
            event_text = msg.get('text', '') or f"{msg.get('username', '未知')} {msg.get('event', '')}"
            return f"[{display_time}] 🌐 [系统] {event_text}"

        elif msg_type == "group":
            return f"[{display_time}] [群聊] {sender}: {content}"   # ← 注意是 display_time

        elif msg_type == "private":
            to_user = msg.get("to", "")
            if to_user == self.username:
                return f"[{display_time}] [私聊] {sender} → 我: {content}"
            else:
                return f"[{display_time}] [私聊] 我 → {to_user}: {content}"

        else:
            return f"[{display_time}] [未知] {content}"
    
    def show_system_notification(self, text: str):
        """显示灰色半透明亚克力风格的系统提示，插入到最新消息下方并居中"""
        print("[DEBUG]渲染中，请稍后")
        # 创建标签
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("微软雅黑", 12))
        
        # 设置样式：亚克力风（半透明灰底 + 圆角 + 边框）
        label.setStyleSheet("""
            background-color: rgba(240, 240, 240, 0.8);   /* 半透明灰白 */
            color: #333;
            border-radius: 12px;
            padding: 8px 16px;
            margin: 5px 0;
            border: 1px solid rgba(200, 200, 200, 0.8);
            font-size: 12px;
        """)

        # 创建水平布局，让 label 居中
        h_layout = QHBoxLayout()
        h_layout.addStretch()  # 左边留空
        h_layout.addWidget(label)  # 居中
        h_layout.addStretch()  # 右边留空

        # 插入到 chat_area 的最后一个位置（最新消息之后）
        self.chat_area.addLayout(h_layout)