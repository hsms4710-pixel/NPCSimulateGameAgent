"""
NPC 模拟器后端 API 服务
基于 FastAPI 构建的 RESTful API
"""
import sys
import os
import uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import json
import logging
import platform
from collections import deque
from contextlib import asynccontextmanager

from backend.log_manager import LogManager, LogLevel
from backend.npc_service import NPCService
from backend.npc_agent import (
    NPCAgentManager, NPCAction, ActionType, NPCState,
    NPC_TOOLS, build_react_prompt, parse_react_response,
    create_action_from_tool_call, npc_agent_manager
)
from backend.world_data import (
    WorldDataManager, Job, JobStatus, Lodging, LodgingType,
    Relationship, RelationshipLevel, Transaction,
    PropagatingEvent, world_data_manager
)

# 导入世界模拟器
try:
    from world_simulator import (
        WorldManager, PlayerCharacter, PlayerAction,
        get_available_presets, WORLD_LOCATIONS,
        NPCLifecycleManager, EventType, EventSeverity
    )
    WORLD_SIMULATOR_AVAILABLE = True
except ImportError:
    WORLD_SIMULATOR_AVAILABLE = False

# 初始化日志管理器
log_manager = LogManager()
logger = log_manager.get_logger("api_server")

# NPC 服务实例
npc_service: Optional[NPCService] = None

# 世界管理器实例
world_manager: Optional['WorldManager'] = None
npc_lifecycle: Optional['NPCLifecycleManager'] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global npc_service, world_manager, npc_lifecycle
    logger.info("启动 NPC 模拟器 API 服务...")
    npc_service = NPCService(log_manager)

    # 初始化世界模拟器
    if WORLD_SIMULATOR_AVAILABLE:
        world_manager = WorldManager()
        npc_lifecycle = NPCLifecycleManager(world_manager)
        logger.info("世界模拟器已初始化")
    else:
        logger.warning("世界模拟器模块不可用")

    # 注册新路由模块（D1）
    try:
        from backend.routes.player_routes import router as player_router
        from backend.routes.event_routes import router as event_router
        from backend.routes.npc_routes import router as npc_router
        app.include_router(player_router)
        app.include_router(event_router)
        app.include_router(npc_router)
        logger.info("新路由模块已注册: player/event/npc")
    except Exception as e:
        logger.warning(f"新路由注册失败（可忽略）: {e}")

    # 初始化事件服务层
    try:
        from backend.services.event_service import init_event_services
        init_event_services()
        logger.info("事件服务层已初始化")
    except Exception as e:
        logger.warning(f"事件服务层初始化失败（可忽略）: {e}")

    yield
    logger.info("关闭 NPC 模拟器 API 服务...")
    if npc_service:
        npc_service.shutdown()


app = FastAPI(
    title="NPC 行为模拟器 API",
    description="艾伦谷 NPC 智能行为模拟系统后端 API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 获取项目根目录和前端目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

# 挂载静态文件目录
if os.path.exists(FRONTEND_DIR):
    # 挂载 CSS
    css_dir = os.path.join(FRONTEND_DIR, "css")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")

    # 挂载 JS
    js_dir = os.path.join(FRONTEND_DIR, "js")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    logger.info(f"前端目录已挂载: {FRONTEND_DIR}")
else:
    logger.warning(f"前端目录不存在: {FRONTEND_DIR}")


# ========== Pydantic 模型 ==========

class APIConfig(BaseModel):
    provider: Optional[str] = "deepseek"
    api_key: Optional[str] = None
    api_base: Optional[str] = "https://api.deepseek.com/v1"
    model: Optional[str] = "deepseek-chat"


class EventRequest(BaseModel):
    content: str
    event_type: str = "dialogue"


class DialogueRequest(BaseModel):
    message: str


class NPCSelectRequest(BaseModel):
    npc_name: str


# ========== 世界模拟器模型 ==========

class PlayerCreateRequest(BaseModel):
    """玩家创建请求"""
    preset_id: Optional[str] = None  # 预设ID
    name: str
    age: int = 25
    gender: str = "男"
    birthplace: str = "远方"
    appearance: str = ""
    # 自定义模式的额外字段
    profession: Optional[str] = None
    background: Optional[str] = None
    personality: Optional[str] = None
    skills: Optional[Dict[str, int]] = None


class PlayerActionRequest(BaseModel):
    """玩家行动请求"""
    action: str  # 社交/饮食/工作/休息/移动
    target: Optional[str] = None  # 目标NPC或地点
    details: Optional[str] = None  # 额外详情（如对话内容）


class WorldEventRequest(BaseModel):
    """世界事件请求"""
    title: str
    description: str
    location: str
    event_type: str = "自定义"
    severity: int = 3  # 1-5


class TimeAdvanceRequest(BaseModel):
    hours: float = 1.0
    update_npcs: bool = True  # 是否同时更新NPC状态


# ========== WebSocket 连接管理 ==========

class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 客户端连接，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket 客户端断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"广播消息失败: {e}")


ws_manager = ConnectionManager()


# ========== API 路由 ==========

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回前端页面"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    else:
        return HTMLResponse(
            content="""
            <html>
                <head><title>NPC 模拟器</title></head>
                <body>
                    <h1>NPC 行为模拟器 API</h1>
                    <p>前端文件未找到。请确保 frontend 目录存在。</p>
                    <p><a href="/docs">查看 API 文档</a></p>
                </body>
            </html>
            """,
            status_code=200
        )


@app.get("/api")
async def api_root():
    """API 根路径"""
    return {
        "name": "NPC 行为模拟器 API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "api": "/api/v1",
            "docs": "/docs",
            "websocket": "/ws"
        }
    }


@app.get("/favicon.ico")
async def favicon():
    """返回空 favicon 防止 404"""
    # 简单的 1x1 透明 ICO
    return Response(content=b"", media_type="image/x-icon")


@app.get("/api/v1/status")
async def get_system_status():
    """获取系统状态"""
    return {
        "status": "ok",
        "npc_initialized": npc_service.is_initialized() if npc_service else False,
        "current_npc": npc_service.get_current_npc_name() if npc_service else None,
        "server_time": datetime.now().isoformat()
    }


# ========== API 配置 ==========

@app.get("/api/v1/config")
async def get_api_config():
    """获取 API 配置（不返回完整密钥）"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    config = npc_service.get_api_config()
    # 隐藏部分密钥
    if config.get("api_key"):
        key = config["api_key"]
        config["api_key_masked"] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
        del config["api_key"]
    return config


@app.post("/api/v1/config")
async def update_api_config(config: APIConfig):
    """更新 API 配置"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    success = npc_service.update_api_config(config.dict())
    if success:
        logger.info("API 配置已更新")
        return {"status": "success", "message": "API 配置已更新"}
    else:
        raise HTTPException(status_code=400, detail="API 配置更新失败")


@app.post("/api/v1/config/test")
async def test_api_connection():
    """测试 API 连接"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    result = npc_service.test_api_connection()
    return result


# ========== NPC 管理 ==========

@app.get("/api/v1/npcs")
async def get_available_npcs():
    """获取可用的 NPC 列表"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    return {"npcs": npc_service.get_available_npcs()}


@app.post("/api/v1/npcs/select")
async def select_npc(request: NPCSelectRequest):
    """选择/切换 NPC"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    success = npc_service.select_npc(request.npc_name)
    if success:
        await ws_manager.broadcast({
            "type": "npc_changed",
            "npc_name": request.npc_name,
            "timestamp": datetime.now().isoformat()
        })
        return {"status": "success", "npc_name": request.npc_name}
    else:
        raise HTTPException(status_code=400, detail=f"无法选择 NPC: {request.npc_name}")


@app.get("/api/v1/npc/status")
async def get_npc_status():
    """获取当前 NPC 状态"""
    if not npc_service or not npc_service.is_initialized():
        raise HTTPException(status_code=503, detail="NPC 未初始化")

    return npc_service.get_npc_status()


@app.get("/api/v1/npc/memories")
async def get_npc_memories(limit: int = 20):
    """获取 NPC 记忆"""
    if not npc_service or not npc_service.is_initialized():
        raise HTTPException(status_code=503, detail="NPC 未初始化")

    return {"memories": npc_service.get_recent_memories(limit)}


@app.get("/api/v1/npc/goals")
async def get_npc_goals():
    """获取 NPC 目标"""
    if not npc_service or not npc_service.is_initialized():
        raise HTTPException(status_code=503, detail="NPC 未初始化")

    return npc_service.get_goals()


@app.get("/api/v1/npc/relationships")
async def get_npc_relationships():
    """获取 NPC 关系"""
    if not npc_service or not npc_service.is_initialized():
        raise HTTPException(status_code=503, detail="NPC 未初始化")

    return {"relationships": npc_service.get_relationships()}


# ========== 事件处理 ==========

@app.post("/api/v1/events")
async def process_event(request: EventRequest):
    """处理事件"""
    if not npc_service or not npc_service.is_initialized():
        raise HTTPException(status_code=503, detail="NPC 未初始化")

    logger.info(f"处理事件: {request.event_type} - {request.content[:50]}...")
    result = npc_service.process_event(request.content, request.event_type)

    # 广播事件处理结果
    await ws_manager.broadcast({
        "type": "event_processed",
        "event": request.dict(),
        "result": result,
        "timestamp": datetime.now().isoformat()
    })

    return result


@app.post("/api/v1/dialogue")
async def send_dialogue(request: DialogueRequest):
    """发送对话"""
    if not npc_service or not npc_service.is_initialized():
        raise HTTPException(status_code=503, detail="NPC 未初始化")

    logger.info(f"收到对话: {request.message[:50]}...")
    result = npc_service.send_dialogue(request.message)

    # 广播对话结果
    await ws_manager.broadcast({
        "type": "dialogue",
        "user_message": request.message,
        "npc_response": result.get("response", ""),
        "timestamp": datetime.now().isoformat()
    })

    return result


# ========== 时间控制 ==========

@app.get("/api/v1/time")
async def get_world_time():
    """获取世界时间"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    return npc_service.get_world_time()


