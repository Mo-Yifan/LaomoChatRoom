# ============================================================ 
# 统一消息格式 + message_type 版本 server.py（增强认证版 + 全函数日志）
# ✅ 支持：私聊 / 群聊 / 离线消息 / 历史漫游 / 防冒用 / 重复登录踢人
# ✅ 客户端无需 extra_headers，彻底避开 Windows asyncio 兼容性问题
# ✅ 已添加全函数操作日志（仅 print，无功能改动）
# ============================================================
import json
import sqlite3
from typing import Dict
from datetime import datetime
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import websockets
import random

app = FastAPI()

# ============================================================
# 静态文件服务 + 根路径重定向（新增）
# ============================================================
# 挂载 web 目录（注意路径）
if os.path.exists("../web"):
    app.mount("/web", StaticFiles(directory="../web"), name="web")

@app.get("/")
async def root():
    return RedirectResponse(url="/web/chat.html")  # ← 现在 /web 是有效的
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 生成唯一用户 ID 的辅助函数
# ============================================================
def generate_unique_user_id(cursor, max_attempts=100):
    """生成 10 位唯一数字 ID"""
    for _ in range(max_attempts):
        # 生成 10 位数字字符串（允许前导0）
        candidate = f"{random.randint(0, 9999999999):010d}"
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (candidate,))
        if cursor.fetchone() is None:
            return candidate
    raise RuntimeError("无法生成唯一用户ID（尝试次数过多）")

#===========================================================
# 生成唯一群 ID 的辅助函数
#===========================================================
def generate_unique_group_id(cursor, max_attempts=100):
    """生成 10 位唯一群 ID，格式为 G + 9 位数字（如 G123456789）"""
    for _ in range(max_attempts):
        candidate = "G" + f"{random.randint(0, 999999999):09d}"
        cursor.execute("SELECT 1 FROM groups WHERE group_id = ?", (candidate,))
        if cursor.fetchone() is None:
            return candidate
    raise RuntimeError("无法生成唯一群ID（尝试次数过多）")

# ============================================================
# 用户存在性检查函数
# ============================================================
def user_exists(username: str) -> bool:
    """检查用户是否存在"""
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"[ERROR] user_exists failed: {e}")
        return False

# ============================================================
# 数据库初始化
# ============================================================
def init_db():
    print("[LOG] init_db() called")
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                user_id TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                last_online TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                user1 TEXT NOT NULL,
                user2 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user1, user2)
            )
        """)

        # === 新增：好友请求表 ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friend_requests (
                from_user TEXT NOT NULL,
                to_user TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (from_user, to_user)
            )
        """)

        conn.commit()
        conn.close()

        conn = sqlite3.connect("../data/messages.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                message_type TEXT NOT NULL,
                delivered INTEGER DEFAULT 0
            )
        """)

        conn.commit()
        conn.close()

        # === groups.db: 群组元数据（新增）===
        conn = sqlite3.connect("../data/groups.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                group_id TEXT PRIMARY KEY,
                group_name TEXT NOT NULL,
                creator TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                group_id TEXT NOT NULL,
                username TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                UNIQUE(group_id, username)
            )
        """)
        conn.commit()
        conn.close()

        print("[LOG] init_db() succeeded: tables created or exist")
    except Exception as e:
        print(f"[LOG] init_db() failed: {e}")

init_db()

# ============================================================
# API：注册 / 登录（保持不变）
# ============================================================
def register_user(username: str, password: str) -> tuple[bool, str]:  # 返回 (成功, user_id)
    print(f"[LOG] register_user(username={username}) called")
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        
        # 生成唯一 ID
        user_id = generate_unique_user_id(cursor)
        
        cursor.execute(
            "INSERT INTO users(username, password, user_id, last_online) VALUES (?, ?, ?, ?)",
            (username, password, user_id, None)
        )
        conn.commit()
        conn.close()
        print(f"[LOG] register_user({username}) succeeded, ID={user_id}")
        return True, user_id
    except sqlite3.IntegrityError as e:
        print(f"[LOG] register_user({username}) failed: user exists")
        return False, ""
    except Exception as e:
        print(f"[LOG] register_user({username}) failed with error: {e}")
        return False, ""

def check_login(identifier: str, password: str) -> tuple[bool, str]:
    """
    identifier 可以是 username 或 user_id
    返回 (是否成功, 实际用户名)
    """
    print(f"[LOG] check_login(identifier={identifier}) called")
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        # 尝试按 username 或 user_id 查
        cursor.execute(
            "SELECT username FROM users WHERE (username = ? OR user_id = ?) AND password = ?",
            (identifier, identifier, password)
        )
        result = cursor.fetchone()
        conn.close()
        if result:
            real_username = result[0]
            print(f"[LOG] check_login({identifier}) succeeded → username={real_username}")
            return True, real_username
        else:
            print(f"[LOG] check_login({identifier}) failed")
            return False, ""
    except Exception as e:
        print(f"[LOG] check_login({identifier}) failed: {e}")
        return False, ""

