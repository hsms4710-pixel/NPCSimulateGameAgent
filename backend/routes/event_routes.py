"""
事件路由 - 统一事件 API（D2）
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


class WorldEventRequest(BaseModel):
    """统一事件触发请求（A4：合并Pydantic模型）"""
    event_type: str = "general"
    content: str
    location: Optional[str] = None
    impact_score: int = 50
    target_npc: Optional[str] = None
    trigger_mode: str = "auto"        # auto/manual/agent
    propagation: str = "gradual"      # instant/gradual/rumor
    metadata: Dict[str, Any] = {}


@router.post("/trigger")
async def trigger_event(request: WorldEventRequest):
    """统一事件触发入口"""
    try:
        from backend.services.event_service import trigger_event as svc_trigger
        result = await svc_trigger(
            event_type=request.event_type,
            content=request.content,
            location=request.location or "",
            impact_score=request.impact_score,
            target_npc=request.target_npc or "",
            propagation=request.propagation,
            metadata=request.metadata
        )
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"事件触发失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active")
async def get_active_events():
    """获取所有活跃事件（含phase/子事件树）"""
    try:
        from backend.services.event_service import get_active_events
        return {"events": get_active_events()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{event_id}")
async def get_event_detail(event_id: str):
    """获取单事件详情"""
    try:
        from backend.services.event_service import get_event_detail
        detail = get_event_detail(event_id)
        if not detail:
            raise HTTPException(status_code=404, detail=f"事件 {event_id} 不存在")
        return detail
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{event_id}/tree")
async def get_event_tree(event_id: str):
    """获取事件因果树"""
    try:
        from backend.services.event_service import get_event_detail, _event_progression
        root = get_event_detail(event_id)
        if not root:
            raise HTTPException(status_code=404, detail=f"事件 {event_id} 不存在")

        def build_tree(eid: str, depth: int = 0) -> dict:
            if depth > 5:  # 防止无限递归
                return {"event_id": eid, "children": []}
            node = get_event_detail(eid) or {"event_id": eid}
            children = []
            child_ids = node.get("child_event_ids", []) + node.get("triggered_events", [])
            for cid in child_ids:
                children.append(build_tree(cid, depth + 1))
            node["children"] = children
            return node

        return build_tree(event_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{event_id}/settle")
async def settle_event(event_id: str):
    """结算事件树（所有子事件递归终止）"""
    try:
        from backend.services.event_service import settle_event_tree
        success = settle_event_tree(event_id)
        return {"success": success, "event_id": event_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