@app.post("/api/v1/time/advance")
async def advance_time(request: TimeAdvanceRequest):
    """推进时间"""
    if not npc_service or not npc_service.is_initialized():
        raise HTTPException(status_code=503, detail="NPC 未初始化")

    result = npc_service.advance_time(request.hours)

    # 广播时间变化
    await ws_manager.broadcast({
        "type": "time_advanced",
        "hours": request.hours,
        "new_time": result.get("current_time"),
        "activity": result.get("activity"),
        "timestamp": datetime.now().isoformat()
    })

    return result


@app.post("/api/v1/time/pause")
async def pause_time():
    """暂停时间"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    npc_service.pause_time()
    return {"status": "paused"}


@app.post("/api/v1/time/resume")
async def resume_time():
    """恢复时间"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    npc_service.resume_time()
    return {"status": "running"}


@app.post("/api/v1/time/reset")
async def reset_time():
    """重置时间"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    npc_service.reset_time()
    return {"status": "reset", "time": npc_service.get_world_time()}


# ========== 自主模式 ==========

@app.post("/api/v1/autonomous/start")
async def start_autonomous_mode():
    """启动自主模式"""
    if not npc_service or not npc_service.is_initialized():
        raise HTTPException(status_code=503, detail="NPC 未初始化")

    npc_service.start_autonomous_mode()
    await ws_manager.broadcast({
        "type": "autonomous_mode",
        "status": "started",
        "timestamp": datetime.now().isoformat()
    })
    return {"status": "started"}


@app.post("/api/v1/autonomous/stop")
async def stop_autonomous_mode():
    """停止自主模式"""
    if not npc_service or not npc_service.is_initialized():
        raise HTTPException(status_code=503, detail="NPC 未初始化")

    npc_service.stop_autonomous_mode()
    await ws_manager.broadcast({
        "type": "autonomous_mode",
        "status": "stopped",
        "timestamp": datetime.now().isoformat()
    })
    return {"status": "stopped"}


@app.get("/api/v1/autonomous/status")
async def get_autonomous_status():
    """获取自主模式状态"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    return {"autonomous_mode": npc_service.is_autonomous_mode_active()}


# ========== 日志系统 ==========

@app.get("/api/v1/logs")
async def get_logs(
    level: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 100
):
    """获取日志"""
    logs = log_manager.get_logs(
        level=LogLevel[level.upper()] if level else None,
        source=source,
        limit=limit
    )
    return {"logs": logs}


@app.get("/api/v1/logs/model")
async def get_model_outputs(limit: int = 50):
    """获取模型输出日志"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    return {"model_outputs": npc_service.get_model_outputs(limit)}


@app.delete("/api/v1/logs")
async def clear_logs():
    """清空日志"""
    log_manager.clear_logs()
    return {"status": "cleared"}


# ========== Token 统计 ==========

@app.get("/api/v1/stats/tokens")
async def get_token_stats():
    """获取 Token 统计"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    return npc_service.get_token_stats()