def update_last_online(username: str, time):
    print(f"[LOG] update_last_online(username={username}, time={time}) called")
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_online=? WHERE username=?", (time, username)
        )
        conn.commit()
        conn.close()
        print(f"[LOG] update_last_online({username}) succeeded")
    except Exception as e:
        print(f"[LOG] update_last_online({username}) failed: {e}")

# ============================================================
# 群组管理函数
# ============================================================
def create_group(creator: str, group_name: str) -> tuple[bool, str]:
    print(f"[LOG] create_group(creator={creator}, name={group_name}) called")
    try:
        conn = sqlite3.connect("../data/groups.db")
        cursor = conn.cursor()
        
        # 生成唯一群ID
        for _ in range(100):
            candidate = "G" + f"{random.randint(0, 999999999):09d}"
            cursor.execute("SELECT 1 FROM groups WHERE group_id = ?", (candidate,))
            if cursor.fetchone() is None:
                gid = candidate
                break
        else:
            raise RuntimeError("无法生成唯一群ID")

        # 【关键】生成当前时间字符串
        created_at = datetime.now().isoformat(timespec="seconds")  # 如 "2025-12-17T16:30:45"

        # 【关键】插入所有 NOT NULL 字段：group_id, group_name, creator, created_at
        cursor.execute(
            "INSERT INTO groups (group_id, group_name, creator, created_at) VALUES (?, ?, ?, ?)",
            (gid, group_name, creator, created_at)
        )
        
        # 同时将创建者加入群成员表
        cursor.execute(
            "INSERT INTO group_members (group_id, username, joined_at) VALUES (?, ?, ?)",
            (gid, creator, created_at)
        )
        
        conn.commit()
        conn.close()
        print(f"[LOG] create_group succeeded: {gid} ({group_name})")
        return True, gid
    except Exception as e:
        print(f"[ERROR] create_group failed: {e}")
        return False, ""

async def join_group(username: str, group_id: str) -> bool:
    print(f"[LOG] join_group({username}, {group_id}) called")
    try:
        # 检查群是否存在
        conn = sqlite3.connect("../data/groups.db")
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM groups WHERE group_id = ?", (group_id,))
        if not cursor.fetchone():
            conn.close()
            return False

        # 检查是否已加入
        cursor.execute("SELECT 1 FROM group_members WHERE username = ? AND group_id = ?", (username, group_id))
        if cursor.fetchone():
            conn.close()
            return True  # 已加入，无需重复插入

        # 插入成员关系
        now = datetime.now().isoformat(timespec="seconds")
        cursor.execute(
            "INSERT INTO group_members (username, group_id, joined_at) VALUES (?, ?, ?)",
            (username, group_id, now)
        )
        conn.commit()
        conn.close()

        # 【关键】获取群名称并发送给用户
        cursor = sqlite3.connect("../data/groups.db").cursor()
        cursor.execute("SELECT group_name FROM groups WHERE group_id = ?", (group_id,))
        row = cursor.fetchone()
        group_name = row[0] if row else f"群-{group_id}"
        cursor.close()

        # 推送 my_groups
        groups = get_user_groups(username)
        my_groups = [{"id": gid, "name": gname} for (gid, gname) in groups]
        await manager.send_json(username, {
            "type": "my_groups",
            "groups": my_groups
        })

        # 广播（使用 manager.broadcast，不要 broadcast_system）
        system_msg = {
            "type": "system",
            "event": "user_joined_group",
            "username": username,
            "text": f"{username} 加入了群聊"
        }
        await manager.broadcast(system_msg, exclude=username)

        return True
    
    except Exception as e:
        print(f"[ERROR] join_group failed: {e}")
        return False

def leave_group(username: str, group_id: str) -> bool:
    print(f"[LOG] leave_group(user={username}, group={group_id}) called")
    try:
        conn = sqlite3.connect("../data/groups.db")
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM group_members WHERE group_id = ? AND username = ?",
            (group_id, username)
        )
        conn.commit()
        conn.close()
        print(f"[LOG] leave_group succeeded")
        return True
    except Exception as e:
        print(f"[LOG] leave_group failed: {e}")
        return False

