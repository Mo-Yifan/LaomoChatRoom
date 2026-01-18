# services/auth_service.py

import asyncio
from typing import Tuple, Optional
from models.user import check_login


async def authenticate_user(
    identifier: str, 
    password: str, 
    current_online_users: set,
    kick_existing_connection_callback
) -> Tuple[bool, Optional[str]]:
    """
    执行用户认证的核心业务逻辑。
    
    Args:
        identifier (str): 用户输入的标识符，可以是 username 或 user_id。
        password (str): 用户密码。
        current_online_users (set): 当前在线用户的集合（真实用户名）。
        kick_existing_connection_callback (callable): 一个异步回调函数，
            用于踢掉已存在的连接。其签名为 async func(username: str) -> None。

    Returns:
        Tuple[bool, Optional[str]]: (认证是否成功, 真实用户名或None)
    """
    print(f"[LOG] authenticate_user(identifier={identifier}) called")
    
    # 1. 校验密码，并获取真实用户名
    success, real_username = check_login(identifier, password)
    if not success:
        print(f"[LOG] authenticate_user({identifier}) failed: login check failed")
        return False, None

    # 2. 检查是否已在线 → 触发踢人逻辑（使用 real_username）
    if real_username in current_online_users:
        print(f"[LOG] authenticate_user({real_username}): kicking existing connection")
        # 注意：这里只触发踢人动作，不直接操作 manager
        # 具体的 WebSocket 关闭由回调函数在 ConnectionManager 上下文中执行
        await kick_existing_connection_callback(real_username)

    print(f"[LOG] authenticate_user({real_username}) succeeded")
    return True, real_username