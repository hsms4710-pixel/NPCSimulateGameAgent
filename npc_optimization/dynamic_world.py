# -*- coding: utf-8 -*-
"""
动态世界系统
============

核心设计原则：
1. LLM判定事件发展：每个事件结束时由LLM决定是否触发后续
2. NPC动态管理：新角色实例化为真正的NPC，有上限控制
3. 三方交互：世界、NPC、玩家之间的事件流转

关键机制：
- NPC_LIMIT: 世界NPC上限
- 新NPC创建需要检查上限
- NPC可以通过故事发展被销毁（死亡、离开等）
- 临时角色（如过路商人）可以升级为常驻NPC
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from core_types.event_types import Event, EventAnalysis, NPCEventResponse

logger = logging.getLogger(__name__)


# ==================== NPC生命周期 ====================

class NPCStatus(Enum):
    """NPC状态"""
    ACTIVE = "active"           # 活跃中
    TEMPORARY = "temporary"     # 临时（如过路商人）
    INACTIVE = "inactive"       # 不活跃（离开村庄）
    DECEASED = "deceased"       # 已死亡
    IMPRISONED = "imprisoned"   # 被囚禁


@dataclass
class DynamicNPC:
    """动态NPC信息"""
    id: str
    name: str
    profession: str
    location: str
    status: NPCStatus = NPCStatus.ACTIVE

    # 来源信息
    origin_event_id: Optional[str] = None  # 创建该NPC的事件
    created_at: datetime = field(default_factory=datetime.now)

    # NPC数据
    personality: str = ""
    background: str = ""
    goals: List[str] = field(default_factory=list)

    # 关系网络
    relationships: Dict[str, float] = field(default_factory=dict)  # NPC名 -> 好感度

    # 是否为核心NPC（不可销毁）
    is_core: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "profession": self.profession,
            "location": self.location,
            "status": self.status.value,
            "origin_event_id": self.origin_event_id,
            "is_core": self.is_core
        }


# ==================== 事件结果类型 ====================

class EventOutcome(Enum):
    """事件结果类型"""
    CONTINUE = "continue"       # 事件继续发展
    BRANCH = "branch"           # 分支出新事件线
    RESOLVE = "resolve"         # 事件解决
    ESCALATE = "escalate"       # 事件升级
    FADE = "fade"               # 事件淡化


@dataclass
class EventJudgment:
    """LLM对事件的判定结果"""
    outcome: EventOutcome
    reasoning: str                          # LLM的推理过程

    # 后续事件（如果有）
    follow_up_events: List[Dict[str, Any]] = field(default_factory=list)

    # NPC变化
    npcs_to_create: List[Dict[str, Any]] = field(default_factory=list)
    npcs_to_remove: List[str] = field(default_factory=list)  # NPC ID列表
    npc_status_changes: Dict[str, NPCStatus] = field(default_factory=dict)

    # 世界状态变化
    world_changes: List[str] = field(default_factory=list)

    # 开放问题（需要进一步发展的剧情线）
    open_questions: List[str] = field(default_factory=list)


# ==================== 动态世界管理器 ====================

class DynamicWorldManager:
    """
    动态世界管理器

    核心职责：
    1. 管理NPC的创建、销毁、状态变化
    2. 调用LLM判定事件发展
    3. 维护事件链的连贯性
    """

    # NPC上限
    NPC_LIMIT = 15          # 世界中最多15个活跃NPC
    TEMP_NPC_LIMIT = 5      # 最多5个临时NPC

    # LLM提示词：事件结束判定
    EVENT_JUDGMENT_PROMPT = """你是世界模拟器的叙事引擎。一个事件刚刚发生了变化，请判断它应该如何发展。

## 事件信息
- 内容: {event_content}
- 位置: {event_location}
- 类型: {event_type}
- 参与者: {participants}

## 事件经过
{event_history}

## 当前世界状态
- 活跃NPC ({active_npc_count}/{npc_limit}): {active_npcs}
- 临时NPC ({temp_npc_count}/{temp_limit}): {temp_npcs}

## 你需要判断

1. **事件结果** (选一个):
   - continue: 事件自然发展，产生后续
   - branch: 分支出新的事件线
   - resolve: 事件圆满解决
   - escalate: 事件升级，变得更严重
   - fade: 事件自然淡化，无需后续

2. **后续事件**: 如果事件继续，会发生什么？

3. **NPC变化**:
   - 是否需要创建新NPC？（如: 商人→实例化为"李商人"）
   - 是否有NPC应该离开/死亡？
   - NPC状态是否变化？

