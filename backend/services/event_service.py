"""
事件服务层 - 封装完整事件链路（B1/D1）
"""
import logging
import asyncio
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# 全局引用
_event_coordinator = None
_event_progression = None
_world_event_manager = None


def init_event_services(coordinator=None, progression=None, world_event_mgr=None):
    """初始化事件服务（由 api_server 启动时调用）"""
    global _event_coordinator, _event_progression, _world_event_manager
    _event_coordinator = coordinator
    _event_progression = progression
    _world_event_manager = world_event_mgr
    logger.info("事件服务层初始化完成")


async def trigger_event(event_type: str, content: str, location: str = "",
                        impact_score: int = 50, target_npc: str = "",
                        propagation: str = "gradual",
                        metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    统一事件触发入口（B1完整链路）
    返回事件数据字典
    """
    from core_types.event_types import Event
    metadata = metadata or {}

    # 1. 创建 UnifiedEvent
    event = Event.create(
        content=content,
        event_type=event_type,
        location=location,
        importance=impact_score
    )
    # 附加元数据
    if target_npc:
        event.data["target_npc"] = target_npc
    event.data.update(metadata)

    # 2. 注册到 EventProgressionSystem
    if _event_progression:
        state = _event_progression.register_event(event)
        logger.info(f"事件已注册到推进系统: {event.id}")

    # 3. 空间广播（如果有 WorldEventManager）
    aware_npcs = []
    if _world_event_manager and location:
        pos = (0, 0)  # 默认位置，实际应从地点配置读取
        msg = _world_event_manager.broadcast_spatial_event(
            source_npc="world",
            event_content=content,
            location=pos,
            intensity=min(1.0, impact_score / 100.0),
            range_meters=200.0
        )
        aware_npcs = msg.aware_npcs

    # 4. 将感知到的NPC写入事件
    if hasattr(event, 'aware_npcs'):
        event.aware_npcs.extend(aware_npcs)

    # 5. EventCoordinator 分析并分配角色
    npc_directives = {}
    if _event_coordinator:
        try:
            from core_types.event_types import EventAnalysis, EventPriority
            analysis = EventAnalysis(
                event_id=event.id,
                event_content=content,
                event_type=event_type,
                event_location=location,
                priority=EventPriority.HIGH if impact_score > 70 else EventPriority.MEDIUM,
                affected_npcs=aware_npcs,
                coordination_notes=f"impact={impact_score}"
            )
            npc_directives = await _event_coordinator.coordinate_event(analysis)
        except Exception as e:
            logger.warning(f"EventCoordinator 分析失败: {e}")

    if hasattr(event, 'npc_directives'):
        event.npc_directives.update(npc_directives)

    return {
        "event_id": event.id,
        "event_type": event_type,
        "content": content,
        "location": location,
        "impact_score": impact_score,
        "aware_npcs": aware_npcs,
        "npc_directives": npc_directives,
        "phase": getattr(event, 'phase', 'initial'),
        "timestamp": datetime.now().isoformat()
    }


def get_active_events() -> List[Dict[str, Any]]:
    """获取所有活跃事件（含阶段/子事件树）"""
    if not _event_progression:
        return []
    summaries = _event_progression.get_active_events_summary()
    # 附加子事件信息
    for s in summaries:
        eid = s.get("event_id", "")
        state = _event_progression.active_events.get(eid)
        if state:
            child_ids = list(getattr(state.event, 'child_event_ids', [])) + list(state.triggered_events)
            s["child_event_ids"] = child_ids
            s["history_count"] = len(state.history)
    return summaries


def get_event_detail(event_id: str) -> Optional[Dict[str, Any]]:
    """获取单事件详情"""
    if not _event_progression:
        return None
    state = _event_progression.active_events.get(event_id)
    if not state:
        return None
    ev = state.event
    return {
        "event_id": ev.id,
        "content": ev.content,
        "event_type": ev.event_type,
        "location": ev.location,
        "importance": ev.importance,
        "phase": state.phase.value,
        "npcs_aware": state.npcs_aware,
        "npcs_reacted": state.npcs_reacted,
        "triggered_events": state.triggered_events,
        "child_event_ids": list(getattr(ev, 'child_event_ids', [])),
        "npc_directives": getattr(ev, 'npc_directives', {}),
        "economic_data": getattr(ev, 'economic_data', {}),
        "history": state.history[-10:],
    }


def settle_event_tree(event_id: str) -> bool:
    """触发事件树结算"""
    if not _event_progression:
        return False
    try:
        _event_progression._settle_event_tree(event_id)
        return True
    except Exception as e:
        logger.error(f"事件树结算失败: {e}")
        return False
