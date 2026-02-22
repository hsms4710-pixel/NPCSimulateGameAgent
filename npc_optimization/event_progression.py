# -*- coding: utf-8 -*-
"""
事件推进系统
============

负责：
1. 随时间自动推进事件状态
2. 生成后续事件（事件链）
3. 触发NPC对事件的主动响应
4. 管理事件生命周期

设计原则：
- 事件不是静态的，会随时间演变
- LLM决定事件如何发展
- 事件可以产生子事件
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from core_types.event_types import Event, EventAnalysis

logger = logging.getLogger(__name__)


class EventPhase(Enum):
    """事件阶段"""
    INITIAL = "initial"           # 刚发生
    SPREADING = "spreading"       # 消息传播中
    REACTING = "reacting"         # NPC正在反应
    DEVELOPING = "developing"     # 事件发展中
    CLIMAX = "climax"             # 高潮
    RESOLVING = "resolving"       # 正在解决
    RESOLVED = "resolved"         # 已解决
    FADED = "faded"               # 已淡化（被遗忘）


@dataclass
class EventState:
    """事件状态跟踪"""
    event: Event
    phase: EventPhase = EventPhase.INITIAL
    phase_start_time: datetime = field(default_factory=datetime.now)

    # 参与者跟踪
    npcs_aware: List[str] = field(default_factory=list)       # 已知晓的NPC
    npcs_reacted: List[str] = field(default_factory=list)     # 已反应的NPC
    npcs_involved: List[str] = field(default_factory=list)    # 深度参与的NPC

    # 事件链
    triggered_events: List[str] = field(default_factory=list)  # 触发的子事件ID

    # 发展历史
    history: List[Dict[str, Any]] = field(default_factory=list)

    def add_history(self, action: str, details: str = ""):
        """添加历史记录"""
        self.history.append({
            "time": datetime.now().isoformat(),
            "phase": self.phase.value,
            "action": action,
            "details": details
        })


@dataclass
class EventProgression:
    """事件推进结果"""
    event_id: str
    old_phase: EventPhase
    new_phase: EventPhase
    triggered_events: List[Event] = field(default_factory=list)
    npc_actions: Dict[str, str] = field(default_factory=dict)
    world_changes: List[str] = field(default_factory=list)
    narration: str = ""  # LLM生成的叙述


class EventProgressionSystem:
    """
    事件推进系统

    管理事件的生命周期和自动推进。

    防止无限迭代的机制：
    1. MAX_EVENT_DEPTH: 子事件最大深度限制
    2. MAX_ACTIVE_EVENTS: 同时活跃事件数量限制
    3. MIN_IMPORTANCE_THRESHOLD: 低于此重要度的事件自动淡化
    4. MAX_EVENT_LIFETIME: 事件最大生存时间
    5. MAX_CHILD_EVENTS: 单个事件最多触发的子事件数
    """

    # ========== 防止无限迭代的限制 ==========
    MAX_EVENT_DEPTH = 3              # 子事件最大深度（事件->子事件->孙事件）
    MAX_ACTIVE_EVENTS = 20           # 同时活跃的事件最大数量
    MIN_IMPORTANCE_THRESHOLD = 10    # 低于此重要度的事件自动淡化
    MAX_EVENT_LIFETIME_HOURS = 24    # 事件最大生存时间（游戏小时）
    MAX_CHILD_EVENTS = 3             # 单个事件最多触发的子事件数
    IMPORTANCE_DECAY_PER_CHILD = 15  # 每层子事件重要度衰减

    # 阶段持续时间（游戏分钟）
    PHASE_DURATIONS = {
        EventPhase.INITIAL: 10,        # 10分钟后开始传播
        EventPhase.SPREADING: 30,      # 30分钟传播期
        EventPhase.REACTING: 60,       # 60分钟反应期
        EventPhase.DEVELOPING: 120,    # 2小时发展期
        EventPhase.CLIMAX: 30,         # 30分钟高潮
        EventPhase.RESOLVING: 60,      # 60分钟解决期
    }

    # 事件类型的典型持续时间（游戏小时）
    EVENT_DURATIONS = {
        "social": 2,        # 社交事件2小时
        "accident": 4,      # 事故4小时
        "crime": 6,         # 犯罪6小时
        "natural": 8,       # 自然事件8小时
        "political": 24,    # 政治事件1天
        "economic": 48,     # 经济事件2天
    }

    # LLM提示词：事件推进
    EVENT_PROGRESSION_PROMPT = """你是一个世界模拟器。请根据当前事件状态，决定事件如何发展。

