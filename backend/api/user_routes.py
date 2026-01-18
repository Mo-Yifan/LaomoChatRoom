# api/user_routes.py

from fastapi import APIRouter
from models.user import get_db_connection as get_user_db

router = APIRouter()

@router.get("/all_users")
async def get_all_users():
    try:
        conn = get_user_db("users")
        cursor = conn.cursor()
        cursor.execute("SELECT username, user_id, last_online FROM users ORDER BY username")
        rows = cursor.fetchall()
        conn.close()
        users = [
            {"username": row[0], "user_id": row[1], "last_online": row[2]} for row in rows
        ]
        return {"status": "ok", "users": users}
    except Exception as e:
        return {"status": "fail", "reason": str(e)}