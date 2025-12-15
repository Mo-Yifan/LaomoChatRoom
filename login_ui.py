from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QGraphicsDropShadowEffect, QCompleter
)
from PyQt6.QtGui import QFont, QColor, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QEvent
import sys
import asyncio

class LoginWindow(QWidget):
    login_request = pyqtSignal(str, str)       # 发给 client.py 主程序
    open_register_window = pyqtSignal()  # 去注册信号
    login_success = pyqtSignal(str)            # 登录成功信号

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        self.resize(420, 320)
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6dd5fa, stop:1 #2980b9
                );
            }
        """)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("用户登录")
        title.setFont(QFont("微软雅黑", 22, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)

        self.username = QLineEdit()
        # 加载历史账号
        self.username.installEventFilter(self)  # 安装事件过滤器
        self.settings = QSettings("MyChatApp", "LoginHistory")  # 组织名/应用名
        history = self.settings.value("usernames", [], type=list)
        print(f"[DEBUG] Loaded login history: {history}")

        # 设置 QCompleter
        self.completer = QCompleter(history, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.username.setCompleter(self.completer)

        self.username.setPlaceholderText("用户名")
        self.username.setFixedHeight(40)
        self.username.setStyleSheet("""
            QLineEdit {
                border: none;
                border-radius: 10px;
                padding-left: 15px;
                background: white;
                font-size: 16px;
            }
        """)

        self.password = QLineEdit()
        self.password.setPlaceholderText("密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setFixedHeight(40)
        self.password.setStyleSheet("""
            QLineEdit {
                border: none;
                border-radius: 10px;
                padding-left: 15px;
                background: white;
                font-size: 16px;
            }
        """)

        btn = QPushButton("登录")
        btn.setFixedHeight(40)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #2980b9;
                font-size: 18px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #e8f6ff;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QColor(0, 0, 0, 160))
        btn.setGraphicsEffect(shadow)
        btn.clicked.connect(self.do_login)

        layout.addSpacing(15)
        layout.addWidget(self.username)
        layout.addWidget(self.password)
        layout.addSpacing(20)
        layout.addWidget(btn)

        # 去注册超链接
        self.register_link = QLabel('<a href="#">没有账号？去注册</a>')
        self.register_link.setFont(QFont("微软雅黑", 12))
        self.register_link.setStyleSheet("color: white;")
        self.register_link.setTextFormat(Qt.TextFormat.RichText)
        self.register_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.register_link.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.register_link.linkActivated.connect(self.open_register)
        layout.addWidget(self.register_link)

        self.setLayout(layout)

    def eventFilter(self, obj, event):
        if obj == self.username:
            if event.type() == QEvent.Type.FocusIn:
                # 获得焦点时，如果内容为空，立即弹出全部历史
                if not self.username.text():
                    self.completer.setCompletionPrefix("")  # 清空前缀
                    self.completer.complete()  # 手动弹出
            elif event.type() == QEvent.Type.KeyPress:
                # 可选：按 Esc 时不清空，保持体验
                if event.key() == Qt.Key.Key_Escape:
                    return True  # 阻止默认关闭行为（可选）
        return super().eventFilter(obj, event)
    
    # ------------------- 登录按钮 -------------------
    def do_login(self):
        username = self.username.text()
        password = self.password.text()
        if username and password:
            self.login_request.emit(username, password)

    # ------------------- 去注册 -------------------
    def open_register(self):
        print("[DEBUG] open_register called!")  # ← 加这行
        self.open_register_window.emit() 
