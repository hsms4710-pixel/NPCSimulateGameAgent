# -*- coding: utf-8 -*-
"""
世界管理器
整合玩家、NPC、事件系统，管理整个世界模拟
"""

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
import os

from .player_system import PlayerCharacter, PlayerAction, PlayerNeeds, Gender, Personality, Profession
from .event_system import WorldEventTrigger, WorldEvent, EventType, EventSeverity, PropagationMethod

logger = logging.getLogger(__name__)


class TimeOfDay(Enum):
    """时间段"""
    DAWN = "黎明"         # 5:00 - 7:00
    MORNING = "上午"      # 7:00 - 12:00
    AFTERNOON = "下午"    # 12:00 - 17:00
    EVENING = "傍晚"      # 17:00 - 20:00
    NIGHT = "夜晚"        # 20:00 - 5:00


@dataclass
class WorldTime:
    """世界时间"""
    day: int = 1
    hour: int = 8
    minute: int = 0

    def advance(self, minutes: int = 1):
        """推进时间"""
        self.minute += minutes
        while self.minute >= 60:
            self.minute -= 60
            self.hour += 1
        while self.hour >= 24:
            self.hour -= 24
            self.day += 1

    def get_time_of_day(self) -> TimeOfDay:
        """获取当前时间段"""
        if 5 <= self.hour < 7:
            return TimeOfDay.DAWN
        elif 7 <= self.hour < 12:
            return TimeOfDay.MORNING
        elif 12 <= self.hour < 17:
            return TimeOfDay.AFTERNOON
        elif 17 <= self.hour < 20:
            return TimeOfDay.EVENING
        else:
            return TimeOfDay.NIGHT

    def to_string(self) -> str:
        return f"第{self.day}天 {self.hour:02d}:{self.minute:02d}"

    def to_datetime(self) -> datetime:
        """转换为datetime对象（用于计算）"""
        base = datetime(2024, 1, 1)
        return base + timedelta(days=self.day - 1, hours=self.hour, minutes=self.minute)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day,
            "hour": self.hour,
            "minute": self.minute,
            "time_of_day": self.get_time_of_day().value,
            "display": self.to_string()
        }


# 地点信息
WORLD_LOCATIONS = {
    "镇中心": {
        "type": "公共区域",
        "description": "艾伦谷的中心广场，人来人往",
        "npcs": [],
        "connections": ["市场区", "工坊区", "教堂区", "北区住宅"],
        "services": ["休息"],
        "position": (0, 0)
    },
    "市场区": {
        "type": "商业区",
        "description": "热闹的市场，各种商品琳琅满目",
        "npcs": [],
        "connections": ["镇中心", "酒馆", "杂货店"],
        "services": ["饮食", "购物"],
        "position": (-20, 0)
    },
    "酒馆": {
        "type": "商业区",
        "description": "温馨的酒馆，贝拉·欢笑经营的地方",
        "npcs": ["贝拉·欢笑"],
        "connections": ["市场区"],
        "services": ["饮食", "社交", "休息"],
        "owner": "贝拉·欢笑",
        "position": (-30, 0)
    },
    "杂货店": {
        "type": "商业区",
        "description": "日用品杂货店",
        "npcs": [],
        "connections": ["市场区"],
        "services": ["购物"],
        "position": (-25, -5)
    },
    "工坊区": {
        "type": "工业区",
        "description": "各种工匠的工作区域",
        "npcs": [],
        "connections": ["镇中心", "铁匠铺", "木工坊"],
        "services": ["工作"],
        "position": (20, 0)
    },
    "铁匠铺": {
        "type": "工业区",
        "description": "埃尔德·铁锤的铁匠铺，炉火通明",
        "npcs": ["埃尔德·铁锤"],
        "connections": ["工坊区"],
        "services": ["工作", "购物"],
        "owner": "埃尔德·铁锤",
        "position": (25, 5)
    },
    "木工坊": {
        "type": "工业区",
        "description": "木匠的工作坊",
        "npcs": [],
        "connections": ["工坊区"],
        "services": ["工作"],
        "position": (25, -5)
    },
    "教堂区": {
        "type": "宗教区",
        "description": "圣光教堂所在的区域",
        "npcs": [],
        "connections": ["镇中心", "圣光教堂"],
        "services": ["休息"],
        "position": (0, -20)
    },
    "圣光教堂": {
        "type": "宗教区",
        "description": "西奥多·光明主持的教堂",
        "npcs": ["西奥多·光明"],
        "connections": ["教堂区"],
        "services": ["休息", "社交"],
        "owner": "西奥多·光明",
        "position": (0, -30)
    },
    "北区住宅": {
        "type": "居民区",
        "description": "居民居住的区域",
        "npcs": [],
        "connections": ["镇中心"],
        "services": ["休息"],
        "position": (0, 20)
    }
}


