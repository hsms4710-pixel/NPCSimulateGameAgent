"""
NPC路由 - NPC实例化 API（D2/B3）
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/npc", tags=["npc"])


class InstantiateRequest(BaseModel):
    entity_id: str
    trigger_reason: str = "player_interaction"
    description: str = ""
    profession: str = "商人"


@router.post("/instantiate")
async def instantiate_npc(request: InstantiateRequest):
    """实例化临时NPC（B3：商人实例化链路）"""
    try:
        from npc_core.npc_registry import NPCRegistry, NPCType
        registry = NPCRegistry.get_instance()
        # 通过 LLM 或规则生成 NPC 数据（简化版：直接用请求数据）
        npc_data = {
            "name": f"临时_{request.profession}_{request.entity_id[:6]}",
            "profession": request.profession,
            "description": request.description,
            "trigger_reason": request.trigger_reason
        }
        # 注册为临时NPC
        entry = registry.register_npc(
            name=npc_data["name"],
            npc_type=NPCType.TEMPORARY,
            data=npc_data
        )
        return {
            "success": True,
            "npc_name": npc_data["name"],
            "npc_type": "temporary",
            "data": npc_data
        }
    except Exception as e:
        logger.error(f"NPC实例化失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{npc_name}")
async def remove_npc(npc_name: str, reason: str = "任务完成"):
    """移除临时NPC"""
    try:
        from npc_core.npc_registry import NPCRegistry
        registry = NPCRegistry.get_instance()
        registry.unregister_npc(npc_name, reason=reason)
        return {"success": True, "npc_name": npc_name, "reason": reason}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{npc_name}/relationships")
async def get_npc_relationships(npc_name: str):
    """获取NPC关系列表"""
    try:
        from backend.world_data import world_data_manager
        rels = []
        for key, rel in world_data_manager.relationships.items():
            if npc_name in [rel.entity_a, rel.entity_b]:
                rels.append(rel.to_dict())
        rels.sort(key=lambda r: r.get("affinity", 0), reverse=True)
        return {"npc": npc_name, "relationships": rels}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