def get_user_groups(username: str):
    """获取用户加入的所有群组 [(group_id, group_name), ...]"""
    print(f"[LOG] get_user_groups(user={username}) called")
    try:
        conn = sqlite3.connect("../data/groups.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.group_id, g.group_name, g.creator, g.created_at
            FROM group_members gm
            JOIN groups g ON gm.group_id = g.group_id
            WHERE gm.username = ?
        """, (username,))
        groups = cursor.fetchall()
        conn.close()
        print(f"[LOG] get_user_groups returned {len(groups)} groups")
        return groups
    except Exception as e:
        print(f"[LOG] get_user_groups failed: {e}")
        return []

# ============================================================
# 好友管理函数
# ============================================================
def add_friend(user_a: str, user_b: str) -> bool:
    """添加好友关系（无向）"""
    if user_a == user_b:
        return False
    
    # 确保 user1 < user2，保证唯一存储
    u1, u2 = sorted([user_a, user_b])
    
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        now = datetime.now().isoformat(timespec="seconds")
        cursor.execute(
            "INSERT OR IGNORE INTO friends (user1, user2, created_at) VALUES (?, ?, ?)",
            (u1, u2, now)
        )
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        print(f"[ERROR] add_friend failed: {e}")
        return False


def are_friends(user_a: str, user_b: str) -> bool:
    """判断两人是否为好友"""
    if user_a == user_b:
        return True  # 自己和自己算“好友”（方便逻辑）
    u1, u2 = sorted([user_a, user_b])
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM friends WHERE user1 = ? AND user2 = ?", (u1, u2))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        return False


def get_friends_list(username: str) -> list:
    """获取某用户的所有好友列表"""
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user2 FROM friends WHERE user1 = ?
            UNION
            SELECT user1 FROM friends WHERE user2 = ?
        """, (username, username))
        friends = [row[0] for row in cursor.fetchall()]
        conn.close()
        return friends
    except Exception as e:
        print(f"[ERROR] get_friends_list failed: {e}")
        return []

def create_friend_request(sender: str, receiver: str) -> bool:
    """创建好友请求"""
    print(f"[DB DEBUG] create_friend_request called with:")
    print(f"  sender = {repr(sender)}")
    print(f"  receiver = {repr(receiver)}")
    print(f"  sender == receiver? {sender == receiver}")
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        now = datetime.now().isoformat(timespec="seconds")
        print(f"[DB DEBUG] Executing INSERT INTO friend_requests...")
        cursor.execute(
            "INSERT OR IGNORE INTO friend_requests (from_user, to_user, created_at) VALUES (?, ?, ?)",
            (sender, receiver, now)
        )
        conn.commit()
        success = cursor.rowcount > 0
        print(f"[DB DEBUG] INSERT rowcount = {cursor.rowcount}")
        conn.close()
        return success
    except Exception as e:
        print(f"[ERROR] create_friend_request failed: {e}")
        return False


def has_pending_request(sender: str, receiver: str) -> bool:
    """检查是否存在待处理的请求（sender → receiver）"""
    try:
        print("[DEBUG] has_pending_request called")
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM friend_requests WHERE from_user = ? AND to_user = ?",
            (sender, receiver)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"[ERROR] has_pending_request failed: {e}")
        return False


def accept_friend_request(sender: str, receiver: str) -> bool:
    """接受好友请求：建立好友关系 + 删除请求"""
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()

        # 检查请求是否存在
        cursor.execute(
            "SELECT 1 FROM friend_requests WHERE from_user = ? AND to_user = ?",
            (sender, receiver)
        )
        if not cursor.fetchone():
            conn.close()
            return False

        # 建立双向好友关系（使用你已有的 add_friend）
        add_friend(sender, receiver)

        # 删除请求
        cursor.execute(
            "DELETE FROM friend_requests WHERE from_user = ? AND to_user = ?",
            (sender, receiver)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] accept_friend_request failed: {e}")
        return False

def get_pending_friend_requests(to_user: str) -> list:
    """获取某用户的所有待处理好友请求（返回 from_user 列表）"""
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT from_user FROM friend_requests WHERE to_user = ?",
            (to_user,)
        )
        requests = [row[0] for row in cursor.fetchall()]
        conn.close()
        return requests
    except Exception as e:
        print(f"[ERROR] get_pending_friend_requests failed: {e}")
        return []

def delete_friend(user_a: str, user_b: str) -> bool:
    """删除好友关系（无向）"""
    if user_a == user_b:
        return False
    u1, u2 = sorted([user_a, user_b])
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM friends WHERE user1 = ? AND user2 = ?",
            (u1, u2)
        )
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    except Exception as e:
        print(f"[ERROR] delete_friend failed: {e}")
        return False