事件信息:
- 内容: {event_content}
- 位置: {location}
- 类型: {event_type}
- 重要度: {importance}/100
- 当前阶段: {current_phase}
- 已过时间: {elapsed_time}
- 已知晓的NPC: {npcs_aware}
- 已反应的NPC: {npcs_reacted}

历史发展:
{history}

请决定:
1. 事件是否应该进入下一阶段？(是/否)
2. 如果是，新阶段是什么？
3. 会发生什么新情况？（1-2句话描述）
4. 是否触发新的子事件？如果是，描述子事件。
5. 哪些NPC会主动采取行动？

请用JSON格式回答:
{{
    "advance_phase": true/false,
    "new_phase": "阶段名",
    "development": "发生了什么",
    "trigger_new_event": true/false,
    "new_event": {{"content": "...", "type": "...", "location": "..."}},
    "npc_actions": {{"NPC名": "采取的行动"}}
}}"""

    def __init__(self, llm_client=None):
        """
        初始化事件推进系统

        Args:
            llm_client: LLM客户端
        """
        self.llm_client = llm_client
        self.active_events: Dict[str, EventState] = {}
        self.event_history: List[EventProgression] = []
        self.event_depths: Dict[str, int] = {}  # 事件ID -> 深度

        # 回调函数
        self.on_phase_change: Optional[Callable] = None
        self.on_new_event: Optional[Callable] = None
        self.on_event_resolved: Optional[Callable] = None

    def _get_event_depth(self, event: Event) -> int:
        """获取事件深度（根事件=0，子事件=1，孙事件=2...）"""
        if event.id in self.event_depths:
            return self.event_depths[event.id]

        parent_id = event.data.get("parent_event_id") or event.parent_event_id
        if not parent_id or parent_id not in self.event_depths:
            return 0
        return self.event_depths[parent_id] + 1

    def _can_create_child_event(self, parent_state: EventState) -> bool:
        """检查是否可以创建子事件"""
        # 检查1: 深度限制
        parent_depth = self._get_event_depth(parent_state.event)
        if parent_depth >= self.MAX_EVENT_DEPTH:
            logger.debug(f"事件 {parent_state.event.id} 已达最大深度 {self.MAX_EVENT_DEPTH}")
            return False

        # 检查2: 子事件数量限制
        if len(parent_state.triggered_events) >= self.MAX_CHILD_EVENTS:
            logger.debug(f"事件 {parent_state.event.id} 已达子事件上限 {self.MAX_CHILD_EVENTS}")
            return False

        # 检查3: 活跃事件总数限制
        active_count = sum(1 for s in self.active_events.values()
                          if s.phase not in [EventPhase.RESOLVED, EventPhase.FADED])
        if active_count >= self.MAX_ACTIVE_EVENTS:
            logger.debug(f"活跃事件数 {active_count} 已达上限 {self.MAX_ACTIVE_EVENTS}")
            return False

        return True

    def _should_fade_event(self, state: EventState) -> bool:
        """检查事件是否应该淡化（强制结束）"""
        event = state.event

        # 检查1: 重要度太低
        if event.importance < self.MIN_IMPORTANCE_THRESHOLD:
            logger.debug(f"事件 {event.id} 重要度 {event.importance} 低于阈值，自动淡化")
            return True

        # 检查2: 超过最大生存时间
        lifetime = (datetime.now() - event.timestamp).total_seconds() / 3600
        if lifetime > self.MAX_EVENT_LIFETIME_HOURS:
            logger.debug(f"事件 {event.id} 存活 {lifetime:.1f} 小时，超过上限，自动淡化")
            return True

        return False

    def _calculate_child_importance(self, parent_event: Event) -> int:
        """计算子事件的重要度"""
        parent_depth = self._get_event_depth(parent_event)
        decay = self.IMPORTANCE_DECAY_PER_CHILD * (parent_depth + 1)
        child_importance = max(0, parent_event.importance - decay)
        return child_importance

    def register_event(self, event: Event) -> EventState:
        """注册事件到推进系统"""
        # 检查活跃事件数量限制
        active_count = sum(1 for s in self.active_events.values()
                          if s.phase not in [EventPhase.RESOLVED, EventPhase.FADED])
        if active_count >= self.MAX_ACTIVE_EVENTS:
            logger.warning(f"活跃事件数已达上限 {self.MAX_ACTIVE_EVENTS}，拒绝注册新事件")
            # 强制清理最老的事件
            self._cleanup_oldest_events(count=5)

        # 计算并存储事件深度
        depth = self._get_event_depth(event)
        self.event_depths[event.id] = depth

        # 检查重要度阈值
        if event.importance < self.MIN_IMPORTANCE_THRESHOLD:
            logger.info(f"事件 {event.id} 重要度 {event.importance} 太低，直接标记为淡化")
            state = EventState(event=event, phase=EventPhase.FADED)
            self.active_events[event.id] = state
            return state

        state = EventState(event=event)
        state.add_history("registered", f"事件已注册: {event.content[:50]}")
        self.active_events[event.id] = state
        logger.info(f"事件已注册到推进系统: {event.id} (深度={depth})")
        return state

    def _cleanup_oldest_events(self, count: int = 5):
        """清理最老的活跃事件"""
        # 按时间排序活跃事件
        active_states = [
            (event_id, state)
            for event_id, state in self.active_events.items()
            if state.phase not in [EventPhase.RESOLVED, EventPhase.FADED]
        ]
        active_states.sort(key=lambda x: x[1].event.timestamp)

        # 强制结束最老的事件
        for event_id, state in active_states[:count]:
            state.phase = EventPhase.FADED
            state.event.deactivate()
            state.add_history("force_faded", "因活跃事件过多被强制淡化")
            logger.info(f"事件 {event_id} 被强制淡化")

    def get_event_state(self, event_id: str) -> Optional[EventState]:
        """获取事件状态"""
        return self.active_events.get(event_id)

    def notify_npc_aware(self, event_id: str, npc_name: str):
        """通知NPC已知晓事件"""
        state = self.active_events.get(event_id)
        if state and npc_name not in state.npcs_aware:
            state.npcs_aware.append(npc_name)
            state.add_history("npc_aware", f"{npc_name} 得知了事件")

    def notify_npc_reacted(self, event_id: str, npc_name: str, action: str):
        """通知NPC已对事件做出反应"""
        state = self.active_events.get(event_id)
        if state and npc_name not in state.npcs_reacted:
            state.npcs_reacted.append(npc_name)
            state.add_history("npc_reacted", f"{npc_name}: {action}")

    async def tick(self, game_minutes: int = 10) -> List[EventProgression]:
        """
        推进所有活跃事件

        Args:
            game_minutes: 经过的游戏时间（分钟）

        Returns:
            所有事件的推进结果
        """
        progressions = []

        for event_id, state in list(self.active_events.items()):
            # 跳过已结束的事件
            if state.phase in [EventPhase.RESOLVED, EventPhase.FADED]:
                continue

            # 检查是否应该强制淡化
            if self._should_fade_event(state):
                state.phase = EventPhase.FADED
                state.event.deactivate()
                state.add_history("auto_faded", "重要度过低或超时，自动淡化")
                progressions.append(EventProgression(
                    event_id=event_id,
                    old_phase=state.phase,
                    new_phase=EventPhase.FADED,
                    narration="事件已逐渐被遗忘..."
                ))
                continue

            # 计算该阶段已经过的时间
            elapsed = (datetime.now() - state.phase_start_time).total_seconds() / 60
            phase_duration = self.PHASE_DURATIONS.get(state.phase, 60)

            # 检查是否应该推进
            if elapsed >= phase_duration:
                progression = await self._progress_event(state, game_minutes)
                if progression:
                    progressions.append(progression)
                    self.event_history.append(progression)

        return progressions

    async def _progress_event(self, state: EventState, game_minutes: int) -> Optional[EventProgression]:
        """推进单个事件"""
        old_phase = state.phase

        if self.llm_client:
            # 使用LLM决定事件发展
            return await self._llm_progress_event(state)
        else:
            # 使用规则推进
            return self._rule_based_progress(state)

    def _rule_based_progress(self, state: EventState) -> EventProgression:
        """基于规则的事件推进"""
        old_phase = state.phase
        event = state.event

        # 阶段转换逻辑
        phase_transitions = {
            EventPhase.INITIAL: EventPhase.SPREADING,
            EventPhase.SPREADING: EventPhase.REACTING,
            EventPhase.REACTING: EventPhase.DEVELOPING,
            EventPhase.DEVELOPING: EventPhase.RESOLVING,
            EventPhase.RESOLVING: EventPhase.RESOLVED,
            EventPhase.CLIMAX: EventPhase.RESOLVING,
        }

        new_phase = phase_transitions.get(old_phase, EventPhase.FADED)

        # 更新状态
        state.phase = new_phase
        state.phase_start_time = datetime.now()
        state.add_history("phase_change", f"{old_phase.value} -> {new_phase.value}")

        # 生成叙述
        narrations = {
            EventPhase.SPREADING: f"关于{event.location}的消息开始在村子里传播...",
            EventPhase.REACTING: f"村民们开始对{event.content[:20]}做出反应...",
            EventPhase.DEVELOPING: f"事态正在发展中...",
            EventPhase.RESOLVING: f"事件开始平息...",
            EventPhase.RESOLVED: f"事件已经结束。",
        }

        # 触发回调
        if self.on_phase_change:
            self.on_phase_change(event.id, old_phase, new_phase)

        if new_phase == EventPhase.RESOLVED:
            event.resolve()
            if self.on_event_resolved:
                self.on_event_resolved(event.id)

        return EventProgression(
            event_id=event.id,
            old_phase=old_phase,
            new_phase=new_phase,
            narration=narrations.get(new_phase, "")
        )

    async def _llm_progress_event(self, state: EventState) -> EventProgression:
        """使用LLM推进事件"""
        event = state.event
        old_phase = state.phase

        # 构建历史字符串
        history_str = "\n".join([
            f"- [{h['time'][:16]}] {h['action']}: {h['details']}"
            for h in state.history[-5:]  # 最近5条
        ]) or "（无历史记录）"

        elapsed = datetime.now() - state.phase_start_time
        elapsed_str = f"{int(elapsed.total_seconds() / 60)} 分钟"

        prompt = self.EVENT_PROGRESSION_PROMPT.format(
            event_content=event.content,
            location=event.location,
            event_type=event.event_type,
            importance=event.importance,
            current_phase=state.phase.value,
            elapsed_time=elapsed_str,
            npcs_aware=", ".join(state.npcs_aware) or "无",
            npcs_reacted=", ".join(state.npcs_reacted) or "无",
            history=history_str
        )

        try:
            response = await asyncio.to_thread(
                self.llm_client.generate_response,
                prompt=prompt,
                context={},
                temperature=0.8,
                max_tokens=400
            )

            # 解析响应
            import json
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(response[json_start:json_end])

                triggered_events = []

                # 推进阶段
                if data.get("advance_phase"):
                    new_phase_str = data.get("new_phase", "")
                    try:
                        new_phase = EventPhase(new_phase_str)
                    except ValueError:
                        # 映射常见的中文阶段名
                        phase_map = {
                            "传播中": EventPhase.SPREADING,
                            "反应中": EventPhase.REACTING,
                            "发展中": EventPhase.DEVELOPING,
                            "高潮": EventPhase.CLIMAX,
                            "解决中": EventPhase.RESOLVING,
                            "已解决": EventPhase.RESOLVED,
                        }
                        new_phase = phase_map.get(new_phase_str, self._get_next_phase(old_phase))

                    state.phase = new_phase
                    state.phase_start_time = datetime.now()
                else:
                    new_phase = old_phase

                # 记录发展
                development = data.get("development", "")
                if development:
                    state.add_history("development", development)

                # 触发新事件（带限制检查）
                if data.get("trigger_new_event") and data.get("new_event"):
                    if self._can_create_child_event(state):
                        new_event_data = data["new_event"]
                        child_importance = self._calculate_child_importance(event)

                        new_event = Event.create(
                            content=new_event_data.get("content", ""),
                            event_type=new_event_data.get("type", "general"),
                            location=new_event_data.get("location", event.location),
                            importance=child_importance,
                            parent_event_id=event.id
                        )
                        triggered_events.append(new_event)
                        state.triggered_events.append(new_event.id)

                        # B1：将子事件id写回父事件的child_event_ids字段
                        if hasattr(event, 'child_event_ids'):
                            event.child_event_ids.append(new_event.id)

                        # 注册子事件
                        self.register_event(new_event)

                        if self.on_new_event:
                            self.on_new_event(new_event)

                        logger.info(f"触发子事件: {new_event.id} (重要度={child_importance})")
                    else:
                        logger.debug("子事件创建被限制")

                # 处理NPC行动
                npc_actions = data.get("npc_actions", {})
                for npc_name, action in npc_actions.items():
                    self.notify_npc_reacted(event.id, npc_name, action)

                # 触发回调
                if new_phase != old_phase and self.on_phase_change:
                    self.on_phase_change(event.id, old_phase, new_phase)

                if new_phase == EventPhase.RESOLVED:
                    event.resolve()
                    if self.on_event_resolved:
                        self.on_event_resolved(event.id)

                return EventProgression(
                    event_id=event.id,
                    old_phase=old_phase,
                    new_phase=new_phase,
                    triggered_events=triggered_events,
                    npc_actions=npc_actions,
                    narration=development
                )

        except Exception as e:
            logger.warning(f"LLM事件推进失败: {e}")

        # 回退到规则推进
        return self._rule_based_progress(state)

    def _get_next_phase(self, current: EventPhase) -> EventPhase:
        """获取下一阶段"""
        transitions = {
            EventPhase.INITIAL: EventPhase.SPREADING,
            EventPhase.SPREADING: EventPhase.REACTING,
            EventPhase.REACTING: EventPhase.DEVELOPING,
            EventPhase.DEVELOPING: EventPhase.RESOLVING,
            EventPhase.CLIMAX: EventPhase.RESOLVING,
            EventPhase.RESOLVING: EventPhase.RESOLVED,
        }
        return transitions.get(current, EventPhase.FADED)

    def get_active_events_summary(self) -> List[Dict[str, Any]]:
        """获取活跃事件摘要"""
        summaries = []
        for event_id, state in self.active_events.items():
            if state.phase not in [EventPhase.RESOLVED, EventPhase.FADED]:
                summaries.append({
                    "event_id": event_id,
                    "content": state.event.content[:50],
                    "location": state.event.location,
                    "phase": state.phase.value,
                    "npcs_aware": len(state.npcs_aware),
                    "npcs_reacted": len(state.npcs_reacted),
                    "triggered_events": len(state.triggered_events)
                })
        return summaries

    def _settle_event_tree(self, event_id: str) -> None:
        """递归结算事件树（B1：子事件终止）"""
        state = self.active_events.get(event_id)
        if not state:
            return
        state.phase = EventPhase.RESOLVED
        state.event.resolve()
        state.add_history("settled", "事件树递归结算")

        # 递归结算子事件
        child_ids = list(getattr(state.event, 'child_event_ids', [])) + list(state.triggered_events)
        for child_id in child_ids:
            if child_id in self.active_events:
                self._settle_event_tree(child_id)

        # 结算NPC任务（触发奖励分发）
        self._settle_npc_tasks(state)

        # 写入三层记忆
        self._record_to_memory(state)

        # 触发回调
        if self.on_event_resolved:
            self.on_event_resolved(event_id)

        logger.info(f"事件树结算完成: {event_id}")

    def _record_to_memory(self, state: EventState) -> None:
        """将已结算事件写入记忆层"""
        try:
            ev = state.event
            summary = (
                f"事件「{ev.content[:40]}」在{ev.location}发生，"
                f"共{len(state.npcs_aware)}人知晓，{len(state.npcs_reacted)}人响应，"
                f"最终结算。"
            )
            logger.info(f"事件记忆记录: {summary}")
            # 尝试通过 MemoryLayerManager 写入
            try:
                from npc_optimization.memory_layers import MemoryLayerManager
                if hasattr(MemoryLayerManager, 'record_world_event'):
                    MemoryLayerManager.record_world_event(
                        event_id=ev.id,
                        content=summary,
                        location=ev.location,
                        participants=list(state.npcs_reacted)
                    )
            except ImportError:
                pass
        except Exception as e:
            logger.warning(f"写入事件记忆失败（非阻塞）: {e}")

    def _settle_npc_tasks(self, state: EventState) -> None:
        """结算与该事件关联的NPC任务（发放奖励、更新关系）"""
        # 通过回调通知外部系统处理任务结算
        # 外部系统（event_service）监听 on_event_resolved 时做具体处理
        event_id = state.event.id
        logger.info(f"触发NPC任务结算: event={event_id}, npcs_reacted={state.npcs_reacted}")


# 示例：商人事件的完整推进流程
MERCHANT_EVENT_EXAMPLE = """
时间线示例："村口来了一个商人"

00:00 [INITIAL] 事件发生
      - 商人到达村口
      - 村口的农夫立即注意到

00:10 [SPREADING] 消息传播
      - 农夫告诉路过的村民
      - 消息向中心广场扩散

00:30 [REACTING] NPC反应
      - 杂货店老板：听说后决定去看看
      - 铁匠：不太感兴趣，继续工作
      → 触发子事件："杂货店老板前往村口"

00:45 [DEVELOPING] 事件发展
      - 杂货店老板与商人交谈
      - 发现商人有稀有香料
      → 触发子事件："商人展示稀有香料"

01:30 [DEVELOPING] 继续发展
      - 多个村民围观
      - 开始议价交易

02:00 [RESOLVING] 开始解决
      - 交易完成
      - 商人准备离开

02:30 [RESOLVED] 事件结束
      - 商人离开村庄
      - 事件进入历史记忆
"""


__all__ = [
    'EventPhase',
    'EventState',
    'EventProgression',
    'EventProgressionSystem',
]
