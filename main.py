"""NPC Agent — 主入口

FastAPI + WebSocket + 世界Tick + HTTP API
"""
import asyncio, json, logging, os, sys
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.world import WorldManager
from core.llm import LLMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="NPC Agent — 银溪镇")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

world = WorldManager()
llm = LLMClient()
world.init_npcs(llm)

ws_clients: list[WebSocket] = []


class PlayerCreateReq(BaseModel):
    name: str
    profession: str = "旅行者"


class MoveReq(BaseModel):
    location: str


class DialogueReq(BaseModel):
    npc_name: str
    message: str


class TradeReq(BaseModel):
    npc_name: str
    item: str
    action: str = "buy"


class QuestReq(BaseModel):
    quest_id: str


@app.on_event("startup")
async def startup():
    asyncio.create_task(world_tick_loop())
    logger.info("世界 Tick 循环已启动")


async def world_tick_loop():
    while True:
        await asyncio.sleep(10)  # 每10秒tick一次
        try:
            updates = await world.tick()
            state = world.get_world_state()
            state["tick_updates"] = updates
            for ws in ws_clients[:]:
                try:
                    await ws.send_json(state)
                except Exception:
                    ws_clients.remove(ws)
        except Exception as e:
            logger.error(f"Tick 失败: {e}")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        await ws.send_json(world.get_world_state())
        while True:
            data = await ws.receive_text()
            # 客户端消息暂不处理（可通过HTTP API操作）
    except WebSocketDisconnect:
        ws_clients.remove(ws)


@app.get("/api/world")
async def get_world():
    return world.get_world_state()


@app.post("/api/player/create")
async def create_player(req: PlayerCreateReq):
    return world.create_player(req.name, req.profession)


@app.post("/api/player/move")
async def player_move(req: MoveReq):
    if not world.player:
        return {"ok": False, "error": "玩家未创建"}
    if req.location not in world.locations:
        return {"ok": False, "error": "未知地点"}
    old = world.player["location"]
    world.player["location"] = req.location
    world.add_event(f"{world.player['name']}从{old}来到{req.location}", "move", location=req.location, importance=2)
    return {"ok": True, "from": old, "to": req.location}


@app.post("/api/dialogue")
async def dialogue(req: DialogueReq):
    if not world.player:
        return {"ok": False, "error": "玩家未创建"}
    npc_loc = world.get_npc_location(req.npc_name)
    if npc_loc != world.player["location"]:
        return {"ok": False, "error": f"{req.npc_name}不在{world.player['location']}"}
    agent = world.npc_agents.get(req.npc_name)
    if not agent:
        return {"ok": False, "error": "NPC不存在"}
    agent.receive_dialogue(world.player["name"], req.message)
    result = await agent._handle_dialogue()
    if result:
        return {"ok": True, "reply": result[0]["result"]["reply"]}
    return {"ok": False, "error": "NPC无响应"}


@app.post("/api/trade")
async def trade(req: TradeReq):
    if not world.player:
        return {"ok": False, "error": "玩家未创建"}
    return world.economy.trade(world.player["name"], req.npc_name, req.item, req.action)


@app.post("/api/quest/accept")
async def accept_quest(req: QuestReq):
    if not world.player:
        return {"ok": False, "error": "玩家未创建"}
    q = world.quests.get(req.quest_id)
    if not q or q["status"] != "available":
        return {"ok": False, "error": "任务不可接"}
    q["status"] = "active"
    q["accepted_by"] = world.player["name"]
    return {"ok": True, "quest": q}


@app.get("/api/npc/{name}")
async def get_npc_detail(name: str):
    agent = world.npc_agents.get(name)
    if not agent:
        return {"ok": False, "error": "NPC不存在"}
    return agent.to_dict()


# 静态文件服务
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dir, "assets")), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = os.path.join(frontend_dir, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dir, "index.html"))
else:
    @app.get("/")
    async def root():
        return HTMLResponse("<h1>NPC Agent — 银溪镇</h1><p>前端未构建，请先 cd frontend && npm install && npm run build</p>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
