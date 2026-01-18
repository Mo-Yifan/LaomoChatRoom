# api/auth_routes.py

from fastapi import APIRouter, Request
from models.user import register_user, check_login
from models.group import get_user_groups # 用于登录后返回群列表
from models.friend import get_friends_list

router = APIRouter()

@router.post("/register")
async def api_register(req: Request):
    print("[LOG] HTTP POST /register received")
    try:
        data = await req.json()
        username = data.get("username")
        password = data.get("password")
        ok, user_id = register_user(username, password)
        if ok:
            result = {"status": "ok", "user_id": user_id}
        else:
            result = {"status": "fail", "reason": "用户已存在"}
        print(f"[LOG] /register response: {result}")
        return result
    except Exception as e:
        print(f"[LOG] /register error: {e}")
        return {"status": "fail", "reason": "请求解析失败"}

@router.post("/login")
async def api_login(req: Request):
    try:
        data = await req.json()
        identifier = data.get("username")
        password = data.get("password")
        ok, real_username = check_login(identifier, password)
        if ok:
            # 查询 user_id
            from models.user import get_db_connection as get_user_db
            conn = get_user_db("users")
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (real_username,))
            row = cursor.fetchone()
            user_id = row[0] if row else ""
            conn.close()
            friends = get_friends_list(real_username)  # 获取好友列表
            my_friends = [{"username": fname} for fname in friends]
            # 获取用户所属群组（调用已有函数）
            groups = get_user_groups(real_username)  # 返回 [(group_id, group_name), ...]
            # 转换为字典列表
            my_groups = [
                {"id": gid, "name": gname, "creator": creator, "created_at": created_at}
                for (gid, gname, creator, created_at) in groups
            ]
            return {
                "status": "ok",
                "username": real_username,
                "user_id": user_id,
                "my_groups": my_groups,  # ← 【新增】登录即返回群列表！
                "my_friends": my_friends
            }
        else:
            return {"status": "fail", "reason": "用户名或密码错误"}
    except Exception as e:
        print(f"[LOG] /login error: {e}")
        return {"status": "fail", "reason": "请求解析失败"}