# ============================================================
# 消息存储（所有消息都存 message_type）（保持不变）
# ============================================================
def save_message(sender, receiver, content, message_type):
    print(f"[LOG] save_message(sender={sender}, receiver={receiver}, type={message_type}) called")
    try:
        time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        conn = sqlite3.connect("../data/messages.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages(sender, receiver, content, timestamp, message_type, delivered)
            VALUES (?,?,?,?,?,0)
        """, (sender, receiver, content, time, message_type))
        conn.commit()
        conn.close()
        print(f"[LOG] save_message succeeded, timestamp={time}")
        return time
    except Exception as e:
        print(f"[LOG] save_message failed: {e}")
        return datetime.now().isoformat(timespec="milliseconds")

def get_offline_messages(username):
    print(f"[LOG] get_offline_messages(username={username}) called")
    try:
        conn = sqlite3.connect("../data/messages.db")
        conn.row_factory = sqlite3.Row  # ← 启用字典式访问
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, sender, receiver, content, timestamp, message_type
            FROM messages
            WHERE receiver=? AND delivered=0
            ORDER BY timestamp ASC
        """, (username,))
        rows = cursor.fetchall()
        conn.close()

        # 转为标准 dict 列表（可选，但更安全）
        msgs = [dict(row) for row in rows]
        print(f"[LOG] get_offline_messages({username}) returned {len(msgs)} messages")
        return msgs
    except Exception as e:
        print(f"[LOG] get_offline_messages({username}) failed: {e}")
        return []

def mark_messages_delivered(ids):
    print(f"[LOG] mark_messages_delivered(ids={ids}) called")
    if not ids:
        print("[LOG] mark_messages_delivered: no ids, skipped")
        return
    try:
        conn = sqlite3.connect("../data/messages.db")
        cursor = conn.cursor()
        cursor.executemany(
            "UPDATE messages SET delivered=1 WHERE id=?",
            [(i,) for i in ids]
        )
        conn.commit()
        conn.close()
        print(f"[LOG] mark_messages_delivered succeeded for {len(ids)} messages")
    except Exception as e:
        print(f"[LOG] mark_messages_delivered failed: {e}")

def get_full_history(username):
    print(f"[LOG] get_full_history(username={username}) called")
    try:
        # 1. 获取用户所属群ID
        conn_groups = sqlite3.connect("../data/groups.db")
        cursor_g = conn_groups.cursor()
        cursor_g.execute("SELECT group_id FROM group_members WHERE username = ?", (username,))
        group_ids = [row[0] for row in cursor_g.fetchall()]
        conn_groups.close()

        # 2. 查询消息
        conn_msg = sqlite3.connect("../data/messages.db")
        conn_msg.row_factory = sqlite3.Row  # ← 启用字典式访问
        cursor_m = conn_msg.cursor()

        if group_ids:
            placeholders = ','.join('?' * len(group_ids))
            query = f"""
                SELECT sender, receiver, content, timestamp, message_type
                FROM messages
                WHERE sender = ? OR receiver = ? OR receiver IN ({placeholders})
                ORDER BY timestamp ASC
            """
            params = [username, username] + group_ids
        else:
            query = """
                SELECT sender, receiver, content, timestamp, message_type
                FROM messages
                WHERE sender = ? OR receiver = ?
                ORDER BY timestamp ASC
            """
            params = [username, username]

        cursor_m.execute(query, params)
        rows = cursor_m.fetchall()
        conn_msg.close()

        # 转为标准 dict，并补充前端需要的字段
        messages = []
        for row in rows:
            msg_dict = dict(row)
            # 推断 chat_type
            if msg_dict["message_type"] == "group":
                msg_dict["chat_type"] = "group"
                msg_dict["target"] = msg_dict["receiver"]  # 群ID
            else:
                msg_dict["chat_type"] = "private"
                # 私聊 target 是对方
                if msg_dict["sender"] == username:
                    msg_dict["target"] = msg_dict["receiver"]
                else:
                    msg_dict["target"] = msg_dict["sender"]
            messages.append(msg_dict)

        print(f"[LOG] get_full_history({username}) returned {len(messages)} messages")
        return messages
    except Exception as e:
        print(f"[LOG] get_full_history({username}) failed: {e}")
        return []

# ============================================================
# 消息格式化：统一 JSON Schema（保持不变）
# ============================================================
def make_message(msg_type, sender="", receiver="", text="", timestamp="", extra=None):
    """所有消息统一格式"""
    print(f"[LOG] make_message(type={msg_type}, from={sender}, to={receiver}) called")
    data = {
        "type": msg_type,
        "from": sender,
        "to": receiver,
        "text": text,
        "timestamp": timestamp,
    }
    if extra:
        data.update(extra)
    print(f"[LOG] make_message returned dict with keys: {list(data.keys())}")
    return data

