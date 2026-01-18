# models/group.py

import sqlite3
from datetime import datetime
import random
from core.database import get_db_connection


def create_group(creator: str, group_name: str) -> tuple[bool, str]:
    print(f"[LOG] create_group(creator={creator}, name={group_name}) called")
    try:
        conn = get_db_connection("groups")
        cursor = conn.cursor()
        
        # 【内联】生成唯一群ID的逻辑（原 generate_unique_group_id 函数）
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


def join_group(username: str, group_id: str) -> bool:
    print(f"[LOG] join_group({username}, {group_id}) called")
    try:
        # 检查群是否存在
        conn = get_db_connection("groups")
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
        return True
    except Exception as e:
        print(f"[ERROR] join_group failed: {e}")
        return False


def leave_group(username: str, group_id: str) -> bool:
    print(f"[LOG] leave_group(user={username}, group={group_id}) called")
    try:
        conn = get_db_connection("groups")
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
        conn = get_db_connection("groups")
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