@app.post("/api/v1/stats/tokens/reset")
async def reset_token_stats():
    """重置 Token 统计"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="服务未初始化")

    npc_service.reset_token_stats()
    return {"status": "reset"}


# ========== 世界模拟器 API ==========

@app.get("/api/v1/world/status")
async def get_world_status():
    """获取世界状态"""
    if not world_manager:
        raise HTTPException(status_code=503, detail="世界模拟器未初始化")

    return world_manager.get_world_state()


@app.get("/api/v1/world/locations")
async def get_world_locations():
    """获取所有地点"""
    if not world_manager:
        raise HTTPException(status_code=503, detail="世界模拟器未初始化")

    return {"locations": WORLD_LOCATIONS}


@app.get("/api/v1/player/presets")
async def get_player_presets():
    """获取玩家预设列表"""
    if not WORLD_SIMULATOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="世界模拟器不可用")

    return {"presets": get_available_presets()}


@app.post("/api/v1/player/create")
async def create_player(request: PlayerCreateRequest):
    """创建玩家角色"""
    if not world_manager:
        raise HTTPException(status_code=503, detail="世界模拟器未初始化")

    try:
        player = world_manager.create_player(
            preset_id=request.preset_id,
            custom_data=request.dict()
        )

        await ws_manager.broadcast({
            "type": "player_created",
            "player": player.to_dict(),
            "timestamp": datetime.now().isoformat()
        })

        return {
            "status": "success",
            "player": player.to_dict(),
            "location": world_manager.get_current_location_info()
        }
    except Exception as e:
        logger.error(f"创建玩家失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/player")
async def get_player():
    """获取当前玩家信息"""
    if not world_manager or not world_manager.player:
        raise HTTPException(status_code=404, detail="玩家未创建")

    return {
        "player": world_manager.player.to_dict(),
        "location": world_manager.get_current_location_info(),
        "available_actions": world_manager.get_available_actions()
    }


@app.post("/api/v1/player/action")
async def execute_player_action(request: PlayerActionRequest):
    """执行玩家行动"""
    if not world_manager or not world_manager.player:
        raise HTTPException(status_code=404, detail="玩家未创建")

    try:
        result = await world_manager.execute_player_action(
            action=request.action,
            target=request.target,
            details=request.details or ""
        )

        # 广播行动结果
        await ws_manager.broadcast({
            "type": "player_action",
            "action": request.action,
            "result": result,
            "world_time": world_manager.world_time.to_dict(),
            "timestamp": datetime.now().isoformat()
        })

        return {
            "result": result,
            "player": world_manager.player.to_dict(),
            "world_time": world_manager.world_time.to_dict(),
            "available_actions": world_manager.get_available_actions()
        }
    except Exception as e:
        logger.error(f"执行玩家行动失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/world/event")
async def trigger_world_event(request: WorldEventRequest):
    """触发世界事件"""
    if not world_manager:
        raise HTTPException(status_code=503, detail="世界模拟器未初始化")

    try:
        event = world_manager.trigger_world_event(
            title=request.title,
            description=request.description,
            location=request.location,
            event_type=request.event_type,
            severity=request.severity
        )

        # 传播事件到NPC
        if npc_lifecycle and npc_service and npc_service.is_initialized():
            responses = await npc_lifecycle.propagate_event_to_npcs(
                event.to_dict(),
                world_manager.world_time.to_datetime(),
                npc_service.npc_system if hasattr(npc_service, 'npc_system') else None
            )
        else:
            responses = {}

        # 广播事件
        await ws_manager.broadcast({
            "type": "world_event",
            "event": event.to_dict(),
            "npc_responses": responses,
            "timestamp": datetime.now().isoformat()
        })

        return {
            "status": "success",
            "event": event.to_dict(),
            "npc_responses": responses
        }
    except Exception as e:
        logger.error(f"触发世界事件失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/world/events")
async def get_world_events(limit: int = 20):
    """获取世界事件历史"""
    if not world_manager:
        raise HTTPException(status_code=503, detail="世界模拟器未初始化")

    return {
        "active_events": [e.to_dict() for e in world_manager.event_trigger.get_active_events()],
        "event_history": world_manager.event_trigger.get_event_history(limit)
    }


@app.get("/api/v1/world/npcs")
async def get_world_npcs():
    """获取所有NPC状态"""
    if not npc_lifecycle:
        raise HTTPException(status_code=503, detail="NPC生命周期管理器未初始化")

    return {"npcs": npc_lifecycle.get_all_npc_states()}


@app.post("/api/v1/world/time/advance")
async def advance_world_time(request: TimeAdvanceRequest):
    """推进世界时间"""
    if not world_manager:
        raise HTTPException(status_code=503, detail="世界模拟器未初始化")

    minutes = int(request.hours * 60)
    world_manager.advance_time(minutes)

    npc_updates = []
    if request.update_npcs and npc_lifecycle:
        npc_updates = npc_lifecycle.update_all_npcs_for_time(world_manager.world_time.hour)

    # 广播时间变化
    await ws_manager.broadcast({
        "type": "world_time_advanced",
        "world_time": world_manager.world_time.to_dict(),
        "npc_updates": npc_updates,
        "timestamp": datetime.now().isoformat()
    })

    return {
        "world_time": world_manager.world_time.to_dict(),
        "player": world_manager.player.to_dict() if world_manager.player else None,
        "npc_updates": npc_updates
    }


@app.get("/api/v1/world/logs")
async def get_world_logs(limit: int = 50):
    """获取交互日志"""
    if not world_manager:
        raise HTTPException(status_code=503, detail="世界模拟器未初始化")

    return {"logs": world_manager.get_interaction_logs(limit)}


@app.post("/api/v1/world/logs/export")
async def export_world_logs():
    """导出日志到Markdown文件"""
    if not world_manager:
        raise HTTPException(status_code=503, detail="世界模拟器未初始化")

    filepath = world_manager.export_logs_to_markdown()
    return {"status": "success", "filepath": filepath}


class PlayerInfo(BaseModel):
    """玩家角色信息"""
    name: str = "旅行者"
    age: int = 28
    gender: str = "男性"
    profession: str = "冒险者"
    background: str = ""


class WorldDialogueRequest(BaseModel):
    """世界对话请求"""
    player_message: str
    npc_name: str
    location: str
    context: Optional[Dict[str, Any]] = None
    player_info: Optional[PlayerInfo] = None


class WorldEventSimpleRequest(BaseModel):
    """简化的世界事件请求"""
    event_content: str
    event_type: str = "world_event"
    location: str
    npc_name: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


# NPC 对话历史缓存（用于连续对话）
npc_conversation_history: Dict[str, list] = {}

# NPC 角色设定
NPC_PROFILES = {
    "埃尔德·铁锤": {
        "profession": "铁匠",
        "personality": "沉稳、实在、略带幽默感",
        "background": "在艾伦谷经营铁匠铺多年的老铁匠，以精湛的锻造技术闻名。",
        "speaking_style": "说话简练直接，偶尔用锻造相关的比喻"
    },
    "贝拉·欢笑": {
        "profession": "酒馆老板娘",
        "personality": "热情开朗、善于倾听、八卦能手",
        "background": "艾伦谷最热闹的酒馆'欢笑杯'的老板娘，消息灵通。",
        "speaking_style": "热情洋溢，喜欢用'亲爱的'称呼客人"
    },
    "西奥多·光明": {
        "profession": "牧师",
        "personality": "慈祥、虔诚、充满智慧",
        "background": "艾伦谷教堂的主持牧师，为村民提供精神指引。",
        "speaking_style": "语调温和，偶尔引用经文或格言"
    },
    "玛格丽特·花语": {
        "profession": "花商",
        "personality": "温柔、浪漫、热爱自然",
        "background": "经营着小镇上最美的花店，对每一朵花都如数家珍。",
        "speaking_style": "说话轻柔，喜欢用花来比喻事物"
    },
    "汉斯·巧手": {
        "profession": "工匠",
        "personality": "细心、专注、有些内向",
        "background": "艾伦谷最出色的木工和机械师，擅长制作各种精巧物件。",
        "speaking_style": "话少但精准，喜欢讨论手艺和工具"
    },
    "老农托马斯": {
        "profession": "农夫",
        "personality": "朴实、勤劳、热心肠",
        "background": "在艾伦谷耕作了一辈子的老农，对土地和天气了如指掌。",
        "speaking_style": "说话朴实，喜欢用农事和天气相关的比喻"
    }
}


@app.post("/api/v1/world/dialogue")
async def world_dialogue(request: WorldDialogueRequest):
    """处理世界中的NPC对话（支持连续对话）"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="NPC服务未初始化")

    npc_name = request.npc_name
    player_message = request.player_message
    location = request.location
    context = request.context or {}
    player_info = request.player_info

    logger.info(f"世界对话: 玩家对 {npc_name} 说: {player_message[:50]}...")

    try:
        # 获取或创建对话历史
        history_key = f"{npc_name}_{location}"
        if history_key not in npc_conversation_history:
            npc_conversation_history[history_key] = []

        conversation_history = npc_conversation_history[history_key]

        # 获取NPC角色设定
        npc_profile = NPC_PROFILES.get(npc_name, {
            "profession": "村民",
            "personality": "友好",
            "background": f"艾伦谷的普通居民。",
            "speaking_style": "朴实自然"
        })

        # 构建玩家信息描述
        player_desc = ""
        if player_info:
            player_desc = f"""
对话对象（玩家角色）：
- 姓名：{player_info.name}
- 年龄：{player_info.age}岁
- 性别：{player_info.gender}
- 职业：{player_info.profession}"""
            if player_info.background:
                player_desc += f"""
- 背景：{player_info.background}"""
            player_desc += """

请根据玩家的身份背景，用合适的方式称呼和回应对方。"""

        # 构建系统提示词
        system_prompt = f"""你是艾伦谷世界中的NPC角色：{npc_name}

角色信息：
- 职业：{npc_profile['profession']}
- 性格：{npc_profile['personality']}
- 背景：{npc_profile['background']}
- 说话风格：{npc_profile['speaking_style']}

当前场景：
- 地点：{location}
- 时间：第{context.get('day', 1)}天 {context.get('hour', 8)}:00
{player_desc}
规则：
1. 始终保持角色扮演，用第一人称回应
2. 回复要简短自然（1-3句话），像真实对话
3. 回复要符合角色的职业、性格和说话风格
4. 如果被问到你不知道的事情，可以合理推测或表示不清楚
5. 不要跳出角色或打破第四面墙
6. 根据玩家的身份和背景，调整你的态度和称呼方式"""

        # 检查是否有可用的LLM客户端
        if hasattr(npc_service, 'llm_client') and npc_service.llm_client:
            # 使用LLM生成响应
            llm_context = {
                "system_prompt": system_prompt,
                "conversation_history": conversation_history[-10:]  # 最多保留10轮历史
            }

            response_text = npc_service.llm_client.generate_response(
                prompt=player_message,
                context=llm_context,
                temperature=0.8,
                max_tokens=200
            )

            # 保存对话历史
            conversation_history.append({"role": "user", "content": player_message})
            conversation_history.append({"role": "assistant", "content": response_text})

            # 限制历史长度
            if len(conversation_history) > 20:
                npc_conversation_history[history_key] = conversation_history[-20:]

            logger.info(f"LLM响应成功: {response_text[:50]}...")
        else:
            # 没有LLM客户端，使用基于规则的响应
            response_text = _generate_fallback_response(npc_name, player_message, npc_profile)
            logger.info(f"使用回退响应: {response_text[:50]}...")

        await ws_manager.broadcast({
            "type": "world_dialogue",
            "player_message": player_message,
            "npc_name": npc_name,
            "npc_response": response_text,
            "location": location,
            "timestamp": datetime.now().isoformat()
        })

        return {
            "response": response_text,
            "npc_name": npc_name,
            "location": location
        }

    except Exception as e:
        logger.error(f"世界对话处理失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "response": f"{npc_name}似乎没有听清你说的话。",
            "npc_name": npc_name,
            "location": location
        }


def _generate_fallback_response(npc_name: str, player_message: str, npc_profile: dict) -> str:
    """生成基于规则的回退响应"""
    import random

    profession = npc_profile.get("profession", "村民")
    message_lower = player_message.lower()

    # 根据消息内容生成相关响应
    if any(word in message_lower for word in ["你好", "嗨", "早", "晚"]):
        greetings = [
            f"你好啊，旅行者！欢迎来到艾伦谷。",
            f"哦，你好！我是{npc_name}，有什么我能帮你的吗？",
            f"欢迎，欢迎！今天想聊点什么？"
        ]
        return random.choice(greetings)

    if any(word in message_lower for word in ["武器", "剑", "刀", "盾"]):
        if "铁匠" in profession:
            return "当然有！我这里有各式各样的武器。你想要什么类型的？铁剑、钢剑还是匕首？"
        else:
            return f"武器？你可能需要去找铁匠铺的埃尔德，他是这方面的专家。"

    if any(word in message_lower for word in ["酒", "吃", "喝", "饿"]):
        if "酒馆" in profession:
            return "亲爱的，想喝点什么？我们这里有最好的麦酒和炖肉！"
        else:
            return "饿了？欢笑杯酒馆的贝拉做的炖肉可是一绝！"

    if any(word in message_lower for word in ["花", "植物", "礼物"]):
        if "花商" in profession:
            return "你来对地方了！今天的玫瑰特别新鲜，送给心上人最合适不过了。"
        else:
            return "花？玛格丽特的花店有最美的鲜花，你可以去看看。"

    if any(word in message_lower for word in ["祈祷", "祝福", "神", "帮助"]):
        if "牧师" in profession:
            return "愿光明照耀你的前路，孩子。有什么困扰你的事情吗？"
        else:
            return "如果你需要祝福，可以去教堂找西奥多牧师。"

    # 默认响应
    defaults = [
        f"嗯，这是个好问题。让我想想...",
        f"有意思！你能再详细说说吗？",
        f"我对这个不太了解，但我们可以聊聊别的。",
        f"原来如此。你在艾伦谷还习惯吗？"
    ]
    return random.choice(defaults)


# ========== 世界事件系统 ==========

# 活动事件缓存
active_world_events: Dict[int, Dict[str, Any]] = {}

