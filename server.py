# server.py
import json
import sqlite3
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ------------------------------
# 允许跨域访问
# ------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# 数据库（用户注册与登录）
# ------------------------------
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("[服务器] 数据库初始化完成")

def register_user(username: str, password: str) -> bool:
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users(username, password) VALUES (?, ?)",
            (username, password)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def check_login(username: str, password: str) -> bool:
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, password)
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None


# ------------------------------
# 在线用户管理（全部用 JSON）
# ------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, username: str, websocket: WebSocket):
        self.active_connections[username] = websocket
        print(f"[服务器] 用户 {username} 已连接 | 在线人数: {len(self.active_connections)}")

        # 通知所有客户端在线人数更新
        await self.broadcast({
            "type": "system",
            "event": "user_join",
            "username": username,
            "online": len(self.active_connections)
        })

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]
            print(f"[服务器] 用户 {username} 已断开 | 在线人数: {len(self.active_connections)}")

    async def send_json(self, username: str, message: dict):
        """发送给单个用户 JSON 消息"""
        if username in self.active_connections:
            try:
                await self.active_connections[username].send_text(json.dumps(message))
            except:
                pass

    async def broadcast(self, message: dict, exclude: str = None):
        """向所有用户广播 JSON"""
        for username, ws in self.active_connections.items():
            if username != exclude:
                try:
                    await ws.send_text(json.dumps(message))
                except:
                    pass


manager = ConnectionManager()

# ------------------------------
# HTTP 接口：注册 / 登录
# ------------------------------
@app.post("/register")
async def api_register(req: Request):
    data = await req.json()
    username = data.get("username")
    password = data.get("password")
    if username and password:
        if register_user(username, password):
            return {"status": "ok"}
        else:
            return {"status": "fail", "reason": "用户名已存在"}
    return {"status": "fail", "reason": "参数缺失"}

@app.post("/login")
async def api_login(req: Request):
    data = await req.json()
    username = data.get("username")
    password = data.get("password")
    if username and password and check_login(username, password):
        return {"status": "ok"}
    return {"status": "fail", "reason": "用户名或密码错误"}


# ------------------------------
# WebSocket 接口
# ------------------------------
@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    await manager.connect(username, websocket)

    try:
        while True:
            raw_data = await websocket.receive_text()

            # ---------------- 解析 JSON ----------------
            try:
                msg = json.loads(raw_data)
            except json.JSONDecodeError:
                print(f"[服务器] JSON 解析失败: {raw_data}")
                continue

            print(f"[服务器] 收到消息: {msg}")

            msg_type = msg.get("type")

            # ---------------- 群聊 ----------------
            if msg_type == "chat":
                text = msg.get("text", "")
                await manager.broadcast({
                    "type": "chat",
                    "from": username,
                    "text": text
                }, exclude= username )

            # ---------------- 私聊 ----------------
            elif msg_type == "private":
                to_user = msg.get("to")
                text = msg.get("text", "")

                if to_user:
                    # 发给对方
                    await manager.send_json(to_user, {
                        "type": "private",
                        "from": username,
                        "to": to_user,
                        "text": text
                    })

    except WebSocketDisconnect:
        manager.disconnect(username)
        await manager.broadcast({
            "type": "system",
            "event": "user_leave",
            "username": username,
            "online": len(manager.active_connections)
        })

    except Exception as e:
        print(f"[服务器] 出现异常: {e}")
        manager.disconnect(username)


# ------------------------------
# 启动服务器
# ------------------------------
if __name__ == "__main__":
    import uvicorn
    init_db()
    print("[服务器] 启动中，监听端口 12345 ...")
    uvicorn.run(app, host="0.0.0.0", port=12345)
