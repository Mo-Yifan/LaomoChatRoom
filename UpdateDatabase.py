import sqlite3
import os
import sys

def migrate_messages():
    # 检查 users.db 是否存在
    if not os.path.exists("users.db"):
        print("❌ users.db 不存在，无法迁移消息。")
        return

    # 检查是否已有 messages.db（避免覆盖）
    if os.path.exists("messages.db"):
        print("⚠️  messages.db 已存在。为安全起见，请先备份或删除它再运行迁移。")
        response = input("是否继续覆盖？(y/N): ").strip().lower()
        if response != 'y':
            print("迁移已取消。")
            return
        else:
            os.remove("messages.db")
            print("✅ 已删除旧的 messages.db")

    # 连接旧数据库（只读模式更安全）
    try:
        old_conn = sqlite3.connect("users.db", uri=True)
        old_cursor = old_conn.cursor()

        # 检查 messages 表是否存在
        old_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='messages'
        """)
        if not old_cursor.fetchone():
            print("ℹ️  users.db 中没有 messages 表，无需迁移。")
            old_conn.close()
            return

        print("🔍 发现 messages 表，开始迁移...")

        # 创建新数据库和表结构
        new_conn = sqlite3.connect("messages.db")
        new_cursor = new_conn.cursor()

        # 复用你 server.py 中的建表语句（确保字段一致）
        new_cursor.execute("""
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

        # 从旧表读取所有数据
        old_cursor.execute("SELECT * FROM messages")
        rows = old_cursor.fetchall()

        if not rows:
            print("ℹ️  messages 表为空，无数据可迁移。")
        else:
            # 获取列名（兼容不同字段顺序）
            old_cursor.execute("PRAGMA table_info(messages)")
            columns = [info[1] for info in old_cursor.fetchall()]
            print(f"📊 旧表字段: {columns}")
            print(f"📤 共找到 {len(rows)} 条消息，正在迁移...")

            # 插入到新表
            # 注意：如果旧表没有 delivered 字段，我们默认设为 0
            insert_sql = """
                INSERT INTO messages(sender, receiver, content, timestamp, message_type, delivered)
                VALUES (?, ?, ?, ?, ?, ?)
            """

            migrated = 0
            for row in rows:
                row_dict = dict(zip(columns, row))

                # 提取必要字段，缺失则设默认值
                sender = row_dict.get('sender', '')
                receiver = row_dict.get('receiver', '__GROUP__')
                content = row_dict.get('content', '')
                timestamp = row_dict.get('timestamp', '')
                msg_type = row_dict.get('message_type', 'group')
                delivered = row_dict.get('delivered', 0)

                if not sender or not content or not timestamp:
                    print(f"⚠️  跳过无效消息: {row}")
                    continue

                new_cursor.execute(insert_sql, (sender, receiver, content, timestamp, msg_type, delivered))
                migrated += 1

            new_conn.commit()
            print(f"✅ 成功迁移 {migrated} 条消息到 messages.db")

        new_conn.close()
        old_conn.close()

    except Exception as e:
        print(f"💥 迁移过程中出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("=== 老莫聊天室 - 消息数据库迁移工具 ===")
    migrate_messages()
    print("🔚 迁移完成。请启动服务器前确认 server.py 已适配双库结构。")