# ============================================================
# WebSocket 在线管理（增强版：支持 pending + authenticate）
# ============================================================
class ConnectionManager:
    def __init__(self):
        self._temp_id_counter = 0
        self.pending_connections: Dict[str, WebSocket] = {}
        self.active_connections: Dict[str, WebSocket] = {}
        print("[LOG] ConnectionManager.__init__ completed")

    def _gen_temp_id(self) -> str:
        self._temp_id_counter += 1
        temp_id = f"temp_{self._temp_id_counter}"
        print(f"[LOG] _gen_temp_id() generated: {temp_id}")
        return temp_id

    async def connect(self, websocket: WebSocket) -> str:
        temp_id = self._gen_temp_id()
        self.pending_connections[temp_id] = websocket
        print(f"[LOG] connect() added pending connection: {temp_id}")
        return temp_id

    def disconnect_pending(self, temp_id: str):
        removed = self.pending_connections.pop(temp_id, None)
        print(f"[LOG] disconnect_pending({temp_id}) called, removed: {removed is not None}")

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]
            update_last_online(username, datetime.now().isoformat(timespec="seconds"))
            print(f"[LOG] disconnect({username}) succeeded, now {len(self.active_connections)} online")
        else:
            print(f"[LOG] disconnect({username}) called but not active")

    def authenticate(self, temp_id: str, username: str, password: str) -> bool:
        """
        注意：这里的 `username` 实际是用户输入的「标识符」，
        可能是真实用户名，也可能是 10 位用户 ID。
        """
        print(f"[LOG] authenticate(temp_id={temp_id}, identifier={username}) called")

        # 1. 校验密码，并获取真实用户名
        success, real_username = check_login(username, password)
        if not success:
            print(f"[LOG] authenticate({username}) failed: login check failed")
            return False

        # 2. 检查是否已在线 → 踢掉旧连接（使用 real_username）
        if real_username in self.active_connections:
            old_ws = self.active_connections[real_username]
            try:
                asyncio.create_task(old_ws.close(code=4000, reason="重复登录"))
                print(f"[LOG] authenticate({real_username}): kicked existing connection")
            except Exception as e:
                print(f"[LOG] authenticate({real_username}): error kicking old connection: {e}")
            self.disconnect(real_username)

        # 3. 提升为正式用户
        ws = self.pending_connections.pop(temp_id, None)
        if ws is None:
            print(f"[LOG] authenticate({real_username}) failed: temp_id {temp_id} not found")
            return False

        self.active_connections[real_username] = ws
        update_last_online(real_username, None)
        print(f"[LOG] authenticate({real_username}) succeeded, now {len(self.active_connections)} online")
        return True

    async def send_welcome(self, username: str):
        print(f"[LOG] send_welcome({username}) started")
        try:
            # 1. 获取离线消息
            offline_msgs = get_offline_messages(username)
            for msg in offline_msgs:
                await self.send_json(username, msg)
            if offline_msgs:
                msg_ids = [msg["message_id"] for msg in offline_msgs if "message_id" in msg]
                mark_messages_delivered(msg_ids)

            # 2. 获取完整历史（可选，你已有）
            full_history = get_full_history(username)
            for msg in full_history:
                # 确保只发送必要字段，避免泄露 id 等
                safe_msg = {
                    "type": "message",
                    "sender": msg["sender"],
                    "target": msg["target"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"],
                    "chat_type": msg["chat_type"]
                }
                await self.send_json(username, safe_msg)

            # 3. 【关键新增】获取并推送用户所属群组！
            groups = get_user_groups(username)
            my_groups = [
                {"id": gid, "name": gname, "creator": creator, "created_at": created_at}
                for (gid, gname, creator, created_at) in groups
            ]
            await self.send_json(username, {"type": "my_groups", "groups": my_groups})

            # 4. 【新增】获取并推送用户的好友列表！
            friends = get_friends_list(username)  # ← 返回 ["user1", "user2", ...]
            await self.send_json(username, {
                "type": "my_friends",
                "friends": friends
            })
            
            # 5.【新增】推送所有未处理的好友请求
            pending_requesters = get_pending_friend_requests(username)
            for requester in pending_requesters:
                await self.send_json(username, {
                    "type": "friend_request",
                    "from": requester,
                    "text": f"{requester} 请求与你成为好友",
                    "options": ["Y", "N"],
                    "timestamp": datetime.now().isoformat()
                })
            
            # 6. 广播上线通知（使用已有的 broadcast）
            system_msg = {
                "type": "system",
                "event": "user_online",
                "username": username,
                "text": f"{username} 上线了"
            }
            await self.broadcast(system_msg, exclude=username)

            # === 新增：推送当前所有在线用户 ===
            online_usernames = list(manager.active_connections.keys())
            await self.send_json(username, {
                "type": "online_users",
                "users": online_usernames,
                "usernames": online_usernames
            })
            
            print(f"[LOG] send_welcome({username}) completed successfully")
        except Exception as e:
            print(f"[ERROR] send_welcome({username}) failed: {e}")

    async def send_json(self, username: str, data: dict):
        print(f"[LOG] send_json(to={username}, type={data.get('type')}) called")
        ws = self.active_connections.get(username)
        if ws:
            try:
                await ws.send_text(json.dumps(data, ensure_ascii=False))
                print(f"[LOG] send_json to {username} succeeded")
            except Exception as e:
                print(f"[LOG] send_json to {username} failed: {e}")
                self.disconnect(username)
        else:
            print(f"[LOG] send_json failed: {username} not in active_connections")

    async def broadcast_to_group(self, group_id: str, data: dict, exclude: str = None):
        print(f"[LOG] broadcast_to_group(group={group_id}, type={data.get('type')}, exclude={exclude}) called")
        try:
            # 从 groups.db 获取群成员
            conn = sqlite3.connect("../data/groups.db")  # ← 关键修改
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM group_members WHERE group_id = ?", (group_id,))
            members = [row[0] for row in cursor.fetchall()]
            conn.close()

            msg_str = json.dumps(data, ensure_ascii=False)
            dead_users = []
            for username in members:
                if username == exclude:
                    continue
                ws = self.active_connections.get(username)
                if ws:
                    try:
                        await ws.send_text(msg_str)
                    except Exception as e:
                        print(f"[LOG] broadcast_to_group to {username} failed: {e}")
                        dead_users.append(username)
            for u in dead_users:
                self.disconnect(u)
            print(f"[LOG] broadcast_to_group completed to {len(members) - len(dead_users)} users")
        except Exception as e:
            print(f"[LOG] broadcast_to_group error: {e}")
    
    async def broadcast(self, data: dict, exclude: str = None):
        print(f"[LOG] broadcast(type={data.get('type')}, exclude={exclude}) called, current online: {list(self.active_connections.keys())}")
        msg_str = json.dumps(data, ensure_ascii=False)
        dead_users = []
        for u, ws in list(self.active_connections.items()):
            if u == exclude:
                continue
            try:
                await ws.send_text(msg_str)
            except Exception as e:
                print(f"[LOG] broadcast to {u} failed: {e}")
                dead_users.append(u)
        # Clean up dead connections
        for u in dead_users:
            self.disconnect(u)
        print(f"[LOG] broadcast completed, cleaned up {len(dead_users)} dead connections")

manager = ConnectionManager()

# ============================================================
# HTTP API（保持不变）
# ============================================================
@app.post("/register")
async def api_register(req: Request):
    print("[LOG] HTTP POST /register received")
    try:
        data = await req.json()
        username = data.get("username")
        password = data.get("password")
        ok, user_id = register_user(username, password)
        if ok:
            result = {"status": "ok", "user_id": user_id}
        else:
            result = {"status": "fail", "reason": "用户已存在"}
        print(f"[LOG] /register response: {result}")
        return result
    except Exception as e:
        print(f"[LOG] /register error: {e}")
        return {"status": "fail", "reason": "请求解析失败"}

@app.post("/login")
async def api_login(req: Request):
    try:
        data = await req.json()
        identifier = data.get("username")
        password = data.get("password")
        ok, real_username = check_login(identifier, password)
        if ok:
            # 查询 user_id 和 群列表
            conn = sqlite3.connect("../data/users.db")
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (real_username,))
            row = cursor.fetchone()
            user_id = row[0] if row else ""
            conn.close()

            # 获取用户所属群组（调用已有函数）
            groups = get_user_groups(real_username)  # 返回 [(group_id, group_name), ...]

            # 转换为字典列表
            my_groups = [
                {"id": gid, "name": gname, "creator": creator, "created_at": created_at}
                for (gid, gname, creator, created_at) in groups
            ]

            return {
                "status": "ok",
                "username": real_username,
                "user_id": user_id,
                "my_groups": my_groups  # ← 【新增】登录即返回群列表！
            }
        else:
            return {"status": "fail", "reason": "用户名或密码错误"}
    except Exception as e:
        print(f"[LOG] /login error: {e}")
        return {"status": "fail", "reason": "请求解析失败"}

