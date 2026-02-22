# -*- coding: utf-8 -*-
"""
NPC生活循环系统
管理多个NPC的自主行为和日常生活
"""

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

# 从统一类型模块导入
from core_types import NPCAction, UnifiedNPCState

# 使用别名保持向后兼容
NPCActivity = NPCAction

logger = logging.getLogger(__name__)


# 活动名称到NPCActivity枚举的映射
ACTIVITY_NAME_MAP = {
    "起床": NPCActivity.WAKING_UP,
    "吃饭": NPCActivity.EAT,
    "工作": NPCActivity.WORK,
    "休息": NPCActivity.REST,
    "睡觉": NPCActivity.SLEEP,
    "社交": NPCActivity.SOCIALIZE,
    "祈祷": NPCActivity.PRAY,
    "观察": NPCActivity.OBSERVE,
    "思考": NPCActivity.THINK,
    "学习": NPCActivity.LEARN,
    "旅行": NPCActivity.TRAVEL,
    "帮助": NPCActivity.HELP_OTHERS,
}


def _parse_activity(activity_str: str) -> NPCActivity:
    """将活动字符串转换为NPCActivity枚举"""
    return ACTIVITY_NAME_MAP.get(activity_str, NPCActivity.IDLE)


@dataclass
class NPCSchedule:
    """NPC日程表"""
    npc_name: str
    # 时间段 -> 活动和位置
    schedule: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def get_scheduled_activity(self, hour: int) -> Dict[str, Any]:
        """根据时间获取计划活动"""
        if 5 <= hour < 7:
            return self.schedule.get("dawn", {"activity": NPCActivity.WAKING_UP, "location": None})
        elif 7 <= hour < 9:
            return self.schedule.get("early_morning", {"activity": NPCActivity.EAT, "location": None})
        elif 9 <= hour < 12:
            return self.schedule.get("morning", {"activity": NPCActivity.WORK, "location": None})
        elif 12 <= hour < 14:
            return self.schedule.get("noon", {"activity": NPCActivity.EAT, "location": None})
        elif 14 <= hour < 17:
            return self.schedule.get("afternoon", {"activity": NPCActivity.WORK, "location": None})
        elif 17 <= hour < 19:
            return self.schedule.get("evening", {"activity": NPCActivity.REST, "location": None})
        elif 19 <= hour < 21:
            return self.schedule.get("night", {"activity": NPCActivity.SOCIALIZE, "location": None})
        else:
            return self.schedule.get("late_night", {"activity": NPCActivity.SLEEP, "location": None})

    @classmethod
    def from_json_schedule(cls, npc_name: str, json_schedule: Dict[str, Any]) -> 'NPCSchedule':
        """从JSON格式的日程表创建NPCSchedule实例"""
        schedule = {}
        for period, data in json_schedule.items():
            if isinstance(data, dict):
                activity_str = data.get("activity", "休息")
                schedule[period] = {
                    "activity": _parse_activity(activity_str),
                    "location": data.get("location"),
                    "description": data.get("description", "")
                }
        return cls(npc_name=npc_name, schedule=schedule)


def load_npc_schedules() -> Dict[str, NPCSchedule]:
    """从数据配置加载所有NPC日程表"""
    from data import get_data_loader
    loader = get_data_loader()

    schedules = {}
    all_npcs = loader.get_all_npcs()

    for npc_id, npc_data in all_npcs.items():
        npc_name = npc_data.get("name", npc_id)
        json_schedule = npc_data.get("daily_schedule", {})
        if json_schedule:
            schedules[npc_name] = NPCSchedule.from_json_schedule(npc_name, json_schedule)

    logger.info(f"从配置文件加载了 {len(schedules)} 个NPC日程表")
    return schedules


# 延迟加载NPC日程（首次访问时加载）
_npc_schedules_cache: Optional[Dict[str, NPCSchedule]] = None


def get_npc_schedules() -> Dict[str, NPCSchedule]:
    """获取NPC日程表（带缓存）"""
    global _npc_schedules_cache
    if _npc_schedules_cache is None:
        _npc_schedules_cache = load_npc_schedules()
    return _npc_schedules_cache


def clear_schedules_cache():
    """清除日程缓存"""
    global _npc_schedules_cache
    _npc_schedules_cache = None


@dataclass
class LifecycleNPCState:
    """生命周期管理专用的NPC状态（简化版）"""
    name: str
    current_location: str
    current_activity: NPCActivity
    needs: Dict[str, float] = field(default_factory=lambda: {
        "hunger": 0.3,
        "fatigue": 0.2,
        "social": 0.5
    })
    mood: str = "平静"
    is_busy: bool = False
    last_update: datetime = field(default_factory=datetime.now)

    # 知道的事件
    known_events: List[str] = field(default_factory=list)

    # 当前正在执行的任务
    current_task: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "current_location": self.current_location,
            "current_activity": self.current_activity.value,
            "needs": self.needs,
            "mood": self.mood,
            "is_busy": self.is_busy,
            "known_events": self.known_events,
            "current_task": self.current_task
        }


