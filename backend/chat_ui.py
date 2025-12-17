from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QLabel,
    QLineEdit, QMessageBox, QListWidget, QListWidgetItem, QSplitter, QFrame, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon
from datetime import datetime


class ChatWindow(QWidget):
    send_msg = pyqtSignal(dict)  # 用于发送消息（含目标）

    def __init__(self, username, user_id):
        super().__init__()
        self.username = username
        self.user_id = user_id
        self.current_target = "__GROUP__"  # 当前选中的会话目标：username 或 Gxxxxxxxxx
        self.current_target_type = "group"  # "group" 或 "private"
        self.group_names = {}  # group_id -> group_name 映射
        self.session_history = {}  # 缓存各会话的消息 [{}, ...]
        self.all_users = []          # 所有用户列表 [{"username": "...", "last_online": "..."}]
        self.online_users = set()    # 当前在线用户名集合

        self.setWindowTitle(f"老莫聊天室 - {username} ({user_id})")
        self.resize(900, 600)

        # 主布局：左右分栏
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ====== 左侧面板：顶部按钮 + 会话列表 ======
        left_widget = QWidget()
        left_widget.setFixedWidth(250)
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 创建群聊按钮
        create_group_btn = QPushButton("创建群聊")
        create_group_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #333;
                border: none;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
                text-align: left;
                padding-left: 15px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)
        create_group_btn.clicked.connect(self.show_create_group_dialog)
        left_layout.addWidget(create_group_btn)
        # --- 加入群聊 ---
        join_group_btn = QPushButton("加入群聊")
        join_group_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #333;
                border: none;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
                text-align: left;
                padding-left: 15px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)
        join_group_btn.clicked.connect(self.show_join_group_dialog)
        left_layout.addWidget(join_group_btn)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #ccc;")
        left_layout.addWidget(line)

        # 会话列表
        self.left_panel = QListWidget()
        self.left_panel.setStyleSheet("""
            QListWidget {
                border: none;
                background: #f8f8f8;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background: #e0f0ff;
            }
        """)
        self.left_panel.itemClicked.connect(self.on_session_clicked)
        left_layout.addWidget(self.left_panel)

        left_widget.setLayout(left_layout)
        main_layout.addWidget(left_widget)

        # ====== 右侧面板：聊天区 ======
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(10, 10, 10, 10)

        # 聊天标题
        self.chat_title = QLabel("请选择一个会话")
        self.chat_title.setFont(QFont("微软雅黑", 16, QFont.Weight.Bold))
        self.chat_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.chat_title)

        # 消息显示区（可滚动）
        self.chat_area = QVBoxLayout()
        self.chat_area.setAlignment(Qt.AlignmentFlag.AlignTop)  # 从顶部开始
        self.chat_area.setSpacing(5)
        self.chat_area.addStretch()
        scroll_widget = QWidget()
        scroll_widget.setLayout(self.chat_area)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_widget)
        scroll.setStyleSheet("background: #f0f0f0; border: none;")
        right_layout.addWidget(scroll)

        # 输入栏
        bottom = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入消息...")
        self.input.setFixedHeight(40)
        self.input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #aaa;
                border-radius: 8px;
                padding-left: 10px;
                font-size: 16px;
            }
        """)
        self.input.returnPressed.connect(self.send_message)  # 回车发送

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
        right_layout.addLayout(bottom)

        right_widget.setLayout(right_layout)
        main_layout.addWidget(right_widget)

        self.setLayout(main_layout)

        # 初始化默认会话（可选）
        self.add_session_item("__GROUP__", "默认群聊", "group")
        self.on_session_clicked(self.left_panel.item(0))  # 自动选中第一个

    def set_all_users(self, users: list):
        """初始化所有用户列表"""
        self.all_users = users
        self.refresh_user_list_in_sidebar()
    
    def refresh_user_list_in_sidebar(self):
        """根据 all_users 和 online_users 刷新左侧用户列表"""
        # 先移除所有非群聊项（保留“创建群聊”、“加入群聊”按钮）
        # 我们约定：用户会话的 type="private"

        # 清除非群聊的私聊项
        items_to_remove = []
        for i in range(self.left_panel.count()):
            item = self.left_panel.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data.get("type") == "private":
                items_to_remove.append(item)

        for item in items_to_remove:
            self.left_panel.takeItem(self.left_panel.row(item))

        # 重新添加所有用户
        for user_info in self.all_users:
            username = user_info["username"]
            if username == self.username:
                continue  # 不显示自己

            is_online = username in self.online_users
            status = "(在线)" if is_online else "(离线)"
            display_name = f"{username} {status}"

            # 添加到列表（避免重复）
            exists = False
            for i in range(self.left_panel.count()):
                item = self.left_panel.item(i)
                data = item.data(Qt.ItemDataRole.UserRole)
                if data and data.get("target") == username:
                    exists = True
                    # 更新显示文本
                    icon = "👤"
                    item.setText(f"{icon} {display_name}")
                    break

            if not exists:
                self.add_session_item(username, display_name, "private")
    
    def update_title(self, target: str, is_online: bool):
        """更新右上角聊天标题"""
        status = "(在线)" if is_online else "(离线)"
        title_text = f"私聊：{target} {status}"
        self.title_label.setText(title_text)  # 假设你有 title_label
    
    # =============================================================
    # 创建与加入群聊
    # =============================================================
    def show_create_group_dialog(self):
        """弹出创建群聊对话框"""
        group_name, ok = QInputDialog.getText(
            self,
            "创建群聊",
            "请输入群名称:",
            QLineEdit.EchoMode.Normal,
            ""
        )
        if ok and group_name.strip():
            # 发送创建群信号（由 main.py 接收并调用 client.create_group）
            self.send_msg.emit({
                "type": "create_group",
                "group_name": group_name.strip()
            })
        elif ok and not group_name.strip():
            QMessageBox.warning(self, "提示", "群名称不能为空")
    
    def show_join_group_dialog(self):
        """弹出加入群聊对话框"""
        group_id, ok = QInputDialog.getText(
            self,
            "加入群聊",
            "请输入群ID（格式：G + 9位数字，例如 G123456789）:",
            QLineEdit.EchoMode.Normal,
            ""
        )
        if not ok:
            return  # 用户取消

        group_id = group_id.strip()
        if not group_id:
            QMessageBox.warning(self, "提示", "群ID不能为空")
            return

        # 校验格式：必须以 G 开头，后面是9位数字
        import re
        if not re.fullmatch(r"G\d{9}", group_id):
            QMessageBox.warning(self, "格式错误", "群ID必须是 'G' 后跟9位数字，例如 G123456789")
            return

        # 发送加入指令
        self.send_msg.emit({
            "type": "join_group",
            "group_id": group_id
        })
    # =============================================================
    # 会话管理
    # =============================================================

    def add_session_item(self, target_id: str, name: str, session_type: str):
        """添加一个会话到左侧列表"""
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, {"target": target_id, "type": session_type})
        
        # 设置显示文本
        icon = "👥" if session_type == "group" else "👤"
        item.setText(f"{icon} {name}")
        self.left_panel.addItem(item)

    def update_or_add_session(self, target_id: str, name: str, session_type: str):
        """如果存在则更新，否则新增（避免重复）"""
        for i in range(self.left_panel.count()):
            item = self.left_panel.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data["target"] == target_id:
                # 更新名称（比如群名修改）
                icon = "👥" if session_type == "group" else "👤"
                item.setText(f"{icon} {name}")
                return
        self.add_session_item(target_id, name, session_type)

    def on_session_clicked(self, item):
        """切换会话"""
        data = item.data(Qt.ItemDataRole.UserRole)
        self.current_target = data["target"]
        self.current_target_type = data["type"]

        # 更新标题
        if self.current_target_type == "group":
            self.chat_title.setText(f"群聊：{item.text()[2:]}")  # 去掉 emoji
        else:
            self.chat_title.setText(f"私聊：{item.text()[2:]}")

        # 清空当前聊天区
        while self.chat_area.count():
            child = self.chat_area.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                # 删除 layout 中的 widget
                while child.layout().count():
                    sub_child = child.layout().takeAt(0)
                    if sub_child.widget():
                        sub_child.widget().deleteLater()

        # 加载缓存的历史消息
        msgs = self.session_history.get(self.current_target, [])
        for msg in msgs:
            rendered = self.render_message(msg)
            is_user = (msg.get("sender") == self.username)
            self.add_message_to_ui(rendered, is_user)

    # =============================================================
    # 消息发送
    # =============================================================

    def send_message(self):
        text = self.input.text().strip()
        if not text:
            return

        # === 构造标准格式的消息（和服务器返回的一致）===
        if self.current_target_type == "group":
            local_msg = {
                "type": "message",
                "sender": self.username,
                "target": self.current_target,
                "content": text,
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "chat_type": "group"
            }
        else:
            local_msg = {
                "type": "message",
                "sender": self.username,
                "target": self.current_target,
                "content": text,
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "chat_type": "private"
            }

        # 发送给服务器（网络层可能需要旧格式）
        # 注意：这里你可以按服务器要求构造另一份 payload
        if self.current_target_type == "group":
            network_payload = {
                "type": "group",
                "from": self.username,
                "to": self.current_target,
                "text": text
            }
        else:
            network_payload = {
                "type": "private",
                "from": self.username,
                "to": self.current_target,
                "text": text
            }

        self.send_msg.emit(network_payload)  # 发给服务器

        # 本地立即显示（使用标准格式）
        rendered = self.render_message(local_msg)
        self.add_message_to_ui(rendered, is_user=True)
        self.input.clear()

        # 缓存到历史记录
        if self.current_target not in self.session_history:
            self.session_history[self.current_target] = []
        self.session_history[self.current_target].append(local_msg)

    # =============================================================
    # 消息显示（UI）
    # =============================================================
    def add_message_to_ui(self, text: str, is_user: bool):
        row = QHBoxLayout()
        label = QLabel(text)
        label.setWordWrap(True)
        label.setMaximumWidth(int(self.width() * 4.0))  # 限制最大宽度
        label.setAlignment(Qt.AlignmentFlag.AlignLeft)  # 文本左对齐
        
        print("[DEBUG]is_user =", is_user) 
        if is_user:
            label.setStyleSheet("""
                background-color: #f0ffff;
                color: #333;
                border-radius: 12px;
                padding: 12px 8px;           /* 增加内边距 */
                margin: 4px 0;
                font-size: 16px;              /* 字体变大 */
                font-weight: normal;          /* 可选：加粗 */
                border: 1px solid #ddd;
            """)
            row.addStretch()
            row.addWidget(label)
        else:
            label.setStyleSheet("""
                background-color: white;
                color: #333;
                border-radius: 12px;
                padding: 12px 8px;           /* 增加内边距 */
                margin: 4px 0;
                font-size: 16px;              /* 字体变大 */
                font-weight: normal;          /* 可选：加粗 */
                border: 1px solid #ddd;
            """)
            row.addWidget(label)
            row.addStretch()

        self.chat_area.addLayout(row)

    # =============================================================
    # 处理服务器消息
    # =============================================================

    def handle_server_message(self, msg):
        print(f"[UI] 收到服务器消息: {msg}")
        msg_type = msg.get("type")

        # ===== 系统消息 =====
        if msg_type == "system":
            event = msg.get("event")
            username = msg.get("username")
            if event == "user_online":
                if username != self.username:
                    self.online_users.add(username)
                    self.refresh_user_list_in_sidebar()
                    # 更新当前会话标题（如果正在和该用户聊天）
                    if self.current_target == username:
                        self.update_title(username, True)
            elif event == "user_leave":
                self.online_users.discard(username)
                self.refresh_user_list_in_sidebar()
                if self.current_target == username:
                    self.update_title(username, False)
        
        elif msg_type == "online_users":
            usernames = msg.get("usernames", [])
            self.online_users = set(usernames)
            print(f"[UI] 收到在线用户列表: {usernames}")
            
            # 刷新左侧栏
            self.refresh_user_list_in_sidebar()
            
            # 如果当前正在聊天的用户状态变了，也更新标题
            if self.current_target and self.current_target_type == "private":
                is_online = self.current_target in self.online_users
                self.update_title(self.current_target, is_online)

        # ===== 认证成功 =====
        elif msg_type == "auth_success":
            self.show_system_notification("欢迎回来！")

        # ===== 推送我的群列表 =====
        elif msg_type == "my_groups":
            groups = msg.get("groups", [])
            for g in groups:
                if isinstance(g, dict) and "id" in g and "name" in g:
                    group_id = g["id"]
                    group_name = g["name"]
                    self.update_or_add_session(group_id, group_name, "group")

        # ===== 群创建成功 =====
        elif msg_type == "group_created":
            group_id = msg.get("group_id")
            group_name = msg.get("group_name", f"群-{group_id}")  # 默认格式备用
            if group_id:
                self.update_or_add_session(group_id, group_name, "group")
                self.show_system_notification(f"群「{group_name}」创建成功！")

        # ===== 加入/退出群通知 =====
        elif msg_type == "group_joined":
            # 可能需要从其他地方获取群名？这里暂用 ID
            gid = msg.get("group_id")
            self.update_or_add_session(gid, f"群-{gid}", "group")
        
        elif msg_type == "group_left":
            pass  # UI 不移除，但可标记

        # ===== 历史消息 =====
        elif msg_type == "history":
            print(f"[DEBUG] 收到历史消息，共 {len(msg.get('messages', []))} 条")
            for m in msg.get("messages", []):
                if isinstance(m, dict):
                    # 历史消息也要走缓存和显示逻辑
                    self._cache_and_maybe_display(m)

        # ===== 实时聊天消息 =====
        elif msg_type == "group":
            # 群聊消息
            self._cache_and_maybe_display(msg)
        
        elif msg_type == "private":
            # 私聊消息
            self._cache_and_maybe_display(msg)
        
        elif msg_type == "message":
            # 所有实时聊天消息（群/私聊）都通过统一入口处理
            self._cache_and_maybe_display(msg)

        else:
            unknown_text = f"[未知消息类型: {msg_type}] {msg}"
            self.add_message_to_ui(unknown_text, is_user=False)

    def _cache_and_maybe_display(self, msg: dict):
        # ===== 新增：兼容旧格式（from/to/text/type=group） =====
        raw_type = msg.get("type")
        if raw_type in ("group", "private"):
            # 转换为标准格式
            converted_msg = {
                "type": "message",                     # 统一为 "message"
                "sender": msg.get("from"),
                "target": msg.get("to"),
                "content": msg.get("text"),
                "timestamp": msg.get("timestamp"),
                "chat_type": raw_type                  # "group" or "private"
            }
            msg = converted_msg  # 后续逻辑使用新格式
        
        """缓存消息，并在当前会话时显示"""
        sender = msg.get("sender", "")      # ← 改为 "sender"
        target = msg.get("target", "")      # ← 改为 "target"
        chat_type = msg.get("chat_type", "")

        # 确定这条消息属于哪个会话
        if chat_type == "private":
            if sender == self.username:
                session_key = target  # 我发给别人的私聊
            else:
                session_key = sender  # 别人发给我的私聊
        elif chat_type == "group":
            session_key = target      # 群ID
        else:
            # 兜底：尝试从 target 推断
            if target.startswith("G"):
                session_key = target
                chat_type = "group"
                msg["chat_type"] = "group"  # 补全
            else:
                session_key = sender if sender != self.username else target
                chat_type = "private"
                msg["chat_type"] = "private"

        # 缓存消息
        if session_key not in self.session_history:
            self.session_history[session_key] = []
        self.session_history[session_key].append(msg)

        # 如果当前正在查看这个会话，则显示
        if session_key == self.current_target:
            rendered = self.render_message(msg)
            is_user = (sender == self.username)
            print(f"[DEBUG] self.username = {repr(self.username)}")
            print(f"[DEBUG] sender = {repr(sender)}")
            print(f"[DEBUG] is_user = {sender == self.username}")
            self.add_message_to_ui(rendered, is_user=is_user)

    # =============================================================
    # 渲染消息（保持不变）
    # =============================================================
    def render_message(self, msg: dict) -> str:
        ts_str = msg.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts_str)
        except Exception:
            return f"[无效时间] {msg.get('content', '')}"

        now = datetime.now()
        if dt.date() == now.date():
            display_time = dt.strftime("%H:%M:%S")
        else:
            display_time = dt.strftime("%Y年%m月%d日 %H:%M:%S")

        sender = msg.get("sender", "未知")
        root_type = msg.get("type")
        content = msg.get("content", "")
        chat_type = msg.get("chat_type")

        print(f"[DEBUG render] chat_type={repr(chat_type)}, msg={msg}")  # ← 加这行

        if root_type == "group":
            return f"[{display_time}] {sender}: {content}"
        
        elif root_type == "private":
            if sender == self.username:
                return f"[{display_time}] 我: {content}"
            else:
                return f"[{display_time}] {sender}: {content}"
        
        elif root_type == "message":
            if chat_type == "group":
                return f"[{display_time}] {sender}: {content}"
            elif chat_type == "private":
                if sender == self.username:
                    return f"[{display_time}] 我: {content}"
                else:
                    return f"[{display_time}] {sender}: {content}"
        else:
            return f"[{display_time}] [系统] {content}"

    def show_system_notification(self, text: str):
        """显示灰色半透明亚克力风格的系统提示"""
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("微软雅黑", 12))
        label.setStyleSheet("""
            background-color: rgba(240, 240, 240, 0.8);
            color: #333;
            border-radius: 12px;
            padding: 8px 16px;
            margin: 5px 0;
            border: 1px solid rgba(200, 200, 200, 0.8);
            font-size: 12px;
        """)
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(label)
        h_layout.addStretch()
        self.chat_area.addLayout(h_layout)