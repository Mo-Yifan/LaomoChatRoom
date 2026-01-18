# services/websocket_manager.py

import json
import asyncio
from datetime import datetime
from typing import Dict, Optional, Callable, Awaitable
from fastapi import WebSocket

# 导入模型层函数
from models.user import update_last_online
from models.friend import get_pending_friend_requests, get_friends_list
from models.group import get_user_groups
from models.message import get_offline_messages, get_full_history, mark_messages_delivered

# 导入服务层函数
from services.auth_service import authenticate_user


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

    async def authenticate(self, temp_id: str, identifier: str, password: str) -> bool:
        """
        认证一个临时连接，并将其提升为活跃的已认证连接。
        """
        # 定义踢人回调，用于 auth_service
        async def kick_callback(username: str):
            old_ws = self.active_connections[username]
            try:
                asyncio.create_task(old_ws.close(code=4000, reason="重复登录"))
                print(f"[LOG] authenticate({username}): kicked existing connection")
            except Exception as e:
                print(f"[LOG] authenticate({username}): error kicking old connection: {e}")
            self.disconnect(username)

        # 调用认证服务
        success, real_username = await authenticate_user(
            identifier=identifier,
            password=password,
            current_online_users=set(self.active_connections.keys()),
            kick_existing_connection_callback=kick_callback
        )

        if not success:
            return False

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
                msg_ids = [msg["id"] for msg in offline_msgs if "id" in msg]  # 注意：原始代码此处有bug，应为"id"
                mark_messages_delivered(msg_ids)

            # 2. 获取完整历史
            full_history = get_full_history(username)
            for msg in full_history:
                safe_msg = {
                    "type": "message",
                    "sender": msg["sender"],
                    "target": msg["target"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"],
                    "chat_type": msg["chat_type"]
                }
                await self.send_json(username, safe_msg)

            # 3. 获取并推送用户所属群组！
            groups = get_user_groups(username)
            my_groups = [
                {"id": gid, "name": gname, "creator": creator, "created_at": created_at}
                for (gid, gname, creator, created_at) in groups
            ]
            await self.send_json(username, {"type": "my_groups", "groups": my_groups})

            # 4. 获取并推送用户的好友列表！
            friends = get_friends_list(username)
            await self.send_json(username, {"type": "my_friends", "friends": friends})

            # 5. 推送所有未处理的好友请求
            pending_requesters = get_pending_friend_requests(username)
            for requester in pending_requesters:
                await self.send_json(username, {
                    "type": "friend_request",
                    "from": requester,
                    "text": f"{requester} 请求与你成为好友",
                    "options": ["Y", "N"],
                    "timestamp": datetime.now().isoformat()
                })

            # 6. 广播上线通知
            system_msg = {
                "type": "system",
                "event": "user_online",
                "username": username,
                "text": f"{username} 上线了"
            }
            await self.broadcast(system_msg, exclude=username)

            # 7. 推送当前所有在线用户
            online_usernames = list(self.active_connections.keys())
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
        from models.group import get_db_connection as get_group_db
        print(f"[LOG] broadcast_to_group(group={group_id}, type={data.get('type')}, exclude={exclude}) called")
        try:
            # 从 groups.db 获取群成员
            conn = get_group_db("groups")
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


# 创建全局管理器实例
manager = ConnectionManager()