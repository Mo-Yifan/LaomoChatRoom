# models/friend.py

import sqlite3
from datetime import datetime
from core.database import get_db_connection


def add_friend(user_a: str, user_b: str) -> bool:
    """添加好友关系（无向）"""
    if user_a == user_b:
        return False
    # 确保 user1 < user2，保证唯一存储
    u1, u2 = sorted([user_a, user_b])
    try:
        conn = get_db_connection("users")
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
        conn = get_db_connection("users")
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM friends WHERE user1 = ? AND user2 = ?", (u1, u2))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        return False


def get_friends_list(username: str) -> list:
    """获取某用户的所有好友列表"""
    print(f"[LOG] get_friends_list(username={username}) called")
    try:
        conn = get_db_connection("users")
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
    print(f" sender = {repr(sender)}")
    print(f" receiver = {repr(receiver)}")
    print(f" sender == receiver? {sender == receiver}")
    try:
        conn = get_db_connection("users")
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
        conn = get_db_connection("users")
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
        conn = get_db_connection("users")
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
        conn = get_db_connection("users")
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
        conn = get_db_connection("users")
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