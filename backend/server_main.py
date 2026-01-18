# server_main.py

import os
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 导入配置
from core.config import HOST, PORT, RELOAD
from core.logger import logger

# 导入数据集初始化函数
from core.database import init_db
from core.database import get_db_connection

# 导入 API 路由
from api.auth_routes import router as auth_router
from api.user_routes import router as user_router
# 如果有其他 API 路由（如 group_routes, friend_routes），也在这里导入并挂载

# 导入 WebSocket 处理器
# 注意：WebSocket 路由通常直接在主 app 上定义，或通过一个包含 WebSocket 路由的子路由器
# 根据之前的 websocket_handler.py 设计，我们假设它导出了一个处理单个连接的协程函数 websocket_endpoint
from ws.websocket_handler import websocket_endpoint

# 创建 FastAPI 应用实例
app = FastAPI()

# 挂载 web 目录（注意路径）
if os.path.exists("../web"):
    app.mount("/web", StaticFiles(directory="../web"), name="web")

# 配置 CORS（与原始 server.py 一致）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 API 路由
app.include_router(auth_router)
app.include_router(user_router)
# app.include_router(group_router) # 示例
# app.include_router(friend_router) # 示例

# 挂载 WebSocket 路由
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket_endpoint(websocket)  # 调用处理函数

@app.get("/")
async def root():
    """根路径健康检查"""
    return {"status": "ok", "message": "Chat Server is running"}

if __name__ == "__main__":
    # 建立连接
    get_db_connection("users")
    get_db_connection("messages")
    get_db_connection("groups")
    get_db_connection("friends")
    # 初始化数据库
    init_db()
    logger.info("Starting Chat Server...")
    logger.info(f"Listening on {HOST}:{PORT}")
    uvicorn.run("server_main:app", host=HOST, port=PORT, reload=RELOAD)