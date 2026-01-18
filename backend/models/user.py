# models/user.py

import sqlite3
from datetime import datetime
from core.database import get_db_connection


def user_exists(username: str) -> bool:
    """检查用户是否存在"""
    try:
        conn = get_db_connection("users")
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"[ERROR] user_exists failed: {e}")
        return False


def register_user(username: str, password: str) -> tuple[bool, str]:
    # 返回 (成功, user_id)
    print(f"[LOG] register_user(username={username}) called")
    try:
        conn = get_db_connection("users")
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

    # === 新增调试 ===
    print(f"[DEBUG] Raw inputs → identifier: {repr(identifier)}, password: {repr(password)}")
    # =================

    try:
        conn = get_db_connection("users")
        cursor = conn.cursor()

        # === 打印将要执行的 SQL 和参数 ===
        query = "SELECT username FROM users WHERE (username = ? OR user_id = ?) AND password = ?"
        params = (identifier, identifier, password)
        print(f"[DEBUG] Executing SQL: {query}")
        print(f"[DEBUG] With params: {params}")
        # ==================================

        cursor.execute("SELECT username, user_id, password FROM users;")
        rows = cursor.fetchall()
        print(f"[DEBUG] All rows in Python: {rows}")
        for row in rows:
            print(f"  -> username={repr(row[0])}, user_id={repr(row[1])}, password={repr(row[2])}")
        
        # 尝试按 username 或 user_id 查
        cursor.execute(
            "SELECT username FROM users WHERE (username = ? OR user_id = ?) AND password = ?",
            (identifier, identifier, password)
        )
        result = cursor.fetchone()

        # === 打印查询结果 ===
        print(f"[DEBUG] SQL result: {result}")
        # ====================

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
        conn = get_db_connection("users")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_online=? WHERE username=?",
            (time, username)
        )
        conn.commit()
        conn.close()
        print(f"[LOG] update_last_online({username}) succeeded")
    except Exception as e:
        print(f"[LOG] update_last_online({username}) failed: {e}")


def get_all_users():
    """获取所有用户信息（供 HTTP API 使用）"""
    try:
        conn = get_db_connection("users")
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
# 生成唯一用户 ID 的辅助函数
# 注意：此函数依赖于传入的 cursor 对象，因此保留在 user 模型内
# ============================================================
def generate_unique_user_id(cursor, max_attempts=100):
    """生成 10 位唯一数字 ID"""
    import random
    for _ in range(max_attempts):
        # 生成 10 位数字字符串（允许前导0）
        candidate = f"{random.randint(0, 9999999999):010d}"
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (candidate,))
        if cursor.fetchone() is None:
            return candidate
    raise RuntimeError("无法生成唯一用户ID（尝试次数过多）")