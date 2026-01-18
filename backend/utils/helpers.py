# utils/helpers.py

import random
import json
from datetime import datetime
from typing import Optional, Dict, Any

def generate_unique_user_id(cursor, max_attempts=100):
    """生成 10 位唯一数字 ID"""
    for _ in range(max_attempts):
        # 生成 10 位数字字符串（允许前导0）
        candidate = f"{random.randint(0, 9999999999):010d}"
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (candidate,))
        if cursor.fetchone() is None:
            return candidate
    raise RuntimeError("无法生成唯一用户ID（尝试次数过多）")


def generate_unique_group_id(cursor, max_attempts=100):
    """生成 10 位唯一群 ID，格式为 G + 9 位数字（如 G123456789）"""
    for _ in range(max_attempts):
        candidate = "G" + f"{random.randint(0, 999999999):09d}"
        cursor.execute("SELECT 1 FROM groups WHERE group_id = ?", (candidate,))
        if cursor.fetchone() is None:
            return candidate
    raise RuntimeError("无法生成唯一群ID（尝试次数过多）")


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