4. **开放问题**: 这个事件留下了什么未解之谜或待发展的线索？

## 请用JSON格式回答:
{{
    "outcome": "continue/branch/resolve/escalate/fade",
    "reasoning": "你的推理过程（2-3句话）",
    "follow_up_events": [
        {{"content": "后续事件描述", "type": "事件类型", "location": "位置", "importance": 0-100}}
    ],
    "npcs_to_create": [
        {{"name": "NPC名", "profession": "职业", "location": "位置", "is_temporary": true/false, "background": "简短背景"}}
    ],
    "npcs_to_remove": ["要移除的NPC名"],
    "npc_status_changes": {{"NPC名": "新状态"}},
    "world_changes": ["世界状态变化1", "变化2"],
    "open_questions": ["未解之谜1", "待发展线索2"]
}}"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

        # NPC管理
        self.npcs: Dict[str, DynamicNPC] = {}
        self.npc_counter = 0

        # 事件历史
        self.event_chain: List[Event] = []
        self.judgments: List[EventJudgment] = []

        # 开放问题池（未解决的剧情线）
        self.open_questions: List[Dict[str, Any]] = []

        # 回调
        self.on_npc_created: Optional[Callable] = None
        self.on_npc_removed: Optional[Callable] = None
        self.on_event_triggered: Optional[Callable] = None

    # ==================== NPC管理 ====================

    def _generate_npc_id(self) -> str:
        self.npc_counter += 1
        return f"npc_{self.npc_counter:04d}"

    def get_active_npc_count(self) -> int:
        """获取活跃NPC数量"""
        return sum(1 for npc in self.npcs.values()
                   if npc.status == NPCStatus.ACTIVE)

    def get_temp_npc_count(self) -> int:
        """获取临时NPC数量"""
        return sum(1 for npc in self.npcs.values()
                   if npc.status == NPCStatus.TEMPORARY)

    def can_create_npc(self, is_temporary: bool = False) -> Tuple[bool, str]:
        """检查是否可以创建NPC"""
        if is_temporary:
            if self.get_temp_npc_count() >= self.TEMP_NPC_LIMIT:
                return False, f"临时NPC已达上限 ({self.TEMP_NPC_LIMIT})"
        else:
            if self.get_active_npc_count() >= self.NPC_LIMIT:
                return False, f"活跃NPC已达上限 ({self.NPC_LIMIT})"
        return True, "可以创建"

    def create_npc(
        self,
        name: str,
        profession: str,
        location: str,
        is_temporary: bool = False,
        origin_event_id: str = None,
        background: str = "",
        is_core: bool = False
    ) -> Optional[DynamicNPC]:
        """创建NPC"""
        can_create, reason = self.can_create_npc(is_temporary)
        if not can_create:
            logger.warning(f"无法创建NPC '{name}': {reason}")
            return None

        npc = DynamicNPC(
            id=self._generate_npc_id(),
            name=name,
            profession=profession,
            location=location,
            status=NPCStatus.TEMPORARY if is_temporary else NPCStatus.ACTIVE,
            origin_event_id=origin_event_id,
            background=background,
            is_core=is_core
        )
        self.npcs[npc.id] = npc
        logger.info(f"创建NPC: {name} ({npc.id}), 临时={is_temporary}")

        if self.on_npc_created:
            self.on_npc_created(npc)

        return npc

    def remove_npc(self, npc_id: str, reason: str = "removed") -> bool:
        """移除NPC"""
        if npc_id not in self.npcs:
            return False

        npc = self.npcs[npc_id]
        if npc.is_core:
            logger.warning(f"无法移除核心NPC: {npc.name}")
            return False

        # 根据原因设置状态
        if reason == "deceased":
            npc.status = NPCStatus.DECEASED
        elif reason == "left":
            npc.status = NPCStatus.INACTIVE
        elif reason == "imprisoned":
            npc.status = NPCStatus.IMPRISONED
        else:
            npc.status = NPCStatus.INACTIVE

        logger.info(f"NPC状态变更: {npc.name} -> {npc.status.value}")

        if self.on_npc_removed:
            self.on_npc_removed(npc, reason)

        return True

    def promote_temp_npc(self, npc_id: str) -> bool:
        """将临时NPC提升为常驻NPC"""
        if npc_id not in self.npcs:
            return False

        npc = self.npcs[npc_id]
        if npc.status != NPCStatus.TEMPORARY:
            return False

        # 检查是否有空间
        if self.get_active_npc_count() >= self.NPC_LIMIT:
            logger.warning(f"无法提升NPC '{npc.name}': 活跃NPC已满")
            return False

        npc.status = NPCStatus.ACTIVE
        logger.info(f"NPC提升为常驻: {npc.name}")
        return True

    def get_npcs_summary(self) -> Dict[str, List[str]]:
        """获取NPC摘要"""
        active = []
        temp = []
        inactive = []

        for npc in self.npcs.values():
            info = f"{npc.name}({npc.profession})"
            if npc.status == NPCStatus.ACTIVE:
                active.append(info)
            elif npc.status == NPCStatus.TEMPORARY:
                temp.append(info)
            else:
                inactive.append(f"{info}[{npc.status.value}]")

        return {"active": active, "temporary": temp, "inactive": inactive}

    # ==================== LLM事件判定 ====================

    async def judge_event(
        self,
        event: Event,
        event_history: List[str] = None,
        participants: List[str] = None
    ) -> EventJudgment:
        """
        使用LLM判定事件发展

        这是核心方法：在事件的关键节点调用，决定后续发展
        """
        if not self.llm_client:
            return self._fallback_judgment(event)

        # 构建上下文
        summary = self.get_npcs_summary()
        history_str = "\n".join([f"- {h}" for h in (event_history or [])]) or "（无历史）"

        prompt = self.EVENT_JUDGMENT_PROMPT.format(
            event_content=event.content,
            event_location=event.location,
            event_type=event.event_type,
            participants=", ".join(participants or []),
            event_history=history_str,
            active_npc_count=self.get_active_npc_count(),
            npc_limit=self.NPC_LIMIT,
            active_npcs=", ".join(summary["active"]) or "无",
            temp_npc_count=self.get_temp_npc_count(),
            temp_limit=self.TEMP_NPC_LIMIT,
            temp_npcs=", ".join(summary["temporary"]) or "无"
        )

        try:
            response = await asyncio.to_thread(
                self.llm_client.generate_response,
                prompt=prompt,
                context={},
                temperature=0.8,
                max_tokens=600
            )

            # 解析JSON
            import json
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(response[json_start:json_end])

                # 映射outcome
                outcome_map = {
                    "continue": EventOutcome.CONTINUE,
                    "branch": EventOutcome.BRANCH,
                    "resolve": EventOutcome.RESOLVE,
                    "escalate": EventOutcome.ESCALATE,
                    "fade": EventOutcome.FADE
                }
                outcome = outcome_map.get(data.get("outcome", "fade"), EventOutcome.FADE)

                # 映射NPC状态
                status_map = {
                    "active": NPCStatus.ACTIVE,
                    "temporary": NPCStatus.TEMPORARY,
                    "inactive": NPCStatus.INACTIVE,
                    "deceased": NPCStatus.DECEASED,
                    "imprisoned": NPCStatus.IMPRISONED
                }
                npc_status_changes = {}
                for name, status_str in data.get("npc_status_changes", {}).items():
                    if status_str in status_map:
                        npc_status_changes[name] = status_map[status_str]

                judgment = EventJudgment(
                    outcome=outcome,
                    reasoning=data.get("reasoning", ""),
                    follow_up_events=data.get("follow_up_events", []),
                    npcs_to_create=data.get("npcs_to_create", []),
                    npcs_to_remove=data.get("npcs_to_remove", []),
                    npc_status_changes=npc_status_changes,
                    world_changes=data.get("world_changes", []),
                    open_questions=data.get("open_questions", [])
                )

                self.judgments.append(judgment)
                return judgment

        except Exception as e:
            logger.warning(f"LLM判定失败: {e}")

        return self._fallback_judgment(event)

    def _fallback_judgment(self, event: Event) -> EventJudgment:
        """回退判定（无LLM时）"""
        # 基于重要度简单判断
        if event.importance >= 70:
            outcome = EventOutcome.CONTINUE
        elif event.importance >= 40:
            outcome = EventOutcome.RESOLVE
        else:
            outcome = EventOutcome.FADE

        return EventJudgment(
            outcome=outcome,
            reasoning="基于重要度的自动判定"
        )

    # ==================== 执行判定结果 ====================

    async def apply_judgment(self, judgment: EventJudgment, source_event: Event) -> List[Event]:
        """
        执行判定结果

        Returns:
            触发的后续事件列表
        """
        triggered_events = []

        # 1. 创建新NPC
        for npc_data in judgment.npcs_to_create:
            npc = self.create_npc(
                name=npc_data.get("name", "未知"),
                profession=npc_data.get("profession", "村民"),
                location=npc_data.get("location", source_event.location),
                is_temporary=npc_data.get("is_temporary", True),
                origin_event_id=source_event.id,
                background=npc_data.get("background", "")
            )
            if npc:
                logger.info(f"事件触发创建NPC: {npc.name}")

        # 2. 移除/变更NPC状态
        for npc_name in judgment.npcs_to_remove:
            # 查找NPC
            for npc_id, npc in self.npcs.items():
                if npc.name == npc_name:
                    self.remove_npc(npc_id, reason="story")
                    break

        for npc_name, new_status in judgment.npc_status_changes.items():
            for npc_id, npc in self.npcs.items():
                if npc.name == npc_name:
                    old_status = npc.status
                    npc.status = new_status
                    logger.info(f"NPC状态变更: {npc_name} {old_status.value} -> {new_status.value}")
                    break

        # 3. 创建后续事件
        for event_data in judgment.follow_up_events:
            new_event = Event.create(
                content=event_data.get("content", ""),
                event_type=event_data.get("type", "general"),
                location=event_data.get("location", source_event.location),
                importance=event_data.get("importance", source_event.importance - 10),
                parent_event_id=source_event.id
            )
            triggered_events.append(new_event)
            self.event_chain.append(new_event)

            if self.on_event_triggered:
                self.on_event_triggered(new_event)

            logger.info(f"触发后续事件: {new_event.content[:30]}...")

        # 4. 记录开放问题
        for question in judgment.open_questions:
            self.open_questions.append({
                "question": question,
                "source_event_id": source_event.id,
                "created_at": datetime.now().isoformat()
            })

        return triggered_events

    # ==================== 示例场景 ====================

    def get_example_scenarios(self) -> str:
        """返回示例场景说明"""
        return """
## 场景1: 教堂失火

事件链:
1. [世界事件] 教堂失火 (importance=90)
   ↓ LLM判定: escalate
2. [NPC事件] 牧师呼救，村民救火
   ↓ LLM判定: continue
3. [玩家事件] 玩家参与救火
   ↓ LLM判定: branch
   ├─ [事件A] 火被扑灭，教堂受损
   └─ [事件B] 发现纵火痕迹
      ↓ LLM判定: continue
      - 创建临时NPC: "可疑流浪汉"
4. [调查事件] 寻找纵火犯
   ↓ LLM判定: continue
   - 临时NPC提升为常驻: "黑衣人" (职业=纵火犯)
5. [审判事件] 抓获凶手
   ↓ LLM判定: resolve
   - NPC状态变更: "黑衣人" -> imprisoned
   - 开放问题: "谁雇佣了他？"

## 场景2: 商人来访

事件链:
1. [世界事件] 村口来了一个商人 (importance=30)
   ↓ LLM判定: continue
   - 创建临时NPC: "旅行商人老李"
2. [NPC事件] 杂货店老板与商人交谈
   ↓ LLM判定: continue
3. [交易事件] 发现稀有香料
   ↓ LLM判定: branch
   ├─ [事件A] 交易成功，约定下次供货
   │   ↓ LLM判定: resolve
   │   - 临时NPC提升为常驻: "老李" (定期来访)
   └─ [事件B] 价格谈不拢，商人离开
       ↓ LLM判定: fade
       - 移除临时NPC: "旅行商人老李"

## NPC数量控制

活跃NPC上限: 15
临时NPC上限: 5

当NPC满时:
- 新临时NPC无法创建
- 必须等待NPC离开/死亡/被捕
- 或者临时NPC自然离开

核心NPC (is_core=True):
- 不可被移除
- 如: 铁匠、牧师、酒馆老板等村庄核心角色
"""


# ==================== 便捷函数 ====================

_world_manager: Optional[DynamicWorldManager] = None


def get_world_manager() -> DynamicWorldManager:
    """获取全局世界管理器"""
    global _world_manager
    if _world_manager is None:
        _world_manager = DynamicWorldManager()
    return _world_manager


def reset_world_manager():
    """重置世界管理器"""
    global _world_manager
    _world_manager = None


__all__ = [
    'NPCStatus',
    'DynamicNPC',
    'EventOutcome',
    'EventJudgment',
    'DynamicWorldManager',
    'get_world_manager',
    'reset_world_manager',
]