# 事件阶段定义
EVENT_PHASES = {
    "fire": [
        {"phase": 1, "description": "火势刚起", "duration": 1},  # 持续1小时
        {"phase": 2, "description": "火势蔓延", "duration": 2},
        {"phase": 3, "description": "全力救火", "duration": 2},
        {"phase": 4, "description": "火势受控", "duration": 1},
        {"phase": 5, "description": "余烬处理", "duration": 1},
        {"phase": 6, "description": "事件结束", "duration": 0}
    ],
    "default": [
        {"phase": 1, "description": "事件发生", "duration": 1},
        {"phase": 2, "description": "事件发展", "duration": 2},
        {"phase": 3, "description": "事件高潮", "duration": 1},
        {"phase": 4, "description": "事件结束", "duration": 0}
    ]
}

# 地点邻接关系（用于事件传播）
LOCATION_ADJACENCY = {
    "村庄大门": ["镇中心", "森林边缘"],
    "镇中心": ["村庄大门", "酒馆", "市场区", "教堂"],
    "酒馆": ["镇中心", "市场区"],
    "市场区": ["镇中心", "酒馆", "铁匠铺"],
    "铁匠铺": ["市场区", "工坊区"],
    "教堂": ["镇中心", "农田"],
    "工坊区": ["铁匠铺", "农田"],
    "农田": ["教堂", "工坊区", "森林边缘"],
    "森林边缘": ["村庄大门", "农田"]
}


class WorldEventTriggerRequest(BaseModel):
    """世界事件触发请求（用于前端世界模拟器）"""
    event_content: str
    event_type: str = "world_event"
    location: str
    npc_name: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@app.post("/api/v1/world/event/trigger")
async def trigger_world_event_llm(request: WorldEventTriggerRequest):
    """触发世界事件并获取NPC反应（LLM驱动）"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="NPC服务未初始化")

    event_content = request.event_content
    location = request.location
    npc_name = request.npc_name
    context = request.context or {}

    logger.info(f"世界事件: [{location}] {event_content[:50]}... NPC: {npc_name}")

    try:
        # 确定事件类型
        event_type = "fire" if any(word in event_content for word in ["火", "燃烧", "着火"]) else "default"
        phases = EVENT_PHASES.get(event_type, EVENT_PHASES["default"])

        # 创建或更新事件 - 使用 UUID 避免哈希冲突
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        if event_id not in active_world_events:
            active_world_events[event_id] = {
                "id": event_id,
                "content": event_content,
                "location": location,
                "type": event_type,
                "start_hour": context.get("hour", 8),
                "start_day": context.get("day", 1),
                "current_phase": 1,
                "phases": phases,
                "elapsed_hours": 0,
                "npc_reactions": {},
                "propagated_to": [location]
            }

        event = active_world_events[event_id]
        current_phase = event["current_phase"]
        phase_info = phases[min(current_phase - 1, len(phases) - 1)]

        # 获取NPC角色设定
        npc_profile = NPC_PROFILES.get(npc_name, {
            "profession": "村民",
            "personality": "友好",
            "background": f"艾伦谷的普通居民。",
            "speaking_style": "朴实自然"
        })

        # 计算NPC与事件的距离
        distance = _calculate_location_distance(location, context.get("npc_location", location))

        # 根据距离调整反应
        distance_context = ""
        if distance == 0:
            distance_context = "事件就发生在你面前，你亲眼目睹了一切。"
        elif distance == 1:
            distance_context = "你听到了附近的骚动，有人跑来告诉你发生了什么。"
        else:
            distance_context = "你听到了远处的传闻，具体情况还不太清楚。"

        # 构建系统提示词
        system_prompt = f"""你是艾伦谷世界中的NPC角色：{npc_name}

角色信息：
- 职业：{npc_profile['profession']}
- 性格：{npc_profile['personality']}
- 背景：{npc_profile['background']}
- 说话风格：{npc_profile['speaking_style']}

当前场景：
- 你所在位置：{context.get("npc_location", location)}
- 事件发生位置：{location}
- {distance_context}
- 事件阶段：{phase_info['description']}

正在发生的事件：
{event_content}

