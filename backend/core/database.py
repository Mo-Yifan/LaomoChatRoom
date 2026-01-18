# core/database.py

import sqlite3
import os
from datetime import datetime

def get_db_connection(db_name: str) -> sqlite3.Connection:
    """
    根据数据库名称获取 SQLite 连接。
    
    Args:
        db_name (str): 数据库名称，如 'users', 'messages', 'groups'。
        
    Returns:
        sqlite3.Connection: 对应的数据库连接对象。
    """
    # 确保 ../../data 目录存在
    data_dir = "D:\\MyProject\\NetworkChatroom\\data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    db_path = f"{data_dir}/{db_name}.db"
    # === 关键调试 ===
    print(f"[CRITICAL] Connecting to DB: {os.path.abspath(db_path)}")
    if not os.path.exists(db_path):
        print(f"[WARNING] DB file NOT FOUND at: {os.path.abspath(db_path)}")
    else:
        print(f"[INFO] DB file exists. Size: {os.path.getsize(db_path)} bytes")
    # ================
    conn = sqlite3.connect(db_path)
    return conn


def init_db():
    """
    初始化所有数据库和表结构。
    完全保留原始 server.py 中的 init_db() 函数逻辑、SQL 语句、路径和日志。
    """
    print("[LOG] init_db() called")
    try:
        # === users.db: 用户、好友、好友请求 ===
        conn = get_db_connection("users")
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

        # === messages.db: 消息存储 ===
        conn = get_db_connection("messages")
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
        conn = get_db_connection("groups")
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