@app.get("/all_users")
async def get_all_users():
    try:
        conn = sqlite3.connect("../data/users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT username, user_id, last_online FROM users ORDER BY username")
        rows = cursor.fetchall()
        conn.close()
        users = [
            {"username": row[0], "user_id": row[1], "last_online": row[2]}
            for row in rows
        ]
        return {"status": "ok", "users": users}
    except Exception as e:
        return {"status": "fail", "reason": str(e)}

# ============================================================
# WebSocket：统一入口 /ws（无路径参数！）
# ============================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("[LOG] WebSocket /ws connection attempt")
    await websocket.accept()
    temp_id = await manager.connect(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                print(f"[LOG] Invalid JSON from {temp_id}: {text[:50]}...")
                continue
            msg_type = msg.get("type")
            if msg_type == "login":
                username = msg.get("username")
                password = msg.get("password")
                print(f"[LOG] Login attempt from {temp_id}: username={username}")
                if not username or not password:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "text": "缺少 username 或 password"
                    }))
                    continue
                if manager.authenticate(temp_id, username, password):
                    # 获取真实用户名（你需要从 authenticate 返回它，或重新查一次）
                    success, real_username = check_login(username, password)
                    if success:
                        # 👇 新增：通知客户端真实用户名
                        await websocket.send_text(json.dumps({
                            "type": "auth_success",
                            "username": real_username
                        }))
                        # 进入消息循环
                        await authenticated_message_loop(websocket, real_username)
                        return
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "text": "用户名或密码错误"
                    }))
                    print(f"[LOG] Authentication failed for {username}")
                    return
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "text": "请先发送 login 消息完成认证"
                }))
                print(f"[LOG] Non-login message from unauthenticated {temp_id}: {msg_type}")
    except WebSocketDisconnect:
        manager.disconnect_pending(temp_id)
        print(f"[LOG] WebSocket {temp_id} disconnected")