规则：
1. 根据你的角色身份和性格，对这个事件做出反应
2. 反应要符合角色特点和事件的严重程度
3. 如果事件与你的职业相关（如牧师遇到教堂起火），反应要更强烈
4. 回复简短自然（1-2句话），表达你的反应和可能的行动
5. 不要跳出角色"""

        response_text = None
        decision_result = None
        movement_triggered = False
        movement_destination = None

        # 首先，通过四级决策系统处理事件（处理移动逻辑等）
        try:
            decision_result = npc_service.process_event(
                content=event_content,
                event_type=event_type,
                event_location=location
            )
            if decision_result and not decision_result.get("error"):
                response_text = decision_result.get("response_text")
                movement_triggered = decision_result.get("movement_triggered", False)
                movement_destination = decision_result.get("movement_destination")
                logger.info(f"四级决策系统处理成功，移动触发: {movement_triggered}")
        except Exception as e:
            logger.error(f"四级决策系统处理失败: {e}")

        # 如果四级决策没有生成响应，使用LLM生成反应
        if not response_text:
            if hasattr(npc_service, 'llm_client') and npc_service.llm_client:
                try:
                    response_text = npc_service.llm_client.generate_response(
                        prompt=f"作为{npc_name}，你对「{event_content}」这个事件有什么反应？",
                        context={"system_prompt": system_prompt},
                        temperature=0.8,
                        max_tokens=150
                    )
                    logger.info(f"LLM事件响应成功: {response_text[:50]}...")
                except Exception as e:
                    logger.error(f"LLM事件响应失败: {e}")

        # 如果仍然没有响应，使用智能回退
        if not response_text:
            response_text = _generate_event_reaction(npc_name, event_content, npc_profile, phase_info, distance)

        # 保存NPC反应
        event["npc_reactions"][npc_name] = {
            "reaction": response_text,
            "phase": current_phase,
            "timestamp": datetime.now().isoformat(),
            "movement_triggered": movement_triggered,
            "movement_destination": movement_destination
        }

        await ws_manager.broadcast({
            "type": "world_event",
            "event_id": event_id,
            "event_content": event_content,
            "location": location,
            "phase": current_phase,
            "phase_description": phase_info["description"],
            "npc_name": npc_name,
            "npc_reaction": response_text,
            "movement_triggered": movement_triggered,
            "movement_destination": movement_destination,
            "timestamp": datetime.now().isoformat()
        })

        return {
            "status": "success",
            "event_id": event_id,
            "response": response_text,
            "npc_reaction": response_text,
            "phase": current_phase,
            "phase_description": phase_info["description"],
            "movement_triggered": movement_triggered,
            "movement_destination": movement_destination,
            "decision_level": decision_result.get("decision_level") if decision_result else None
        }

    except Exception as e:
        logger.error(f"世界事件处理失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "response": f"{npc_name}注意到了周围发生的事情，神情紧张。",
            "npc_reaction": f"{npc_name}注意到了周围发生的事情，神情紧张。"
        }


def _calculate_location_distance(loc1: str, loc2: str) -> int:
    """计算两个地点之间的距离（BFS）"""
    if loc1 == loc2:
        return 0

    visited = {loc1}
    queue = [(loc1, 0)]

    while queue:
        current, dist = queue.pop(0)
        for neighbor in LOCATION_ADJACENCY.get(current, []):
            if neighbor == loc2:
                return dist + 1
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))

    return 999  # 无法到达


def _generate_event_reaction(npc_name: str, event_content: str, npc_profile: dict, phase_info: dict, distance: int) -> str:
    """生成基于规则的事件反应"""
    import random

    profession = npc_profile.get("profession", "村民")
    phase_desc = phase_info.get("description", "事件发生")
    event_lower = event_content.lower()

    # 检测事件类型
    is_fire = any(word in event_lower for word in ["火", "燃烧", "着火", "烧"])
    is_church = any(word in event_lower for word in ["教堂", "神殿"])

    # 根据职业和事件类型生成反应
    if is_fire and is_church:
        if "牧师" in profession:
            reactions = [
                "天哪！教堂着火了！这是我侍奉了一辈子的地方！快，我们必须救火！",
                "主啊，请保佑教堂！所有人，快来帮忙！",
                "不！教堂里还有圣物！我必须去救出来！"
            ]
            return random.choice(reactions)
        elif "铁匠" in profession:
            return "教堂着火了？我这就带上水桶过去帮忙！打铁的手也能救火！"
        elif "酒馆" in profession:
            return "天哪，教堂起火了！亲爱的们，快放下酒杯，我们得去帮忙救火！"
        elif "花商" in profession:
            return "教堂...起火了？那是我每天祈祷的地方...我们必须做点什么！"

    if is_fire:
        generic_fire = [
            f"火！有火！大家快来帮忙啊！",
            f"这火势看起来不妙，我们得赶紧行动！",
            f"快去取水！每一秒都很重要！"
        ]
        return random.choice(generic_fire)

    # 通用反应
    if distance == 0:
        reactions = [
            f"这...这是怎么回事？",
            f"天哪，我亲眼看到了这一切！",
            f"发生了什么？我们该怎么办？"
        ]
    elif distance == 1:
        reactions = [
            f"我听到了动静，发生什么事了？",
            f"有人跑来说出事了？让我过去看看。",
            f"隔壁好像不太对劲..."
        ]
    else:
        reactions = [
            f"听说那边出事了？希望大家都平安。",
            f"有消息传来，不知道是真是假...",
            f"远处好像有些骚动，不知道怎么了。"
        ]

    return random.choice(reactions)


@app.post("/api/v1/world/time/advance/events")
async def advance_world_time_with_events(hours: int = 1):
    """推进世界时间，更新所有活动事件的状态"""
    global active_world_events

    updated_events = []
    ended_events = []

    for event_id, event in list(active_world_events.items()):
        event["elapsed_hours"] += hours
        phases = event["phases"]

        # 计算当前应该在哪个阶段
        total_duration = 0
        new_phase = len(phases)  # 默认最后阶段（结束）

        for i, phase in enumerate(phases):
            total_duration += phase.get("duration", 1)
            if event["elapsed_hours"] <= total_duration:
                new_phase = i + 1
                break

        old_phase = event["current_phase"]
        event["current_phase"] = new_phase

        if new_phase != old_phase:
            if new_phase >= len(phases):
                # 事件结束
                ended_events.append({
                    "event_id": event_id,
                    "content": event["content"],
                    "location": event["location"],
                    "final_phase": "事件结束"
                })
                del active_world_events[event_id]
            else:
                # 阶段更新
                phase_info = phases[new_phase - 1]
                updated_events.append({
                    "event_id": event_id,
                    "content": event["content"],
                    "location": event["location"],
                    "old_phase": old_phase,
                    "new_phase": new_phase,
                    "phase_description": phase_info["description"]
                })

    # 广播更新
    if updated_events or ended_events:
        await ws_manager.broadcast({
            "type": "world_time_update",
            "hours_advanced": hours,
            "updated_events": updated_events,
            "ended_events": ended_events,
            "active_events_count": len(active_world_events),
            "timestamp": datetime.now().isoformat()
        })

    return {
        "status": "success",
        "hours_advanced": hours,
        "updated_events": updated_events,
        "ended_events": ended_events,
        "active_events": [
            {
                "event_id": eid,
                "content": e["content"],
                "location": e["location"],
                "current_phase": e["current_phase"],
                "phase_description": e["phases"][min(e["current_phase"] - 1, len(e["phases"]) - 1)]["description"],
                "elapsed_hours": e["elapsed_hours"]
            }
            for eid, e in active_world_events.items()
        ]
    }


@app.get("/api/v1/world/events/active")
async def get_active_events():
    """获取所有活动中的世界事件"""
    return {
        "events": [
            {
                "event_id": eid,
                "content": e["content"],
                "location": e["location"],
                "current_phase": e["current_phase"],
                "phase_description": e["phases"][min(e["current_phase"] - 1, len(e["phases"]) - 1)]["description"],
                "elapsed_hours": e["elapsed_hours"],
                "npc_reactions": e["npc_reactions"]
            }
            for eid, e in active_world_events.items()
        ]
    }


@app.post("/api/v1/world/event/simple")
async def trigger_simple_world_event(request: WorldEventSimpleRequest):
    """触发简化的世界事件并获取NPC反应"""
    if not npc_service:
        raise HTTPException(status_code=503, detail="NPC服务未初始化")

    logger.info(f"世界事件: [{request.location}] {request.event_content[:50]}...")

    npc_responses = []

    try:
        # 使用简化响应，不依赖外部API
        if request.npc_name:
            npc_responses.append({
                "npc_name": request.npc_name,
                "reaction": f"{request.npc_name}注意到了这个事件，神情变得严肃起来。"
            })
        else:
            npc_responses.append({
                "npc_name": "附近居民",
                "reaction": "附近的人们注意到了这个事件，纷纷议论起来。"
            })

        await ws_manager.broadcast({
            "type": "world_event_simple",
            "event_content": request.event_content,
            "location": request.location,
            "npc_responses": npc_responses,
            "timestamp": datetime.now().isoformat()
        })

        return {
            "status": "success",
            "event_content": request.event_content,
            "location": request.location,
            "npc_responses": npc_responses
        }

    except Exception as e:
        logger.error(f"事件处理失败: {e}")
        return {
            "status": "error",
            "event_content": request.event_content,
            "location": request.location,
            "npc_responses": [{
                "npc_name": "系统",
                "reaction": "事件已发生，但无法获取详细反应。"
            }]
        }


# ========== NPC Agent 行为系统 API ==========

class NPCAgentEventRequest(BaseModel):
    """NPC Agent 事件处理请求"""
    event_content: str
    event_location: str
    event_type: str = "world_event"
    player_location: str
    context: Optional[Dict[str, Any]] = None


class NPCAgentDecisionRequest(BaseModel):
    """NPC Agent 决策请求"""
    npc_name: str
    event_content: str
    event_location: str
    npc_location: str
    context: Optional[Dict[str, Any]] = None


@app.post("/api/v1/npc/agent/decide")
async def npc_agent_decide(request: NPCAgentDecisionRequest):
    """
    让单个NPC进行ReAct决策，决定对事件采取什么行动
    这是核心的Agent决策接口
    """
    if not npc_service:
        raise HTTPException(status_code=503, detail="NPC服务未初始化")

    npc_name = request.npc_name
    event_content = request.event_content
    event_location = request.event_location
    npc_location = request.npc_location
    context = request.context or {}

    logger.info(f"NPC Agent决策: {npc_name} 对事件 '{event_content[:30]}...' 进行思考")

    try:
        # 获取或创建NPC状态
        npc_state = npc_agent_manager.get_npc_state(npc_name)
        if not npc_state:
            # 创建新的NPC状态
            npc_state = NPCState(
                name=npc_name,
                location=npc_location,
                profession=context.get("profession", "村民"),
                current_activity=context.get("activity", "日常活动")
            )
            npc_agent_manager.npc_states[npc_name] = npc_state
        else:
            # 更新位置
            npc_state.location = npc_location

        # 获取NPC角色设定
        npc_profile = NPC_PROFILES.get(npc_name, {
            "profession": npc_state.profession,
            "personality": "友好",
            "background": "艾伦谷的居民",
            "speaking_style": "朴实自然"
        })

        # 计算与事件的距离
        distance = npc_agent_manager.calculate_distance(npc_location, event_location)

        # 构建事件上下文
        event_context = {
            "event": {
                "content": event_content,
                "location": event_location,
                "phase_description": context.get("phase_description", "事件发生中"),
                "type": context.get("event_type", "world_event")
            },
            "distance": distance,
            "day": context.get("day", 1),
            "hour": context.get("hour", 8)
        }

        # 构建ReAct提示词
        react_prompt = build_react_prompt(
            npc_name=npc_name,
            npc_profile=npc_profile,
            npc_state=npc_state,
            event_context=event_context
        )

        action_result = None
        thinking = ""
        description = ""

        # 使用LLM进行决策
        if hasattr(npc_service, 'llm_client') and npc_service.llm_client:
            try:
                llm_response = npc_service.llm_client.generate_response(
                    prompt=react_prompt,
                    context={"system_prompt": "你是一个角色扮演AI，需要根据情境为NPC做出合理的行为决策。"},
                    temperature=0.7,
                    max_tokens=500
                )

                # 解析LLM响应
                parsed = parse_react_response(llm_response)
                thinking = parsed.get("thinking", "")
                description = parsed.get("description", "")

                if parsed.get("action"):
                    action_result = create_action_from_tool_call(parsed["action"])
                    logger.info(f"LLM决策成功: {npc_name} -> {action_result.action_type.value}")

            except Exception as e:
                logger.error(f"LLM决策失败: {e}")

        # 如果LLM失败，使用规则基础的决策
        if not action_result:
            action_result = _rule_based_decision(
                npc_name, npc_profile, npc_state, event_content, event_location, distance
            )
            thinking = f"根据规则判断: 事件'{event_content}'发生在{event_location}，距离{distance}步"
            description = action_result.content or "NPC做出了反应"

        # 执行行动并更新状态
        action_effects = await _execute_npc_action(npc_name, npc_state, action_result)

        # 记录行为历史
        npc_agent_manager.add_action_to_history(npc_name, action_result)

        # 广播NPC行为
        await ws_manager.broadcast({
            "type": "npc_action",
            "npc_name": npc_name,
            "action_type": action_result.action_type.value,
            "action_target": action_result.target,
            "action_content": action_result.content,
            "thinking": thinking,
            "description": description,
            "effects": action_effects,
            "timestamp": datetime.now().isoformat()
        })

        return {
            "status": "success",
            "npc_name": npc_name,
            "action": action_result.to_dict(),
            "thinking": thinking,
            "description": description,
            "effects": action_effects,
            "new_location": npc_state.location,
            "new_activity": npc_state.current_activity
        }

    except Exception as e:
        logger.error(f"NPC Agent决策失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "npc_name": npc_name,
            "action": {"action_type": "continue", "content": "继续当前活动"},
            "description": f"{npc_name}注意到了周围的变化。"
        }


@app.post("/api/v1/npc/agent/event/process")
async def process_event_with_agents(request: NPCAgentEventRequest):
    """
    处理世界事件，让所有相关NPC通过Agent决策系统做出反应
    区分前台事件（玩家当前位置）和后台事件（其他位置）
    """
    if not npc_service:
        raise HTTPException(status_code=503, detail="NPC服务未初始化")

    event_content = request.event_content
    event_location = request.event_location
    player_location = request.player_location
    context = request.context or {}

    logger.info(f"处理世界事件: '{event_content}' @ {event_location}, 玩家在 {player_location}")

    try:
        # 分类事件
        is_emergency = _is_emergency_event(event_content)
        event_id = f"evt_{uuid.uuid4().hex[:12]}"

        # 获取所有NPC状态
        all_npcs = npc_agent_manager.get_all_npc_states()

        foreground_responses = []  # 前台事件响应（玩家当前位置的NPC）
        background_responses = []  # 后台事件响应（其他位置的NPC）
        npc_movements = []         # NPC移动记录

        for npc_name, npc_data in all_npcs.items():
            npc_location = npc_data["location"]
            distance = npc_agent_manager.calculate_distance(npc_location, event_location)

            # 构建决策请求
            decision_request = NPCAgentDecisionRequest(
                npc_name=npc_name,
                event_content=event_content,
                event_location=event_location,
                npc_location=npc_location,
                context={
                    **context,
                    "distance": distance,
                    "is_emergency": is_emergency,
                    "player_location": player_location,
                    "profession": npc_data.get("profession", "村民"),
                    "activity": npc_data.get("current_activity", "日常活动")
                }
            )

            # 获取NPC决策
            decision_result = await npc_agent_decide(decision_request)

            # 根据NPC是否在玩家位置分类响应
            response_data = {
                "npc_name": npc_name,
                "original_location": npc_location,
                "action": decision_result.get("action", {}),
                "description": decision_result.get("description", ""),
                "thinking": decision_result.get("thinking", ""),
                "new_location": decision_result.get("new_location", npc_location),
                "new_activity": decision_result.get("new_activity", "")
            }

            # 检查是否发生了移动
            if response_data["new_location"] != npc_location:
                npc_movements.append({
                    "npc_name": npc_name,
                    "from": npc_location,
                    "to": response_data["new_location"],
                    "reason": decision_result.get("action", {}).get("reason", "")
                })

            # 分类到前台或后台
            if npc_location == player_location:
                foreground_responses.append(response_data)
            else:
                background_responses.append(response_data)

        # 保存活动事件
        active_world_events[event_id] = {
            "id": event_id,
            "content": event_content,
            "location": event_location,
            "is_emergency": is_emergency,
            "start_time": datetime.now().isoformat(),
            "foreground_responses": foreground_responses,
            "background_responses": background_responses,
            "npc_movements": npc_movements
        }

        # 广播事件处理结果
        await ws_manager.broadcast({
            "type": "world_event_processed",
            "event_id": event_id,
            "event_content": event_content,
            "event_location": event_location,
            "is_emergency": is_emergency,
            "foreground_count": len(foreground_responses),
            "background_count": len(background_responses),
            "movement_count": len(npc_movements),
            "timestamp": datetime.now().isoformat()
        })

        return {
            "status": "success",
            "event_id": event_id,
            "event_content": event_content,
            "event_location": event_location,
            "is_emergency": is_emergency,
            "foreground_responses": foreground_responses,
            "background_responses": background_responses,
            "npc_movements": npc_movements
        }

    except Exception as e:
        logger.error(f"事件处理失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "event_content": event_content,
            "foreground_responses": [],
            "background_responses": []
        }


@app.get("/api/v1/npc/agent/states")
async def get_all_npc_states():
    """获取所有NPC的当前状态"""
    return {
        "status": "success",
        "npcs": npc_agent_manager.get_all_npc_states()
    }


@app.get("/api/v1/npc/agent/state/{npc_name}")
async def get_npc_state(npc_name: str):
    """获取指定NPC的状态"""
    state = npc_agent_manager.get_npc_state(npc_name)
    if not state:
        raise HTTPException(status_code=404, detail=f"未找到NPC: {npc_name}")
    return {
        "status": "success",
        "npc": state.to_dict()
    }


@app.post("/api/v1/npc/agent/update_location")
async def update_npc_location(npc_name: str, new_location: str, activity: str = None):
    """手动更新NPC位置"""
    npc_agent_manager.update_npc_location(npc_name, new_location, activity)
    state = npc_agent_manager.get_npc_state(npc_name)
    return {
        "status": "success",
        "npc_name": npc_name,
        "new_location": new_location,
        "new_activity": state.current_activity if state else activity
    }


def _is_emergency_event(event_content: str) -> bool:
    """判断是否是紧急事件"""
    emergency_keywords = [
        "火", "燃烧", "着火", "爆炸", "攻击", "入侵",
        "强盗", "怪物", "倒塌", "洪水", "地震", "危险",
        "救命", "紧急", "伤害", "死亡"
    ]
    return any(keyword in event_content for keyword in emergency_keywords)


def _rule_based_decision(
    npc_name: str,
    npc_profile: Dict,
    npc_state: NPCState,
    event_content: str,
    event_location: str,
    distance: int
) -> NPCAction:
    """基于规则的NPC决策（LLM回退）"""
    profession = npc_profile.get("profession", "村民")
    is_emergency = _is_emergency_event(event_content)

    # 检查是否是与NPC相关的事件
    is_related = False
    if "教堂" in event_content and "牧师" in profession:
        is_related = True
    elif "火" in event_content and "铁匠" in profession:
        is_related = True  # 铁匠善于用水
    elif "酒馆" in event_content and "酒馆" in profession:
        is_related = True

    # 紧急事件决策
    if is_emergency:
        if distance == 0:
            # 事件就在当前位置
            if is_related:
                return NPCAction(
                    action_type=ActionType.HELP,
                    target=event_content,
                    content=f"{npc_name}立即投入救援行动！",
                    priority=10,
                    reason="紧急事件发生在眼前，必须帮忙"
                )
            else:
                return NPCAction(
                    action_type=ActionType.ALERT,
                    target="all",
                    content=f"大家快来帮忙！{event_content}",
                    priority=8,
                    reason="目睹紧急事件，需要呼救"
                )
        elif distance <= 2:
            # 附近发生紧急事件
            if is_related or "牧师" in profession or "铁匠" in profession:
                # 相关职业或有能力帮助的人应该前往
                return NPCAction(
                    action_type=ActionType.MOVE,
                    target=event_location,
                    content=f"{npc_name}赶往{event_location}帮忙！",
                    priority=9,
                    duration_minutes=5,
                    reason=f"紧急事件需要帮助，前往{event_location}"
                )
            else:
                return NPCAction(
                    action_type=ActionType.OBSERVE,
                    target=event_location,
                    content=f"{npc_name}关注着{event_location}方向的动静",
                    priority=5,
                    reason="关注附近的紧急事件"
                )
        else:
            # 距离较远
            return NPCAction(
                action_type=ActionType.SPEAK,
                target=None,
                content=f"听说{event_location}那边出事了...",
                priority=3,
                reason="听到远处的消息"
            )

    # 非紧急事件
    return NPCAction(
        action_type=ActionType.CONTINUE,
        content=f"{npc_name}继续{npc_state.current_activity}",
        priority=1,
        reason="事件与自己关系不大，继续日常活动"
    )


async def _execute_npc_action(npc_name: str, npc_state: NPCState, action: NPCAction) -> Dict[str, Any]:
    """执行NPC行动并返回效果"""
    effects = {
        "location_changed": False,
        "activity_changed": False,
        "mood_changed": False,
        "messages": []
    }

    if action.action_type == ActionType.MOVE:
        # 移动到新位置
        if action.target and action.target != npc_state.location:
            old_location = npc_state.location
            npc_agent_manager.update_npc_location(npc_name, action.target)
            effects["location_changed"] = True
            effects["old_location"] = old_location
            effects["new_location"] = action.target
            effects["messages"].append(f"{npc_name} 从 {old_location} 移动到 {action.target}")

            # 更新活动
            npc_agent_manager.update_npc_activity(npc_name, f"前往{action.target}")

    elif action.action_type == ActionType.HELP:
        # 帮助行动
        npc_agent_manager.update_npc_activity(npc_name, f"正在帮助: {action.content}", "worried")
        effects["activity_changed"] = True
        effects["messages"].append(f"{npc_name} 开始帮助处理事件")

    elif action.action_type == ActionType.SPEAK or action.action_type == ActionType.ALERT:
        # 说话/警告
        effects["messages"].append(f"{npc_name}: {action.content}")

    elif action.action_type == ActionType.FLEE:
        # 逃跑
        if action.target and action.target != npc_state.location:
            old_location = npc_state.location
            npc_agent_manager.update_npc_location(npc_name, action.target, "躲避危险")
            npc_state.mood = "scared"
            effects["location_changed"] = True
            effects["mood_changed"] = True
            effects["messages"].append(f"{npc_name} 逃往 {action.target}")

    elif action.action_type == ActionType.OBSERVE:
        # 观察
        npc_agent_manager.update_npc_activity(npc_name, f"观察{action.target}")
        effects["activity_changed"] = True

    elif action.action_type == ActionType.WORK:
        # 工作
        npc_agent_manager.update_npc_activity(npc_name, action.content or "工作中")
        effects["activity_changed"] = True

    return effects


# ========== WebSocket ==========

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点 - 实时推送日志和状态"""
    await ws_manager.connect(websocket)

    # 启动日志推送任务
    log_push_task = asyncio.create_task(push_logs_to_client(websocket))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # 处理客户端消息
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif message.get("type") == "subscribe":
                # 可以处理订阅特定类型的消息
                pass

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        log_push_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        ws_manager.disconnect(websocket)
        log_push_task.cancel()


