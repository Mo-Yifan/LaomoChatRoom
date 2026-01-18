# ws/websocket_handler.py

import json
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect, FastAPI

# 创建 FastAPI 应用实例（修复 "未定义 'app'" 错误）
app = FastAPI()

# 导入全局 WebSocket 管理器
from services.websocket_manager import manager

# 导入模型层函数
from models.user import user_exists, check_login
from models.group import create_group, join_group, leave_group
from models.friend import are_friends, has_pending_request, create_friend_request, accept_friend_request, delete_friend
from models.message import save_message

# 导入工具函数
from utils.helpers import make_message

async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 统一入口点，与原始 server.py 完全一致。"""
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

                if await manager.authenticate(temp_id, username, password):
                    # 获取真实用户名
                    success, real_username = check_login(username, password)
                    if success:
                        # 通知客户端真实用户名
                        await websocket.send_text(json.dumps({
                            "type": "auth_success",
                            "username": real_username
                        }))
                        # 进入认证后的消息循环
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


async def authenticated_message_loop(websocket: WebSocket, username: str):
    """认证成功后的主消息处理循环，与原始 server.py 完全一致。"""
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
                from models.group import get_db_connection as get_group_db
                conn = get_group_db("groups")
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
                    from models.friend import get_friends_list
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
                    from models.friend import get_friends_list
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