# ✅ 认证后的消息处理循环（私聊/群聊/心跳）
async def authenticated_message_loop(websocket: WebSocket, username: str):
    print(f"[LOG] authenticated_message_loop started for {username}")
    try:
        await manager.send_welcome(username)
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                print(f"[LOG] Invalid JSON from {username}: {text[:50]}...")
                continue
            msg_type = msg.get("type")
            content = msg.get("text")

            if msg_type == "private":
                target = msg.get("to")
                content = msg.get("text")
                if not target or not content:
                    print(f"[LOG] Invalid private message from {username}")
                    continue

                # 保存消息（用于离线/历史）
                ts = save_message(username, target, content, "private")
                packet = make_message("private", username, target, content, ts)

                # 发送给目标用户（如果在线）
                if target in manager.active_connections:
                    await manager.send_json(target, packet)
                    print(f"[LOG] Private message sent to {target}")
                else:
                    print(f"[LOG] {target} is offline; message stored")
            
            elif msg_type == "group":
                target_group = msg.get("to")  # 如 "G123456789"
                content = msg.get("text")
                if not target_group or not target_group.startswith("G") or not content:
                    print(f"[LOG] Invalid group message from {username}")
                    continue
                # 保存消息（receiver 为群ID）
                ts = save_message(username, target_group, content, "group")
                packet = make_message("group", username, target_group, content, ts)
                # 广播给该群成员
                await manager.broadcast_to_group(target_group, packet, exclude=username)
                print(f"[LOG] Group message from {username} to {target_group} broadcasted")
            
            # ===== 新增：创建群组 =====
            elif msg_type == "create_group":
                group_name = msg.get("group_name", "").strip()
                if not group_name:
                    await websocket.send_text(json.dumps({"type": "error", "text": "群名称不能为空"}))
                    continue
                ok, gid = create_group(username, group_name)
                if ok:
                    await websocket.send_text(json.dumps({
                        "type": "group_created",
                        "group_id": gid,
                        "group_name": group_name  # ← 【新增】返回群名！
                    }))
                    print(f"[LOG] Group {gid} created by {username}")
                else:
                    await websocket.send_text(json.dumps({"type": "error", "text": "创建群组失败"}))

            # ===== 新增：加入群组 =====
            elif msg_type == "join_group":
                group_id = msg.get("group_id", "").strip()
                if not group_id or not group_id.startswith("G"):
                    await websocket.send_text(json.dumps({"type": "error", "text": "无效群ID"}))
                    continue

                # 【新增】先获取群名
                conn = sqlite3.connect("../data/groups.db")
                cursor = conn.cursor()
                cursor.execute("SELECT group_name FROM groups WHERE group_id = ?", (group_id,))
                row = cursor.fetchone()
                conn.close()

                if not row:
                    await websocket.send_text(json.dumps({"type": "error", "text": "群不存在"}))
                    continue

                group_name = row[0]

                if join_group(username, group_id):
                    await websocket.send_text(json.dumps({
                        "type": "group_joined",
                        "group_id": group_id,
                        "group_name": group_name  # ←【关键】返回群名！
                    }))
                    print(f"[LOG] {username} joined group {group_id} ({group_name})")
                else:
                    await websocket.send_text(json.dumps({"type": "error", "text": "加入群组失败（可能已加入）"}))
        
            # ===== 新增：退出群组 =====
            elif msg_type == "leave_group":
                group_id = msg.get("group_id", "").strip()
                if leave_group(username, group_id):
                    await websocket.send_text(json.dumps({
                        "type": "group_left",
                        "group_id": group_id
                    }))
                    print(f"[LOG] {username} left group {group_id}")
                else:
                    await websocket.send_text(json.dumps({"type": "error", "text": "退出群组失败"}))
            
            elif msg_type == "add_friend":
                target = msg.get("to", "").strip()
                if not target:
                    await websocket.send_text(json.dumps({"type": "error", "text": "目标用户不能为空"}))
                    continue

                if target == username:
                    await websocket.send_text(json.dumps({"type": "error", "text": "不能添加自己为好友"}))
                    continue

                if not user_exists(target):
                    await websocket.send_text(json.dumps({"type": "error", "text": "用户不存在"}))
                    continue

                # 检查是否已是好友
                if are_friends(username, target):
                    await websocket.send_text(json.dumps({"type": "error", "text": "你们已经是好友"}))
                    continue

                # 检查是否已发送过请求
                if has_pending_request(username, target):
                    await websocket.send_text(json.dumps({"type": "error", "text": "已发送过好友请求，请等待对方处理"}))
                    continue

                # 创建请求
                if create_friend_request(username, target):
                    # 通知请求方
                    await websocket.send_text(json.dumps({
                        "type": "system",
                        "text": f"好友请求已发送给 {target}"
                    }))
                    
                    # ===== 新增调试代码 =====
                    print(f"[PUSH DEBUG] 尝试向 '{target}' 推送 friend_request")
                    print(f"[PUSH DEBUG] 当前在线用户: {list(manager.active_connections.keys())}")
                    print(f"[PUSH DEBUG] '{target}' 是否在线: {target in manager.active_connections}")

                    # 通知接收方（关键！）
                    request_msg = {
                        "type": "friend_request",
                        "from": username,
                        "text": f"{username} 请求与你成为好友",
                        "options": ["Y", "N"],
                        "timestamp": datetime.now().isoformat()
                    }
                    await manager.send_json(target, request_msg)
                    print(f"[LOG] Friend request: {username} → {target}")
                else:
                    await websocket.send_text(json.dumps({"type": "error", "text": "发送好友请求失败"}))

            elif msg_type == "accept_friend":
                requester = msg.get("from", "").strip()
                if not requester:
                    print("[WARN] accept_friend missing 'from'")
                    continue

                if accept_friend_request(requester, username):
                    # 通知双方
                    success_text = f"你和 {requester} 现在是好友了！"
                    await manager.send_json(username, {"type": "system", "text": success_text})
                    await manager.send_json(requester, {"type": "system", "text": success_text})

                    # 推送更新后的好友列表
                    for user in [username, requester]:
                        friends = get_friends_list(user)
                        await manager.send_json(user, {
                            "type": "my_friends",
                            "friends": friends
                        })
                    print(f"[LOG] Friend accepted: {requester} ↔ {username}")
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "text": "无效或已过期的好友请求"
                    }))

            # ===== 新增：删除好友 =====
            elif msg_type == "delete_friend":
                target = msg.get("to", "").strip()
                if not target:
                    print("[WARN] delete_friend missing 'to'")
                    continue
                if delete_friend(username, target):
                    # 通知双方
                    success_text = f"你和 {target} 已解除好友关系"
                    await manager.send_json(username, {"type": "system", "text": success_text})
                    await manager.send_json(target, {"type": "system", "text": success_text})
                    # 推送更新后的好友列表
                    for user in [username, target]:
                        friends = get_friends_list(user)
                        await manager.send_json(user, {
                            "type": "my_friends",
                            "friends": friends
                        })
                    print(f"[LOG] Friend deleted: {username} ↔ {target}")
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "text": "删除好友失败（可能不是好友）"
                    }))
            
            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                print(f"[LOG] Ping from {username} replied")
            
            else:
                print(f"[LOG] Unknown message type from {username}: {msg_type}")
            
    except WebSocketDisconnect:
        manager.disconnect(username)
        await manager.broadcast(make_message(
            msg_type="system",
            text=f"{username} 下线了",
            extra={"event": "user_leave", "username": username}
        ))
        print(f"[LOG] authenticated_message_loop ended for {username} due to disconnect")

# ============================================================
# 服务器启动入口
# ============================================================
if __name__ == "__main__":
    import uvicorn
    HOST = "0.0.0.0"
    PORT = 12345
    print("============================================")
    print(f"🚀 FastAPI 聊天服务器已启动（增强认证版 + 全日志）")
    print(f"🔌 正在监听端口: {PORT}")
    print(f"🌐 WebSocket URL: ws://<服务器IP>:{PORT}/ws")
    print("✅ 客户端连接后，请立即发送：")
    print(' {"type":"login","username":"xxx","password":"yyy"}')
    print("============================================")
    uvicorn.run("server:app", host=HOST, port=PORT, reload=False)