async def push_logs_to_client(websocket: WebSocket):
    """持续推送新日志到客户端"""
    last_log_count = 0

    while True:
        try:
            current_logs = log_manager.get_logs(limit=10)
            current_count = len(log_manager.logs)

            if current_count > last_log_count:
                new_logs = list(log_manager.logs)[-10:]
                await websocket.send_json({
                    "type": "logs",
                    "logs": new_logs
                })
                last_log_count = current_count

            await asyncio.sleep(0.5)
        except Exception:
            break


# ========== 世界数据系统 API ==========

class JobAcceptRequest(BaseModel):
    """接受工作请求"""
    job_id: str
    worker: str


class LodgingBookRequest(BaseModel):
    """住宿预订请求"""
    lodging_id: str
    guest: str
    nights: int = 1


class RelationshipModifyRequest(BaseModel):
    """修改好感度请求"""
    entity_a: str
    entity_b: str
    delta: int
    reason: str = ""


class EventPropagateRequest(BaseModel):
    """事件传播请求"""
    event_content: str
    origin_location: str
    event_type: str = "world_event"
    severity: int = 5


# 经济系统API
@app.get("/api/v1/world/economy/balance/{entity}")
async def get_entity_balance(entity: str):
    """获取实体余额"""
    balance = world_data_manager.get_balance(entity)
    return {"status": "success", "entity": entity, "balance": balance}