class NPCLifecycleManager:
    """NPC生命周期管理器"""

    def __init__(self, world_manager=None):
        self.world_manager = world_manager
        self.npc_states: Dict[str, LifecycleNPCState] = {}
        self.schedules = get_npc_schedules()  # 从配置文件加载日程表
        self._running = False
        self._update_task = None

        # 事件响应回调
        self._event_handlers: List[Callable] = []

        # 初始化NPC状态
        self._initialize_npcs()

    def _initialize_npcs(self):
        """初始化所有NPC状态"""
        for npc_name, schedule in self.schedules.items():
            initial_activity = schedule.get_scheduled_activity(8)
            self.npc_states[npc_name] = LifecycleNPCState(
                name=npc_name,
                current_location=initial_activity.get("location", "镇中心"),
                current_activity=initial_activity.get("activity", NPCActivity.IDLE)
            )
        logger.info(f"初始化了 {len(self.npc_states)} 个NPC")

    def get_npc_state(self, npc_name: str) -> Optional[LifecycleNPCState]:
        """获取NPC状态"""
        return self.npc_states.get(npc_name)

    def get_all_npc_states(self) -> Dict[str, Dict[str, Any]]:
        """获取所有NPC状态"""
        return {name: state.to_dict() for name, state in self.npc_states.items()}

    def update_npc_for_time(self, npc_name: str, hour: int) -> Dict[str, Any]:
        """根据时间更新NPC状态"""
        if npc_name not in self.npc_states:
            return {}

        state = self.npc_states[npc_name]
        schedule = self.schedules.get(npc_name)

        if schedule:
            planned = schedule.get_scheduled_activity(hour)
            new_activity = planned.get("activity", NPCActivity.IDLE)
            new_location = planned.get("location")

            old_activity = state.current_activity
            old_location = state.current_location

            state.current_activity = new_activity
            if new_location:
                state.current_location = new_location

            # 更新需求
            hours_passed = 1
            state.needs["hunger"] = min(1.0, state.needs["hunger"] + hours_passed * 0.05)
            state.needs["fatigue"] = min(1.0, state.needs["fatigue"] + hours_passed * 0.03)

            # 活动影响需求
            if new_activity == NPCActivity.EAT:
                state.needs["hunger"] = max(0, state.needs["hunger"] - 0.5)
            elif new_activity == NPCActivity.SLEEP:
                state.needs["fatigue"] = max(0, state.needs["fatigue"] - 0.3)
            elif new_activity == NPCActivity.SOCIALIZE:
                state.needs["social"] = max(0, state.needs["social"] - 0.3)

            state.last_update = datetime.now()

            # 通知世界管理器
            if self.world_manager:
                self.world_manager.update_npc_state(
                    npc_name,
                    location=state.current_location,
                    status=state.mood,
                    activity=state.current_activity.value
                )

            return {
                "npc_name": npc_name,
                "old_activity": old_activity.value,
                "new_activity": new_activity.value,
                "old_location": old_location,
                "new_location": state.current_location,
                "needs": state.needs.copy()
            }

        return {}

    def update_all_npcs_for_time(self, hour: int) -> List[Dict[str, Any]]:
        """更新所有NPC状态"""
        updates = []
        for npc_name in self.npc_states:
            update = self.update_npc_for_time(npc_name, hour)
            if update:
                updates.append(update)
        return updates

    async def notify_npc_of_event(self, npc_name: str, event: Dict[str, Any],
                                   npc_behavior_system=None) -> Optional[str]:
        """通知NPC有事件发生"""
        if npc_name not in self.npc_states:
            return None

        state = self.npc_states[npc_name]
        event_id = event.get("event_id", "unknown")

        # 检查是否已知道这个事件
        if event_id in state.known_events:
            return None

        state.known_events.append(event_id)

        logger.info(f"NPC {npc_name} 得知了事件: {event.get('title', '未知事件')}")

        # 如果有NPC行为系统，让NPC反应
        if npc_behavior_system:
            try:
                response = await npc_behavior_system.process_event({
                    "type": "world_event",
                    "event": event,
                    "source": "world_event_system"
                })
                return response.get("response")
            except Exception as e:
                logger.error(f"NPC事件响应失败: {e}")

        return f"{npc_name}对此事件表示关注"

    async def propagate_event_to_npcs(self, event: Dict[str, Any],
                                       current_time: datetime,
                                       npc_behavior_system=None) -> Dict[str, str]:
        """将事件传播给相关NPC"""
        responses = {}
        event_location = event.get("location", "")

        for npc_name, state in self.npc_states.items():
            # 计算是否应该知道这个事件（基于距离和时间）
            npc_location = state.current_location

            # 简单距离判断
            if npc_location == event_location:
                # 在同一位置，立即知道
                response = await self.notify_npc_of_event(
                    npc_name, event, npc_behavior_system
                )
                if response:
                    responses[npc_name] = response

        return responses

    def get_npcs_at_location(self, location: str) -> List[str]:
        """获取在指定位置的NPC"""
        return [
            name for name, state in self.npc_states.items()
            if state.current_location == location
        ]

    def is_npc_available(self, npc_name: str) -> bool:
        """检查NPC是否可以交互"""
        state = self.npc_states.get(npc_name)
        if not state:
            return False

        # 睡觉时不可交互
        if state.current_activity == NPCActivity.SLEEP:
            return False

        return not state.is_busy

    def set_npc_busy(self, npc_name: str, busy: bool, task: str = None):
        """设置NPC忙碌状态"""
        if npc_name in self.npc_states:
            self.npc_states[npc_name].is_busy = busy
            self.npc_states[npc_name].current_task = task if busy else None


# 向后兼容别名
NPCState = LifecycleNPCState
