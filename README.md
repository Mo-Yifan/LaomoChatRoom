# 老莫聊天室（MoChat）v5.0

> **全平台融合 · 实时协同 · 体验无界**  
> —— 从桌面走向 Web，构建统一通信生态

---

## 📖 简介

老莫聊天室 v5.0 是一次**架构与体验的双重飞跃**。在 v4.0 成熟的群组与身份系统基础上，我们引入了 **Web 前端支持**，实现 **PyQt6 桌面客户端 + 浏览器 Web 客户端** 的双端并行架构。

现在，你可以在 Windows/macOS/Linux 上使用功能丰富的桌面应用，也能在手机、平板或任意浏览器中通过 `chat.html` 快速接入同一聊天网络——**所有消息、群组、好友关系实时同步，无缝切换**。

这不仅是“多端”，更是“一体”。

---

## 🚀 核心技术特性（v5.0 新增）

### 🌐 **统一 WebSocket 服务，双前端接入**
- 后端 `server.py` 提供标准化 WebSocket 接口 `/ws`
- **桌面端**：基于 `PyQt6 + qasync + websockets`，保留高级 UI 交互
- **Web 端**：纯 HTML/JS 实现 `chat.html`，轻量、跨平台、零安装
- **同一账号**可在桌面与 Web 端同时在线，消息双向同步

### 🔌 **静态资源服务内嵌**
- FastAPI 内置挂载 `../web` 目录为 `/web`
- 访问根路径 `http://<IP>:12345` 自动重定向至 `/web/chat.html`
- 无需 Nginx 或额外 Web 服务器，开箱即用

### 💬 **消息格式全面标准化**
- 所有通信采用统一 JSON Schema：
  ```json
  {
    "type": "message|private|group|system|my_groups|...",
    "from": "发送者真实用户名",
    "to": "目标（私聊对象/群ID）",
    "text": "内容",
    "timestamp": "ISO8601 时间",
    "chat_type": "private|group"
  }
  ```
- 彻底消除 v4 及之前版本中 `group`/`private` 与 `message` 类型混用的问题
- Web 与桌面客户端解析逻辑完全一致，降低维护成本

### 👥 **完整社交图谱支持（继承并强化 v4）**
- ✅ 私聊（含在线状态）
- ✅ 群聊（创建/加入/退出/消息广播）
- ✅ 好友系统（请求/接受/删除）
- ✅ 离线消息 & 全历史漫游
- ✅ 重复登录踢人机制

### 🛠️ **开发者友好设计**
- **全链路日志**：服务端每个函数入口/出口均有 `[LOG]` 输出
- **数据库分离**：`users.db` / `messages.db` / `groups.db` 职责清晰
- **无侵入式调试**：所有日志仅用 `print`，不影响性能
- **Windows 兼容**：彻底移除 `extra_headers`，解决 asyncio 兼容性问题

---

## 🔁 与 v4.0 的关键增量对比

| 能力 | v4.0 | v5.0 |
|------|------|------|
| **前端形态** | 仅 PyQt6 桌面客户端 | **桌面 + Web 双前端** |
| **访问方式** | 需安装 Python 客户端 | **浏览器直接打开即可使用** |
| **部署复杂度** | 需分发客户端程序 | **服务端启动即提供完整 Web 界面** |
| **消息格式** | 混合 `private`/`group`/`message` | **统一 `message` 类型 + `chat_type` 字段** |
| **静态资源** | 无 | **内置 FastAPI StaticFiles 服务** |
| **跨设备体验** | 仅限桌面设备 | **手机/平板/PC 全覆盖** |

> 💡 **v5.0 不是替代 v4，而是扩展**：桌面端仍提供更丰富的交互（如群信息弹窗、用户详情），Web 端则主打轻快便捷。

---

## 📦 快速启动

### 服务端（必需）
```bash
cd server
pip install fastapi uvicorn[standard] websockets sqlite3
python -B server.py
```
启动后自动监听 `0.0.0.0:12345`，并提供：
- WebSocket 服务：`ws://<IP>:12345/ws`
- Web 页面：`http://<IP>:12345`

### 客户端（任选其一）
#### 方式一：Web 浏览器
直接访问 `http://<服务器IP>:12345`，自动加载 `chat.html`

#### 方式二：桌面客户端
```bash
cd client
pip install pyqt6 qasync aiohttp websockets
python -B main.py
```

---

## 📂 项目结构

```
NETWORKCHATROOM/
├── backend/                   # 后端服务代码
│   ├── chat_ui.py             # 聊天主界面逻辑
│   ├── client.py              # 客户端网络通信层
│   ├── login_ui.py            # 登录界面
│   ├── main.py                # 应用入口（启动服务）
│   ├── register_ui.py         # 注册界面
│   └── server.py              # WebSocket 服务器核心逻辑
├── data/                      # 数据库存放目录
│   ├── groups.db              # 群组信息数据库
│   ├── messages.db            # 消息记录数据库
│   └── users.db               # 用户账户数据库
├── logo/                      # 图标资源
│   └── logo.ico               # 应用图标
├── web/                       # Web 前端页面
│   └── chat.html              # 浏览器可访问的聊天界面
├── 版本更新说明.md            # 详细版本演进记录
└── README.md                  # 项目说明文档
```

> ✅ 所有文件均位于项目根目录下，无需额外嵌套。  
> ⚠️ 注意：`backend` 目录中的 `.py` 文件是完整的后端服务模块，`main.py` 为启动入口。

---

## 🌟 未来展望

v5.0 奠定了**统一通信平台**的基础，后续将聚焦：
- Web 端功能增强（消息气泡、时间分组、通知提醒）
- 消息搜索与过滤
- 文件/图片传输（Base64 或分片上传）
- 端到端加密（E2EE）可选模式

---

## 📜 许可证

MIT License — 自由使用、修改、分发。

---

> **作者**：MoYifan  
> **发布日期**：2025 年 12 月  
> **口号**：一处部署，处处可聊。