@app.post("/api/v1/world/economy/transfer")
async def transfer_funds(from_entity: str, to_entity: str, amount: int,
                         category: str = "transfer", description: str = ""):
    """转账"""
    tx = world_data_manager.transfer(from_entity, to_entity, amount, category, description)
    if tx:
        return {"status": "success", "transaction": tx.to_dict()}
    else:
        return {"status": "error", "message": "余额不足或转账失败"}


# 工作系统API
@app.get("/api/v1/world/jobs")
async def get_available_jobs(location: str = None):
    """获取可用工作列表"""
    jobs = world_data_manager.get_available_jobs(location)
    return {
        "status": "success",
        "jobs": [j.to_dict() for j in jobs]
    }


@app.post("/api/v1/world/jobs/accept")
async def accept_job(request: JobAcceptRequest):
    """接受工作"""
    job = world_data_manager.accept_job(request.job_id, request.worker)
    if job:
        await ws_manager.broadcast({
            "type": "job_accepted",
            "job": job.to_dict(),
            "worker": request.worker,
            "timestamp": datetime.now().isoformat()
        })
        return {"status": "success", "job": job.to_dict()}
    else:
        return {"status": "error", "message": "工作不存在或已被接受"}


@app.post("/api/v1/world/jobs/{job_id}/progress")
async def update_job_progress(job_id: str, progress: float):
    """更新工作进度"""
    job = world_data_manager.update_job_progress(job_id, progress)
    if job:
        if job.status == JobStatus.COMPLETED:
            await ws_manager.broadcast({
                "type": "job_completed",
                "job": job.to_dict(),
                "timestamp": datetime.now().isoformat()
            })
        return {"status": "success", "job": job.to_dict()}
    else:
        return {"status": "error", "message": "工作不存在"}


@app.get("/api/v1/world/jobs/worker/{worker}")
async def get_worker_jobs(worker: str):
    """获取某人的工作"""
    jobs = world_data_manager.get_worker_jobs(worker)
    return {"status": "success", "jobs": [j.to_dict() for j in jobs]}


# 住宿系统API
@app.get("/api/v1/world/lodgings")
async def get_available_lodgings(location: str = None):
    """获取可用住宿"""
    lodgings = world_data_manager.get_available_lodgings(location)
    return {
        "status": "success",
        "lodgings": [l.to_dict() for l in lodgings]
    }


@app.post("/api/v1/world/lodgings/book")
async def book_lodging(request: LodgingBookRequest):
    """预订住宿"""
    result = world_data_manager.book_lodging(
        request.lodging_id, request.guest, request.nights
    )
    if result and result.get("success"):
        await ws_manager.broadcast({
            "type": "lodging_booked",
            "guest": request.guest,
            "lodging": result["lodging"],
            "timestamp": datetime.now().isoformat()
        })
        return {"status": "success", **result}
    elif result and result.get("error"):
        return {"status": "error", "message": result["error"], "required": result.get("required")}
    else:
        return {"status": "error", "message": "住宿不可用"}


@app.post("/api/v1/world/lodgings/{lodging_id}/checkout")
async def checkout_lodging(lodging_id: str):
    """退房"""
    lodging = world_data_manager.checkout_lodging(lodging_id)
    if lodging:
        return {"status": "success", "lodging": lodging.to_dict()}
    else:
        return {"status": "error", "message": "住宿不存在"}


# 好感度系统API
@app.get("/api/v1/world/relationships/{entity}")
async def get_entity_relationships(entity: str):
    """获取实体的所有关系"""
    relations = world_data_manager.get_entity_relationships(entity)
    return {"status": "success", "entity": entity, "relationships": relations}


@app.get("/api/v1/world/relationship")
async def get_relationship(entity_a: str, entity_b: str):
    """获取两个实体之间的关系"""
    rel = world_data_manager.get_relationship(entity_a, entity_b)
    return {"status": "success", "relationship": rel.to_dict()}


@app.post("/api/v1/world/relationship/modify")
async def modify_relationship(request: RelationshipModifyRequest):
    """修改好感度"""
    rel = world_data_manager.modify_affinity(
        request.entity_a, request.entity_b,
        request.delta, request.reason
    )
    await ws_manager.broadcast({
        "type": "relationship_changed",
        "entity_a": request.entity_a,
        "entity_b": request.entity_b,
        "new_affinity": rel.affinity,
        "level": rel.level.value,
        "timestamp": datetime.now().isoformat()
    })
    return {"status": "success", "relationship": rel.to_dict()}


# 异步事件传播API
@app.post("/api/v1/world/events/propagate")
async def start_event_propagation(request: EventPropagateRequest):
    """开始事件传播（异步，基于距离延迟）"""
    event_id = f"evt_{datetime.now().timestamp()}"

    event = world_data_manager.create_propagating_event(
        event_id=event_id,
        content=request.event_content,
        origin_location=request.origin_location,
        event_type=request.event_type,
        severity=request.severity
    )

    await ws_manager.broadcast({
        "type": "event_propagation_started",
        "event": event.to_dict(),
        "timestamp": datetime.now().isoformat()
    })

    return {
        "status": "success",
        "event_id": event_id,
        "event": event.to_dict(),
        "pending_notifications": len(event.pending_notifications)
    }


@app.get("/api/v1/world/events/propagate/{event_id}/next")
async def get_next_propagation(event_id: str):
    """获取下一个待传播的通知"""
    result = world_data_manager.get_next_propagation(event_id)
    if result:
        return {"status": "success", **result}
    else:
        return {"status": "complete", "message": "所有位置已通知"}


@app.post("/api/v1/world/events/propagate/{event_id}/notify")
async def mark_location_notified(event_id: str, location: str):
    """标记位置已通知"""
    world_data_manager.mark_location_notified(event_id, location)
    status = world_data_manager.get_event_propagation_status(event_id)

    await ws_manager.broadcast({
        "type": "event_propagation_update",
        "event_id": event_id,
        "location": location,
        "status": status,
        "timestamp": datetime.now().isoformat()
    })

    return {"status": "success", "propagation_status": status}


@app.get("/api/v1/world/events/propagate/{event_id}/status")
async def get_propagation_status(event_id: str):
    """获取事件传播状态"""
    status = world_data_manager.get_event_propagation_status(event_id)
    if status:
        return {"status": "success", **status}
    else:
        return {"status": "error", "message": "事件不存在"}


# 世界状态API
@app.get("/api/v1/world/data/state")
async def get_world_data_state():
    """获取完整的世界数据状态"""
    return {
        "status": "success",
        "world_data": world_data_manager.get_world_state()
    }


# ========== 世界生成器 API ==========

# 导入世界生成器
try:
    from world_simulator.world_generator import (
        WorldGenerator, WorldConfig, LocationConfig, NPCTemplate,
        WorldTheme, THEME_TEMPLATES
    )
    from npc_core import get_npc_registry
    WORLD_GENERATOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"世界生成器不可用: {e}")
    WORLD_GENERATOR_AVAILABLE = False

# 全局世界生成器实例
world_generator: Optional['WorldGenerator'] = None


class WorldCreateRequest(BaseModel):
    """世界创建请求"""
    description: str = ""
    theme: str = "medieval_fantasy"
    npc_count: int = 5
    world_name: Optional[str] = None


class NPCCreateRequest(BaseModel):
    """NPC创建请求"""
    name: str
    profession: str
    location: str
    traits: List[str] = []
    background: str = ""
    npc_type: str = "permanent"


