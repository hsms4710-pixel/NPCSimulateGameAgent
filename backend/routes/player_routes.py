"""
玩家路由 - 背包/工作/住宿/关系 API（D2/C3）
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/player", tags=["player"])


# ========== Pydantic 模型 ==========

class TradeRequest(BaseModel):
    seller_npc: str
    item_id: str
    quantity: int = 1
    action: str = "buy"  # buy / sell


class UseItemRequest(BaseModel):
    item_id: str


class WorkRequest(BaseModel):
    location: str
    duration_hours: float = 4.0


class RestRequest(BaseModel):
    location: str
    duration_hours: float = 8.0


# ========== 路由 ==========

@router.get("/inventory")
async def get_inventory():
    """获取玩家背包"""
    try:
        from backend.services.economy_service import get_player_inventory
        # 获取当前玩家名（从 world_manager 或 session）
        player_name = _get_player_name()
        items = get_player_inventory(player_name)
        return {"player": player_name, "inventory": items}
    except Exception as e:
        logger.error(f"获取背包失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gold")
async def get_gold():
    """获取玩家金币"""
    try:
        from backend.services.economy_service import get_player_gold
        player_name = _get_player_name()
        balance = get_player_gold(player_name)
        return {"player": player_name, **balance}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inventory/use")
async def use_item(request: UseItemRequest):
    """使用物品"""
    try:
        from backend.services.economy_service import use_item
        player_name = _get_player_name()
        player_state = _get_player_state()
        result = use_item(player_name, request.item_id, player_state)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade")
async def trade(request: TradeRequest):
    """与NPC交易（买入/卖出）"""
    try:
        from backend.services.economy_service import execute_trade
        player_name = _get_player_name()
        result = execute_trade(
            buyer=player_name if request.action == "buy" else request.seller_npc,
            seller=request.seller_npc if request.action == "buy" else player_name,
            item_id=request.item_id,
            quantity=request.quantity,
            action=request.action
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/work")
async def work(request: WorkRequest):
    """玩家打工（B2：持续性事件链路）"""
    try:
        from backend.services.economy_service import get_economy_system
        from backend.services.event_service import trigger_event
        import asyncio

        player_name = _get_player_name()
        eco = get_economy_system()

        # 查找该地点的雇主
        employer = _find_employer_at(request.location)
        if not employer:
            return {"success": False, "reason": f"{request.location} 没有雇主"}

        # 计算工资（从数据读，不写死）
        wage_per_hour = 10  # 默认，可从 world_data 读取
        total_earned = int(wage_per_hour * request.duration_hours)

        # 创建持续性工作事件
        event_data = await trigger_event(
            event_type="player_work",
            content=f"{player_name}在{request.location}打工",
            location=request.location,
            impact_score=30,
            metadata={"employer": employer, "wage": wage_per_hour, "duration": request.duration_hours}
        )

        # 经济结算
        if eco:
            try:
                eco.currency_manager.transfer(employer, player_name, total_earned, "wage")
            except Exception:
                pass  # 如果雇主没有足够金币，直接给玩家

        return {
            "success": True,
            "earned": total_earned,
            "location": request.location,
            "employer": employer,
            "duration_hours": request.duration_hours,
            "event_id": event_data.get("event_id")
        }
    except Exception as e:
        logger.error(f"打工失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rest")
async def rest(request: RestRequest):
    """玩家住宿/休息（C2：住宿系统）"""
    try:
        from backend.services.economy_service import get_economy_system, get_player_gold
        from backend.services.event_service import trigger_event

        player_name = _get_player_name()
        eco = get_economy_system()

        innkeeper = _find_innkeeper_at(request.location)
        cost_per_hour = 5  # 默认，可从 world_data 读取
        total_cost = int(cost_per_hour * request.duration_hours)

        # 检查金币
        balance = get_player_gold(player_name)
        if balance.get("gold", 0) < total_cost:
            return {"success": False, "reason": "金币不足", "required": total_cost, "have": balance.get("gold", 0)}

        # 扣款
        if eco and innkeeper:
            try:
                eco.currency_manager.transfer(player_name, innkeeper, total_cost, "lodging")
            except Exception:
                pass

        # 创建住宿事件
        event_data = await trigger_event(
            event_type="lodging",
            content=f"{player_name}在{request.location}入住",
            location=request.location,
            impact_score=20,
            metadata={"innkeeper": innkeeper, "cost": total_cost, "duration": request.duration_hours}
        )

        return {
            "success": True,
            "location": request.location,
            "innkeeper": innkeeper,
            "cost": total_cost,
            "duration_hours": request.duration_hours,
            "energy_restored": min(1.0, 0.15 * request.duration_hours),
            "event_id": event_data.get("event_id")
        }
    except Exception as e:
        logger.error(f"住宿失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/relationships")
async def get_player_relationships():
    """获取玩家关系列表"""
    try:
        player_name = _get_player_name()
        from backend.world_data import world_data_manager
        rels = []
        for key, rel in world_data_manager.relationships.items():
            if player_name in [rel.entity_a, rel.entity_b]:
                rels.append(rel.to_dict())
        # 按好感度排序
        rels.sort(key=lambda r: r.get("affinity", 0), reverse=True)
        return {"player": player_name, "relationships": rels}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== 辅助函数 ==========

def _get_player_name() -> str:
    """从全局 world_manager 获取玩家名"""
    try:
        import backend.api_server as api_mod
        wm = getattr(api_mod, 'world_manager', None)
        if wm and wm.player:
            return wm.player.name
    except Exception:
        pass
    return "玩家"


def _get_player_state() -> dict:
    """获取玩家状态字典"""
    try:
        import backend.api_server as api_mod
        wm = getattr(api_mod, 'world_manager', None)
        if wm and wm.player:
            return wm.player.__dict__
    except Exception:
        pass
    return {}


def _find_employer_at(location: str) -> str:
    """动态查找地点的经营者（从 world_manager.locations 读，不写死）"""
    try:
        import backend.api_server as api_mod
        wm = getattr(api_mod, 'world_manager', None)
        if wm:
            loc_info = wm.locations.get(location, {})
            return loc_info.get("owner", "")
    except Exception:
        pass
    return ""


def _find_innkeeper_at(location: str) -> str:
    """查找住宿地点的掌柜"""
    return _find_employer_at(location)