@dataclass
class InteractionLog:
    """交互日志"""
    timestamp: str
    actor: str
    action: str
    target: Optional[str]
    location: str
    details: str
    response: Optional[str] = None
    world_time: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "world_time": self.world_time,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "location": self.location,
            "details": self.details,
            "response": self.response
        }


class WorldManager:
    """世界管理器"""

    def __init__(self):
        self.player: Optional[PlayerCharacter] = None
        self.npcs: Dict[str, Any] = {}  # NPC系统实例
        self.world_time = WorldTime()
        self.event_trigger = WorldEventTrigger()
        self.locations = WORLD_LOCATIONS.copy()

        # 交互日志
        self.interaction_logs: List[InteractionLog] = []

        # NPC活动状态
        self.npc_states: Dict[str, Dict[str, Any]] = {}

        # 是否运行NPC自主行为
        self.npc_autonomous_running = False

        # 回调函数
        self._on_interaction_callback = None
        self._npc_behavior_system = None

        logger.info("世界管理器初始化完成")

    def set_npc_behavior_system(self, npc_system):
        """设置NPC行为系统引用"""
        self._npc_behavior_system = npc_system

    def create_player(self, preset_id: str = None, custom_data: Dict[str, Any] = None) -> PlayerCharacter:
        """创建玩家角色"""
        if preset_id:
            self.player = PlayerCharacter.from_preset(
                preset_id=preset_id,
                name=custom_data.get("name", "旅行者"),
                age=custom_data.get("age", 25),
                gender=Gender(custom_data.get("gender", "男")),
                birthplace=custom_data.get("birthplace", "远方"),
                appearance=custom_data.get("appearance", "")
            )
        elif custom_data:
            self.player = PlayerCharacter.create_custom(
                name=custom_data["name"],
                age=custom_data["age"],
                gender=Gender(custom_data["gender"]),
                profession=custom_data.get("profession", "旅行者"),
                background=custom_data["background"],
                birthplace=custom_data["birthplace"],
                personality=Personality(custom_data["personality"]),
                appearance=custom_data.get("appearance", ""),
                skills=custom_data.get("skills")
            )
        else:
            raise ValueError("必须提供预设ID或自定义数据")

        # 记录日志
        self._log_interaction(
            actor="系统",
            action="玩家创建",
            target=self.player.name,
            details=f"玩家 {self.player.name} 进入了艾伦谷"
        )

        logger.info(f"玩家角色创建: {self.player.name}")
        return self.player

    def get_player(self) -> Optional[PlayerCharacter]:
        """获取当前玩家"""
        return self.player

    def get_current_location_info(self) -> Dict[str, Any]:
        """获取玩家当前位置信息"""
        if not self.player:
            return {}

        location = self.player.current_location
        loc_info = self.locations.get(location, {})

        return {
            "name": location,
            "type": loc_info.get("type", "未知"),
            "description": loc_info.get("description", ""),
            "npcs": self._get_npcs_at_location(location),
            "connections": loc_info.get("connections", []),
            "services": loc_info.get("services", [])
        }

    def _get_npcs_at_location(self, location: str) -> List[Dict[str, Any]]:
        """获取指定位置的NPC列表"""
        npcs_here = []

        # 获取静态NPC
        loc_info = self.locations.get(location, {})
        static_npcs = loc_info.get("npcs", [])

        for npc_name in static_npcs:
            npcs_here.append({
                "name": npc_name,
                "status": self.npc_states.get(npc_name, {}).get("status", "空闲"),
                "activity": self.npc_states.get(npc_name, {}).get("activity", "站着")
            })

        # 获取动态NPC位置
        for npc_name, state in self.npc_states.items():
            if state.get("location") == location and npc_name not in static_npcs:
                npcs_here.append({
                    "name": npc_name,
                    "status": state.get("status", "空闲"),
                    "activity": state.get("activity", "站着")
                })

        return npcs_here

    def get_available_actions(self) -> List[Dict[str, Any]]:
        """获取玩家可执行的行动"""
        if not self.player:
            return []

        location = self.player.current_location
        loc_info = self.locations.get(location, {})
        services = loc_info.get("services", [])
        npcs_here = self._get_npcs_at_location(location)

        actions = []

        # 社交（如果有NPC）
        if npcs_here:
            actions.append({
                "action": PlayerAction.SOCIALIZE.value,
                "description": "与附近的NPC交谈",
                "available_targets": [npc["name"] for npc in npcs_here]
            })

        # 饮食
        if "饮食" in services:
            actions.append({
                "action": PlayerAction.EAT.value,
                "description": "在此处进食",
                "cost": 5  # 金币
            })

        # 工作
        if "工作" in services:
            actions.append({
                "action": PlayerAction.WORK.value,
                "description": "在此处工作",
                "reward": 10  # 金币/小时
            })

        # 休息
        if "休息" in services:
            actions.append({
                "action": PlayerAction.REST.value,
                "description": "在此处休息"
            })

        # 移动
        connections = loc_info.get("connections", [])
        if connections:
            actions.append({
                "action": PlayerAction.MOVE.value,
                "description": "移动到其他地点",
                "destinations": connections
            })

        return actions

    async def execute_player_action(self, action: str, target: str = None,
                                     details: str = "") -> Dict[str, Any]:
        """执行玩家行动"""
        if not self.player:
            return {"success": False, "message": "玩家未创建"}

        action_type = PlayerAction(action)
        result = {"success": True, "message": "", "response": None}

        if action_type == PlayerAction.MOVE:
            result = await self._handle_move(target)

        elif action_type == PlayerAction.SOCIALIZE:
            result = await self._handle_socialize(target, details)

        elif action_type == PlayerAction.EAT:
            result = await self._handle_eat()

        elif action_type == PlayerAction.WORK:
            result = await self._handle_work()

        elif action_type == PlayerAction.REST:
            result = await self._handle_rest()

        # 记录交互日志
        self._log_interaction(
            actor=self.player.name,
            action=action,
            target=target,
            details=details or result.get("message", ""),
            response=result.get("response")
        )

        return result

    async def _handle_move(self, destination: str) -> Dict[str, Any]:
        """处理移动"""
        loc_info = self.locations.get(self.player.current_location, {})
        connections = loc_info.get("connections", [])

        if destination not in connections:
            return {"success": False, "message": f"无法从{self.player.current_location}到达{destination}"}

        old_location = self.player.current_location
        self.player.move_to(destination)

        # 推进时间（移动需要15分钟）
        self.advance_time(15)

        return {
            "success": True,
            "message": f"你从{old_location}来到了{destination}",
            "new_location": self.get_current_location_info()
        }

    async def _handle_socialize(self, npc_name: str, dialogue: str) -> Dict[str, Any]:
        """处理社交"""
        if not npc_name:
            return {"success": False, "message": "请指定要交谈的NPC"}

        npcs_here = self._get_npcs_at_location(self.player.current_location)
        npc_names = [npc["name"] for npc in npcs_here]

        if npc_name not in npc_names:
            return {"success": False, "message": f"{npc_name}不在这里"}

        # 满足社交需求
        self.player.needs.satisfy_social(0.2)

        # 调用NPC系统处理对话
        response = await self._get_npc_response(npc_name, dialogue)

        # 更新关系
        self.player.update_relationship(npc_name, affinity_change=1, trust_change=0.5)

        # 推进时间
        self.advance_time(5)

        return {
            "success": True,
            "message": f"你与{npc_name}交谈了",
            "response": response,
            "relationship": self.player.relationships.get(npc_name)
        }

    async def _get_npc_response(self, npc_name: str, dialogue: str) -> str:
        """获取NPC响应"""
        if self._npc_behavior_system:
            try:
                # 构建事件
                event_data = {
                    "type": "dialogue",
                    "source": self.player.name,
                    "source_type": "player",
                    "content": dialogue,
                    "player_info": self.player.get_character_card()
                }
                result = await self._npc_behavior_system.process_event(event_data)
                return result.get("response", f"{npc_name}点了点头。")
            except Exception as e:
                logger.error(f"获取NPC响应失败: {e}")
                return f"{npc_name}看着你，似乎在思考。"

        return f"{npc_name}友好地回应了你。"

    async def _handle_eat(self) -> Dict[str, Any]:
        """处理饮食"""
        cost = 5
        if self.player.gold < cost:
            return {"success": False, "message": "金币不足"}

        self.player.gold -= cost
        self.player.needs.satisfy_hunger(0.6)

        # 推进时间
        self.advance_time(30)

        return {
            "success": True,
            "message": f"你享用了一顿美餐，花费{cost}金币",
            "gold_remaining": self.player.gold,
            "hunger": self.player.needs.hunger
        }

    async def _handle_work(self, location: str = None, duration_hours: float = 1.0) -> Dict[str, Any]:
        """处理工作（C1：接入经济系统）"""
        location = location or self.player.current_location
        loc_info = self.locations.get(location, {})
        employer = loc_info.get("owner", "")

        # 计算工资（从地点数据读，不写死）
        wage_per_hour = loc_info.get("wage_per_hour", 10)
        total_earned = int(wage_per_hour * duration_hours)

        # 经济系统转账（如果可用）
        try:
            from world_simulator.economy_system import EconomySystem
            eco = EconomySystem()
            if employer:
                eco.currency_manager.transfer(employer, self.player.name, total_earned, "wage")
        except Exception:
            pass

        # 更新玩家金币
        self.player.gold += total_earned

        # 更新疲劳
        fatigue_gain = 0.1 * duration_hours
        self.player.needs.fatigue = min(1.0, self.player.needs.fatigue + fatigue_gain)

        # 更新关系（与雇主）
        if employer:
            self.player.update_relationship(employer, affinity_change=int(2 * duration_hours))

        # 推进时间
        self.advance_time(int(60 * duration_hours))

        return {
            "success": True,
            "message": f"你在{location}工作了{duration_hours}小时，获得{total_earned}金币",
            "earned": total_earned,
            "employer": employer,
            "gold_remaining": self.player.gold,
            "fatigue": self.player.needs.fatigue
        }

    async def _handle_rest(self, location: str = None, duration_hours: float = 1.0) -> Dict[str, Any]:
        """处理休息/住宿（C2：接入经济系统）"""
        location = location or self.player.current_location
        loc_info = self.locations.get(location, {})
        innkeeper = loc_info.get("owner", "")

        # 住宿费用（从地点数据读，不写死）
        cost_per_hour = loc_info.get("lodging_cost_per_hour", 0)
        total_cost = int(cost_per_hour * duration_hours)

        if total_cost > 0:
            if self.player.gold < total_cost:
                return {"success": False, "message": "金币不足", "required": total_cost, "have": self.player.gold}

            # 扣款
            self.player.gold -= total_cost
            try:
                from world_simulator.economy_system import EconomySystem
                eco = EconomySystem()
                if innkeeper:
                    eco.currency_manager.transfer(self.player.name, innkeeper, total_cost, "lodging")
            except Exception:
                pass

        # 恢复精力/减少疲劳
        energy_restore = min(1.0, 0.15 * duration_hours)
        self.player.needs.satisfy_fatigue(energy_restore)

        # 更新关系
        if innkeeper:
            self.player.update_relationship(innkeeper, affinity_change=1)

        # 推进时间
        self.advance_time(int(60 * duration_hours))

        return {
            "success": True,
            "message": f"你在{location}休息了{duration_hours}小时" + (f"，花费{total_cost}金币" if total_cost > 0 else ""),
            "cost": total_cost,
            "innkeeper": innkeeper,
            "gold_remaining": self.player.gold,
            "fatigue": self.player.needs.fatigue,
            "energy_restored": energy_restore
        }

    def advance_time(self, minutes: int = 1):
        """推进世界时间"""
        hours = minutes / 60

        # 推进时间
        self.world_time.advance(minutes)

        # 更新玩家需求
        if self.player:
            self.player.needs.update(hours)

        logger.debug(f"时间推进到: {self.world_time.to_string()}")

    def trigger_world_event(self, title: str, description: str, location: str,
                            event_type: str = "自定义",
                            severity: int = 3) -> WorldEvent:
        """触发世界事件"""
        event = self.event_trigger.trigger_event(
            title=title,
            description=description,
            location=location,
            event_type=EventType(event_type) if event_type in [e.value for e in EventType] else EventType.CUSTOM,
            severity=EventSeverity(severity)
        )

        # 记录日志
        self._log_interaction(
            actor="世界事件",
            action="事件触发",
            target=location,
            details=f"[{event.severity.value}级] {title}: {description}"
        )

        return event

    def get_events_for_location(self, location: str) -> List[Dict[str, Any]]:
        """获取影响指定位置的事件"""
        return self.event_trigger.get_events_for_npc(
            "location_query",
            location,
            self.world_time.to_datetime()
        )

    def update_npc_state(self, npc_name: str, location: str = None,
                         status: str = None, activity: str = None):
        """更新NPC状态"""
        if npc_name not in self.npc_states:
            self.npc_states[npc_name] = {}

        if location:
            self.npc_states[npc_name]["location"] = location
        if status:
            self.npc_states[npc_name]["status"] = status
        if activity:
            self.npc_states[npc_name]["activity"] = activity

    def _log_interaction(self, actor: str, action: str, target: str = None,
                         details: str = "", response: str = None):
        """记录交互日志"""
        log = InteractionLog(
            timestamp=datetime.now().isoformat(),
            world_time=self.world_time.to_string(),
            actor=actor,
            action=action,
            target=target,
            location=self.player.current_location if self.player else "未知",
            details=details,
            response=response
        )
        self.interaction_logs.append(log)

        # 限制日志数量
        if len(self.interaction_logs) > 1000:
            self.interaction_logs = self.interaction_logs[-500:]

    def get_interaction_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取交互日志"""
        return [log.to_dict() for log in self.interaction_logs[-limit:]]

    def export_logs_to_markdown(self, filepath: str = None) -> str:
        """导出日志到Markdown文件"""
        if not filepath:
            filepath = f"simulation_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        content = f"""# 世界模拟日志

