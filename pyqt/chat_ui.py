from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QLabel, QMenu, QDialog,
    QLineEdit, QMessageBox, QListWidget, QListWidgetItem, QSplitter, QFrame, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QColor
from datetime import datetime
import os

class ChatWindow(QWidget):
    send_msg = pyqtSignal(dict)  # 用于发送消息（含目标）

    def __init__(self, username, user_id):
        super().__init__()
        self.username = username
        self.user_id = user_id
        self.current_target = "__GROUP__"  # 当前选中的会话目标：username 或 Gxxxxxxxxx
        self.current_target_type = "group"  # "group" 或 "private"
        self.group_names = {}  # group_id -> group_name 映射
        self.group_info_cache = {}     # 新增：缓存完整群信息
        self.session_history = {}  # 缓存各会话的消息 [{}, ...]
        self.all_users = []          # 所有用户列表 [{"username": "...", "last_online": "..."}]
        self.online_users = set()    # 当前在线用户名集合
        self.friends_list = set()  # ← 新增：存储好友用户名

        self.setWindowTitle(f"老莫聊天室 - {username} ({user_id})")
        self.resize(900, 600)

        icon_path = "../logo/logo.ico"
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)
        else:
            print(f"[WARN] Icon file not found: {icon_path}")

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
        # 启用自定义上下文菜单
        self.left_panel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.left_panel.customContextMenuRequested.connect(self.show_session_context_menu)

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
        # self.on_session_clicked(self.left_panel.item(0))  # 自动选中第一个

    def set_all_users(self, users: list):
        """初始化所有用户列表"""
        self.all_users = users
        self.refresh_user_list_in_sidebar()
    
    # chat_ui.py - 替换原有的 refresh_user_list_in_sidebar
    def refresh_user_list_in_sidebar(self):
        """刷新左侧会话列表：群聊 → 好友 → 非好友"""
        # 清空所有会话项（保留“创建群聊”、“加入群聊”按钮？不，它们是 QListWidget 之外的）
        # 注意：我们的 left_panel 只包含会话项，按钮在上方
        self.left_panel.clear()

        # === 1. 添加群聊 ===
        # self.group_names: {group_id -> group_name}
        for group_id, group_name in sorted(self.group_names.items()):
            if group_id.startswith("G"):  # 真实群组
                item = QListWidgetItem(f"👥 {group_name}")
                item.setData(Qt.ItemDataRole.UserRole, {"target": group_id, "type": "group"})
                self.left_panel.addItem(item)

        # === 2. 添加私聊项（分好友 / 非好友）===
        # 所有可能私聊对象 = all_users - 自己
        private_targets = []
        for user_info in self.all_users:
            username = user_info["username"]
            if username == self.username:
                continue
            is_online = username in self.online_users
            status = "(在线)" if is_online else "(离线)"
            private_targets.append((username, status))

        # 排序：按用户名字母序
        private_targets.sort(key=lambda x: x[0])

        # 分类
        friend_items = []
        non_friend_items = []

        for username, status in private_targets:
            display_text = f"👤 {username} {status}"
            data = {"target": username, "type": "private"}
            if username in self.friends_list:
                friend_items.append((display_text, data))
            else:
                # 非好友前加 ➕ 标识（可选）
                display_text = f"➕ {username} {status}"
                non_friend_items.append((display_text, data))

        # 先加好友（绿色）
        for text, data in friend_items:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, data)
            item.setForeground(QColor("#00AA00"))  # 绿色字体
            self.left_panel.addItem(item)

        # 再加非好友
        for text, data in non_friend_items:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.left_panel.addItem(item)
    
    def update_title(self, target: str, is_online: bool):
        """更新右上角聊天标题"""
        status = "(在线)" if is_online else "(离线)"
        title_text = f"私聊：{target} {status}"
        self.chat_title.setText(title_text)  
    
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
    
    def show_session_context_menu(self, position):
        """显示会话项的右键菜单"""
        item = self.left_panel.itemAt(position)
        if not item:
            return

        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        target = data.get("target")
        session_type = data.get("type")

        menu = QMenu(self)

        # ====== 新增：统一添加“查看信息”选项 ======
        view_info_action = menu.addAction("查看信息")

        # 只有群聊才显示“退出该群”
        if session_type == "group" and target.startswith("G"):
            menu.addSeparator()
            leave_action = menu.addAction("退出该群")
        else:
            leave_action = None

        # 私聊：根据是否为好友决定是否显示“删除好友”
        delete_action = None
        if session_type == "private":
            menu.addSeparator()
            if target not in self.friends_list:
                add_action = menu.addAction("添加好友")
            else:
                delete_action = menu.addAction("删除好友")
                add_action = None
        else:
            add_action = None

        # 执行菜单弹出
        action = menu.exec(self.left_panel.mapToGlobal(position))
        if not action:
            return  # 用户没选任何项

        # ====== 处理“查看信息” ======
        if action == view_info_action:
            if session_type == "group" and target.startswith("G"):
                # 群聊信息
                group_info = self.group_info_cache.get(target)
                if group_info:
                    dialog = GroupInfoDialog(
                        group_name=group_info["name"],
                        creator=group_info.get("creator", "未知"),
                        created_at=group_info.get("created_at", "未知"),
                        group_id=target,
                        parent=self
                    )
                    dialog.exec()
                else:
                    QMessageBox.warning(self, "提示", "群信息暂不可用")

            elif session_type == "private":
                # 用户信息
                user_info = next((u for u in self.all_users if u["username"] == target), None)
                if user_info:
                    dialog = UserInfoDialog(
                        username=user_info["username"],
                        user_id=user_info.get("user_id", "未知"),
                        last_online=user_info.get("last_online", "从未上线"),
                        parent=self
                    )
                    dialog.exec()
                else:
                    QMessageBox.warning(self, "提示", "用户信息暂不可用")

        # ====== 处理其他操作 ======
        elif action == leave_action:
            # 执行退群逻辑
            self.send_msg.emit({
                "type": "leave_group",
                "group_id": target
            })
            # 本地移除该项（可选）
            row = self.left_panel.row(item)
            self.left_panel.takeItem(row)

            # 如果当前正在聊天的是这个群，清空聊天区
            if self.current_target == target:
                self.current_target = "__GROUP__"
                self.current_target_type = "group"
                self.chat_title.setText("请选择一个会话")
                # 清空消息区
                while self.chat_area.count():
                    child = self.chat_area.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                    elif child.layout():
                        while child.layout().count():
                            sub_child = child.layout().takeAt(0)
                            if sub_child.widget():
                                sub_child.widget().deleteLater()

        elif session_type == "private":
            if add_action and action == add_action:
                self.send_msg.emit({
                    "type": "add_friend",
                    "to": target
                })
                self.show_system_notification(f"已发送好友请求给 {target}")
            elif delete_action and action == delete_action:
                reply = QMessageBox.question(
                    self, "确认", f"确定要删除好友 {target} 吗？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.send_msg.emit({"type": "delete_friend", "to": target})

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

        # === 仅在私聊会话中检测好友请求响应 ===
        if self.current_target_type == "private":
            # 从历史消息中查找最近的好友请求
            history = self.session_history.get(self.current_target, [])
            for msg in reversed(history):  # 从最新往旧找
                if msg.get("type") == "friend_request":
                    upper_text = text.upper()
                    if upper_text in ("Y", "YES"):
                        # 👇 关键：发送 accept_friend 消息，不是普通消息！
                        self.send_msg.emit({
                            "type": "accept_friend",
                            "from": self.current_target  # 或 "from": self.current_target
                        })
                        self.input.clear()
                        self.add_message_to_ui("[系统] 已接受好友请求", is_user=False)
                        return  # ⚠️ 必须 return，阻止发送普通消息

                    elif upper_text in ("N", "NO"):
                        self.input.clear()
                        self.add_message_to_ui("[系统] 已拒绝好友请求", is_user=False)
                        return

                    else:
                        break  # 不是 Y/N，当作普通消息处理
                
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

        if "[系统]" in text and ("请求与你成为好友" in text or "回复 Y" in text):
            label.setStyleSheet("""
                background-color: #fff8e1;
                color: #333;
                border-radius: 12px;
                padding: 12px 8px;
                margin: 4px 0;
                font-size: 16px;
                border: 1px solid #ddd;
            """)
            if is_user:
                row.addStretch()
                row.addWidget(label)
            else:
                row.addWidget(label)
                row.addStretch()
        
        else:
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
    @pyqtSlot(dict)
    def handle_server_message_safely(self, msg: dict):
        """此函数在 Qt 主线程执行，可安全操作 UI"""
        self.handle_server_message(msg)
    
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
        
        elif msg_type == "my_friends":
            friends = msg.get("friends", [])
            self.friends_list.clear()
            self.friends_list.update(friends)
            self.refresh_user_list_in_sidebar()  # 刷新 UI
        
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
            # 重置缓存（可选，确保一致性）
            self.group_info_cache = {}
            
            for g in groups:
                if isinstance(g, dict) and "id" in g and "name" in g:
                    group_id = g["id"]
                    group_name = g["name"]
                    
                    # 👇 1. 保留原有逻辑（必须！）
                    self.group_names[group_id] = group_name
                    
                    # 👇 2. 新增：缓存完整群信息（用于“查看信息”）
                    self.group_info_cache[group_id] = {
                        "name": group_name,
                        "creator": g.get("creator", "未知"),
                        "created_at": g.get("created_at", "未知")
                    }
                    
                    # 👇 3. 更新会话列表（保持原有行为）
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
            gid = msg.get("group_id")
            gname = msg.get("group_name", f"群-{gid}")  # ← 优先用返回的群名
            self.update_or_add_session(gid, gname, "group")
            self.show_system_notification(f"已加入群聊「{gname}」")
        
        elif msg_type == "group_left":
            pass  # UI 不移除，但可标记
        
        # ===== 好友请求 =====
        elif msg_type == "friend_request":
            # 缓存并尝试显示（会自动调用 render_message）
            self._cache_and_maybe_display(msg)
        
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
        raw_type = msg.get("type")

        # ===== 特殊处理 friend_request =====
        if raw_type == "friend_request":
            sender = msg.get("from", "system")
            session_key = sender  # 归入发送者会话
            # 补全字段以便 render_message 使用
            msg.setdefault("sender", sender)
            msg.setdefault("chat_type", "system")
            # 注意：不要设 target，避免干扰
        # ===== 兼容旧格式（group/private）=====
        elif raw_type in ("group", "private"):
            converted_msg = {
                "type": "message",
                "sender": msg.get("from"),
                "target": msg.get("to"),
                "content": msg.get("text"),
                "timestamp": msg.get("timestamp"),
                "chat_type": raw_type
            }
            msg = converted_msg
            sender = msg["sender"]
            target = msg["target"]
            chat_type = msg["chat_type"]

            if chat_type == "private":
                session_key = target if sender == self.username else sender
            else:  # group
                session_key = target
        # ===== 其他标准 message 类型 =====
        else:
            sender = msg.get("sender", "")
            target = msg.get("target", "")
            chat_type = msg.get("chat_type", "")

            if chat_type == "private":
                session_key = target if sender == self.username else sender
            elif chat_type == "group":
                session_key = target
            else:
                # 兜底逻辑
                if target.startswith("G"):
                    session_key = target
                    chat_type = "group"
                    msg["chat_type"] = "group"
                else:
                    session_key = sender if sender != self.username else target
                    chat_type = "private"
                    msg["chat_type"] = "private"

        # === 统一缓存和显示逻辑 ===
        if session_key not in self.session_history:
            self.session_history[session_key] = []
        self.session_history[session_key].append(msg)

        if session_key == self.current_target:
            rendered = self.render_message(msg)
            is_user = (sender == self.username)
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
        
        elif root_type == "friend_request":
            from_user = msg.get("from", "未知用户")
            text = msg.get("text", f"{from_user} 请求与你成为好友")
            options = msg.get("options", ["Y", "N"])
            return f"[系统] {text}\n[回复 Y 接受 / N 拒绝]"
        
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

class GroupInfoDialog(QDialog):
    def __init__(self, group_name: str, creator: str, created_at: str, group_id: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("群聊信息")
        self.setFixedSize(300, 220)
        self.setStyleSheet("background-color: #E6D7FF; border-radius: 12px;")  # 亮紫色

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("👥 群聊信息")
        title.setFont(QFont("微软雅黑", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        info_text = f"""
        <table cellspacing="8">
            <tr><td width="80"><b>群名称：</b></td><td>{group_name}</td></tr>
            <tr><td><b>群&nbsp;&nbsp;号：</b></td><td>{group_id}</td></tr>
            <tr><td><b>创 建 者：</b></td><td>{creator}</td></tr>
            <tr><td><b>创建时间：</b></td><td>{created_at.replace('T', ' ')}</td></tr>
        </table>
        """
        info_label = QLabel(info_text)
        info_label.setFont(QFont("微软雅黑", 10))
        info_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info_label)

        close_btn = QPushButton("关闭")
        close_btn.setFont(QFont("微软雅黑", 10))
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedHeight(30)
        layout.addWidget(close_btn)

        self.setLayout(layout)


class UserInfoDialog(QDialog):
    def __init__(self, username: str, user_id: str, last_online: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("用户信息")
        self.setFixedSize(300, 180)
        self.setStyleSheet("background-color: #FFD7D7; border-radius: 12px;")  # 浅红色

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("👤 用户信息")
        title.setFont(QFont("微软雅黑", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 处理 last_online 为空的情况
        if not last_online or last_online == "None":
            last_online = "从未上线"
        else:
            last_online = last_online.replace('T', ' ')

        info_text = f"""
        <table cellspacing="8">
            <tr><td width="80"><b>用户名：</b></td><td>{username}</td></tr>
            <tr><td><b>账&nbsp;&nbsp;号：</b></td><td>{user_id}</td></tr>
            <tr><td><b>上次在线：</b></td><td>{last_online}</td></tr>
        </table>
        """
        info_label = QLabel(info_text)
        info_label.setFont(QFont("微软雅黑", 10))
        info_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info_label)

        close_btn = QPushButton("关闭")
        close_btn.setFont(QFont("微软雅黑", 10))
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedHeight(30)
        layout.addWidget(close_btn)

        self.setLayout(layout)
