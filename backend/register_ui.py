from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QGraphicsDropShadowEffect, QMessageBox
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, pyqtSignal


class RegisterWindow(QWidget):
    register_request = pyqtSignal(str, str)  # 信号：发给客户端处理注册

    def __init__(self):
        super().__init__()
        self.setWindowTitle("用户注册")
        self.resize(420, 380)

        # 背景渐变
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ff9a9e, stop:1 #fad0c4
                );
            }
        """)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 标题
        title = QLabel("用户注册")
        title.setFont(QFont("微软雅黑", 22, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)

        # 用户名输入
        self.username = QLineEdit()
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

        # 密码输入
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

        # 确认密码
        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("确认密码")
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.setFixedHeight(40)
        self.confirm_password.setStyleSheet("""
            QLineEdit {
                border: none;
                border-radius: 10px;
                padding-left: 15px;
                background: white;
                font-size: 16px;
            }
        """)

        # 注册按钮
        btn = QPushButton("注册")
        btn.setObjectName("注册")
        btn.setFixedHeight(40)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #ff6f61;
                font-size: 18px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #ffe6e1;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QColor(0, 0, 0, 160))
        btn.setGraphicsEffect(shadow)

        # 点击按钮注册
        btn.clicked.connect(self.do_register)

        # 回车触发注册
        self.confirm_password.returnPressed.connect(btn.click)

        # 布局
        layout.addSpacing(15)
        layout.addWidget(self.username)
        layout.addWidget(self.password)
        layout.addWidget(self.confirm_password)
        layout.addSpacing(20)
        layout.addWidget(btn)

        self.setLayout(layout)

    # ------------------ 执行注册 ------------------
    def do_register(self):
        username = self.username.text().strip()
        password = self.password.text().strip()
        confirm = self.confirm_password.text().strip()

        if not username or not password or not confirm:
            QMessageBox.warning(self, "提示", "请完整填写所有字段")
            return
        if password != confirm:
            QMessageBox.warning(self, "提示", "两次输入的密码不一致")
            return

        # 发送信号给客户端处理注册
        self.register_request.emit(username, password)

    # ------------------ 处理注册结果 ------------------
    def handle_register_response(self, response: dict):
        """调用此函数显示注册结果"""
        if response.get("status") == "ok":
            QMessageBox.information(self, "注册成功", "注册成功，请登录！")
            self.close()
        else:
            QMessageBox.warning(self, "注册失败", response.get("reason", "注册失败"))