## 模拟信息
- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 世界时间: {self.world_time.to_string()}
- 玩家: {self.player.name if self.player else '无'}

## 玩家信息
{self.player.get_character_card() if self.player else '无玩家'}

## 交互记录

| 世界时间 | 行动者 | 行动 | 目标 | 地点 | 详情 | 响应 |
|---------|-------|------|------|------|------|------|
"""
        for log in self.interaction_logs:
            content += f"| {log.world_time or '-'} | {log.actor} | {log.action} | {log.target or '-'} | {log.location} | {log.details[:50]}... | {(log.response or '-')[:30]}... |\n"

        content += f"""

## 世界事件

| 时间 | 事件 | 位置 | 严重度 | 状态 |
|------|------|------|--------|------|
"""
        for event in self.event_trigger.event_history:
            content += f"| {event.timestamp.strftime('%H:%M')} | {event.title} | {event.location} | {event.severity.value} | {'活跃' if event.is_active else '结束'} |\n"

        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"日志已导出到: {filepath}")
        return filepath

    def get_world_state(self) -> Dict[str, Any]:
        """获取完整的世界状态"""
        return {
            "time": self.world_time.to_dict(),
            "player": self.player.to_dict() if self.player else None,
            "current_location": self.get_current_location_info() if self.player else None,
            "available_actions": self.get_available_actions(),
            "active_events": [e.to_dict() for e in self.event_trigger.get_active_events()],
            "npc_states": self.npc_states
        }