@app.get("/api/v1/world/generator/themes")
async def get_world_themes():
    """获取可用的世界主题"""
    if not WORLD_GENERATOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="世界生成器不可用")

    themes = []
    for theme in WorldTheme:
        template = THEME_TEMPLATES.get(theme, {})
        themes.append({
            "id": theme.value,
            "name": {
                "medieval_fantasy": "中世纪奇幻",
                "eastern_martial": "东方武侠",
                "steampunk": "蒸汽朋克",
                "post_apocalyptic": "末日废土",
                "modern_urban": "现代都市",
                "pirate_age": "大航海时代",
                "custom": "自定义"
            }.get(theme.value, theme.value),
            "description": template.get("setting_hints", ""),
            "races": template.get("races", []),
            "professions": template.get("professions", [])
        })

    return {"status": "success", "themes": themes}


@app.get("/api/v1/world/generator/saved")
async def get_saved_worlds():
    """获取已保存的世界列表"""
    if not WORLD_GENERATOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="世界生成器不可用")

    try:
        worlds = WorldGenerator.list_saved_worlds()
        return {"status": "success", "saved_worlds": worlds}
    except Exception as e:
        logger.error(f"获取保存的世界失败: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/v1/world/generator/create")
async def create_new_world(request: WorldCreateRequest):
    """创建新世界（使用LLM生成）"""
    global world_generator

    if not WORLD_GENERATOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="世界生成器不可用")

    try:
        # 获取LLM客户端
        llm_client = None
        if npc_service and npc_service.llm_client:
            llm_client = npc_service.llm_client

        world_generator = WorldGenerator(llm_client=llm_client)

        # 生成世界
        try:
            theme_enum = WorldTheme(request.theme)
        except ValueError:
            theme_enum = WorldTheme.MEDIEVAL_FANTASY

        world, locations, npcs = await world_generator.generate_world(
            user_description=request.description,
            theme=theme_enum,
            npc_count=request.npc_count
        )

        # 保存世界
        save_path = world_generator.save_world(request.world_name)

        # 将NPC注册到全局注册表
        registry = get_npc_registry()
        registered_npcs = []
        for npc in npcs.values():
            entry = registry.register_npc(
                name=npc.name,
                npc_type="permanent",
                location=npc.default_location,
                profession=npc.profession,
                traits=npc.personality_traits,
                background=npc.background,
                goals=npc.short_term_goals + npc.long_term_goals,
                origin="world_generation"
            )
            if entry:
                registered_npcs.append(entry.name)

        return {
            "status": "success",
            "world": {
                "id": world.world_id,
                "name": world.world_name,
                "description": world.world_description,
                "theme": world.theme
            },
            "locations": [loc.name for loc in locations.values()],
            "npcs": [{
                "name": npc.name,
                "profession": npc.profession,
                "gender": npc.gender,
                "age": npc.age,
                "race": npc.race,
                "background": npc.background[:100] if npc.background else "",
                "traits": npc.personality_traits[:3] if npc.personality_traits else [],
                "default_location": npc.default_location
            } for npc in npcs.values()],
            "registered_npcs": registered_npcs,
            "save_path": save_path
        }

    except Exception as e:
        logger.error(f"创建世界失败: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.post("/api/v1/world/generator/load")
async def load_saved_world(world_name: str):
    """加载已保存的世界"""
    global world_generator

    if not WORLD_GENERATOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="世界生成器不可用")

    try:
        world_dir = os.path.join("data", "worlds", world_name)
        if not os.path.exists(world_dir):
            return {"status": "error", "message": f"世界不存在: {world_name}"}

        # 获取LLM客户端
        llm_client = None
        if npc_service and npc_service.llm_client:
            llm_client = npc_service.llm_client

        world_generator = WorldGenerator.load_world(world_dir, llm_client)

        # 将NPC注册到全局注册表
        registry = get_npc_registry()
        registered_npcs = []
        for npc in world_generator.npcs.values():
            entry = registry.register_npc(
                name=npc.name,
                npc_type="permanent",
                location=npc.default_location,
                profession=npc.profession,
                traits=npc.personality_traits,
                background=npc.background,
                origin="world_load"
            )
            if entry:
                registered_npcs.append(entry.name)

        return {
            "status": "success",
            "world": {
                "id": world_generator.world_config.world_id,
                "name": world_generator.world_config.world_name,
                "description": world_generator.world_config.world_description,
                "theme": world_generator.world_config.theme
            },
            "locations": list(world_generator.locations.keys()),
            "npcs": [{
                "name": npc.name,
                "profession": npc.profession,
                "gender": npc.gender,
                "age": npc.age,
                "race": npc.race,
                "background": npc.background[:100] if npc.background else "",
                "traits": npc.personality_traits[:3] if npc.personality_traits else [],
                "default_location": npc.default_location
            } for npc in world_generator.npcs.values()],
            "registered_npcs": registered_npcs
        }

    except Exception as e:
        logger.error(f"加载世界失败: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/v1/world/generator/current")
async def get_current_world():
    """获取当前加载的世界信息"""
    if not world_generator or not world_generator.world_config:
        return {"status": "error", "message": "没有加载的世界"}

    return {
        "status": "success",
        "world": {
            "id": world_generator.world_config.world_id,
            "name": world_generator.world_config.world_name,
            "description": world_generator.world_config.world_description,
            "theme": world_generator.world_config.theme
        },
        "locations": [
            {"name": loc.name, "type": loc.location_type, "description": loc.description}
            for loc in world_generator.locations.values()
        ],
        "npcs": [
            {
                "id": npc.npc_id,
                "name": npc.name,
                "profession": npc.profession,
                "location": npc.default_location,
                "traits": npc.personality_traits,
                "background": npc.background[:100] + "..." if len(npc.background) > 100 else npc.background
            }
            for npc in world_generator.npcs.values()
        ]
    }


@app.delete("/api/v1/world/generator/delete/{world_dir}")
async def delete_world(world_dir: str, confirm: bool = False):
    """删除已保存的世界

    Args:
        world_dir: 世界目录名
        confirm: 确认删除标志，必须为True才能删除
    """
    import shutil

    if not confirm:
        return {
            "status": "error",
            "message": "请确认删除操作，设置 confirm=true"
        }

    worlds_dir = Path(__file__).parent.parent / "data" / "worlds"
    world_path = worlds_dir / world_dir

    if not world_path.exists():
        return {
            "status": "error",
            "message": f"世界 '{world_dir}' 不存在"
        }

    # 检查是否是当前加载的世界
    global world_generator
    if world_generator and world_generator.world_config:
        if world_generator.world_config.world_name == world_dir:
            # 卸载当前世界
            world_generator = None

    try:
        # 删除世界目录
        shutil.rmtree(world_path)
        logger.info(f"已删除世界: {world_dir}")

        return {
            "status": "success",
            "message": f"世界 '{world_dir}' 已删除"
        }
    except Exception as e:
        logger.error(f"删除世界失败: {e}")
        return {
            "status": "error",
            "message": f"删除失败: {str(e)}"
        }


@app.get("/api/v1/npc/registry/list")
async def list_registered_npcs():
    """获取注册表中的NPC列表"""
    try:
        registry = get_npc_registry()
        stats = registry.get_statistics()
        active_npcs = registry.get_active_npcs()

        return {
            "status": "success",
            "statistics": stats,
            "npcs": [
                {
                    "id": npc.id,
                    "name": npc.name,
                    "type": npc.npc_type,
                    "status": npc.status,
                    "location": npc.location,
                    "profession": npc.profession,
                    "is_core": registry.is_core_npc(npc_id=npc.id)
                }
                for npc in active_npcs
            ]
        }
    except Exception as e:
        logger.error(f"获取NPC列表失败: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/v1/npc/registry/create")
async def create_npc_manually(request: NPCCreateRequest):
    """手动创建NPC"""
    try:
        registry = get_npc_registry()

        entry = registry.register_npc(
            name=request.name,
            npc_type=request.npc_type,
            location=request.location,
            profession=request.profession,
            traits=request.traits,
            background=request.background,
            origin="manual"
        )

        if entry:
            return {
                "status": "success",
                "npc": {
                    "id": entry.id,
                    "name": entry.name,
                    "type": entry.npc_type,
                    "location": entry.location
                }
            }
        else:
            return {"status": "error", "message": "NPC槽位已满，无法创建"}

    except Exception as e:
        logger.error(f"创建NPC失败: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/v1/npc/registry/promote/{npc_name}")
async def promote_npc_to_core(npc_name: str, reason: str = "玩家标记"):
    """将NPC晋升为核心NPC"""
    try:
        registry = get_npc_registry()
        success = registry.promote_to_core(name=npc_name, reason=reason)

        if success:
            return {"status": "success", "message": f"{npc_name} 已晋升为核心NPC"}
        else:
            return {"status": "error", "message": "晋升失败"}

    except Exception as e:
        logger.error(f"晋升NPC失败: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/v1/npc/registry/remove/{npc_name}")
async def remove_npc(npc_name: str, reason: str = "left"):
    """移除NPC"""
    try:
        registry = get_npc_registry()
        success = registry.unregister_npc(name=npc_name, reason=reason)

        if success:
            return {"status": "success", "message": f"{npc_name} 已移除 ({reason})"}
        else:
            return {"status": "error", "message": "移除失败（可能是核心NPC）"}

    except Exception as e:
        logger.error(f"移除NPC失败: {e}")
        return {"status": "error", "message": str(e)}


# ========== 启动服务 ==========

def run_server(host: str = "127.0.0.1", port: int = 8000):
    """运行服务器"""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
