# models/message.py

import sqlite3
from datetime import datetime
from core.database import get_db_connection


def save_message(sender, receiver, content, message_type):
    print(f"[LOG] save_message(sender={sender}, receiver={receiver}, type={message_type}) called")
    try:
        time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        conn = get_db_connection("messages")
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
        conn = get_db_connection("messages")
        conn.row_factory = sqlite3.Row  # ← 启用字典式访问，与原始 server.py 一致
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, sender, receiver, content, timestamp, message_type
            FROM messages
            WHERE receiver=? AND delivered=0
            ORDER BY timestamp ASC
        """, (username,))
        rows = cursor.fetchall()
        conn.close()
        # 转为标准 dict 列表（可选，但更安全），与原始 server.py 一致
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
        conn = get_db_connection("messages")
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
        conn_groups = get_db_connection("groups")
        cursor_g = conn_groups.cursor()
        cursor_g.execute("SELECT group_id FROM group_members WHERE username = ?", (username,))
        group_ids = [row[0] for row in cursor_g.fetchall()]
        conn_groups.close()

        # 2. 查询消息
        conn_msg = get_db_connection("messages")
        conn_msg.row_factory = sqlite3.Row  # ← 启用字典式访问，与原始 server.py 一致
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

        # 转为标准 dict，并补充前端需要的字段，与原始 server.py 一致
        messages = []
        for row in rows:
            msg_dict = dict(row)
            # 推断 chat_type
            if msg_dict["message_type"] == "group":
                msg_dict["chat_type"] = "group"
                msg_dict["target"] = msg_dict["receiver"]  # 群ID
            else:
                msg_dict["chat_type"] = "private"  # 私聊 target 是对方
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