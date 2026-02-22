# -*- coding: utf-8 -*-
"""
多NPC并行运行系统
================

实现多个NPC Agent的并发执行，使用asyncio进行任务调度。

主要组件:
- NPCAgent: 单个NPC的异步Agent包装器
- WorldSimulator: 世界模拟器主类，协调所有NPC并行执行
- SimulationClock: 模拟时钟，管理游戏时间
- EventScheduler: 事件调度器，处理定时事件

WorldSimulator 继承自 BaseNPCRegistry，实现统一的NPC注册接口。
"""

import asyncio
import logging
import threading
import uuid
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# 从统一类型模块导入
from core_types import AgentState, MessageType, MessagePriority

# 导入必要模块
from npc_optimization.message_bus import NPCMessageBus, Message

# 导入接口
from interfaces import BaseNPCRegistry, NPCStateInterface, Position

logger = logging.getLogger(__name__)


@dataclass
class GameTime:
    """游戏时间"""
    day: int = 1
    hour: int = 8
    minute: int = 0

    def advance(self, minutes: int):
        """推进时间"""
        self.minute += minutes
        while self.minute >= 60:
            self.minute -= 60
            self.hour += 1
        while self.hour >= 24:
            self.hour -= 24
            self.day += 1

    def to_datetime(self) -> datetime:
        """转换为datetime对象"""
        base = datetime(2024, 1, 1)
        return base + timedelta(days=self.day - 1, hours=self.hour, minutes=self.minute)

    def to_string(self) -> str:
        """转换为字符串"""
        return f"Day {self.day} {self.hour:02d}:{self.minute:02d}"

    def copy(self) -> "GameTime":
        """创建副本"""
        return GameTime(day=self.day, hour=self.hour, minute=self.minute)

    def __eq__(self, other):
        if not isinstance(other, GameTime):
            return False
        return self.day == other.day and self.hour == other.hour and self.minute == other.minute

    def __lt__(self, other):
        if not isinstance(other, GameTime):
            return NotImplemented
        if self.day != other.day:
            return self.day < other.day
        if self.hour != other.hour:
            return self.hour < other.hour
        return self.minute < other.minute

    def __le__(self, other):
        return self == other or self < other


@dataclass
class ScheduledEvent:
    """调度事件"""
    event_id: str
    trigger_time: GameTime
    event_type: str
    content: str
    target_agents: List[str] = field(default_factory=list)  # 空表示广播给所有
    metadata: Dict[str, Any] = field(default_factory=dict)
    executed: bool = False

    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())[:8]


class SimulationClock:
    """
    模拟时钟
    管理游戏时间的推进和定时回调
    """

    def __init__(self, initial_time: GameTime = None):
        """
        初始化模拟时钟

        Args:
            initial_time: 初始时间，默认为第1天8:00
        """
        self._current_time = initial_time or GameTime()
        self._time_scale = 1.0  # 1秒现实时间 = 1分钟游戏时间
        self._callbacks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._running = False

    @property
    def current_time(self) -> GameTime:
        """获取当前游戏时间"""
        with self._lock:
            return self._current_time.copy()

    @property
    def time_scale(self) -> float:
        """获取时间缩放"""
        return self._time_scale

    @time_scale.setter
    def time_scale(self, value: float):
        """设置时间缩放（1秒现实 = N分钟游戏）"""
        if value <= 0:
            raise ValueError("时间缩放必须大于0")
        self._time_scale = value

    def advance(self, minutes: int = 1) -> GameTime:
        """
        推进游戏时间

        Args:
            minutes: 推进的分钟数

        Returns:
            推进后的游戏时间
        """
        with self._lock:
            old_time = self._current_time.copy()
            self._current_time.advance(minutes)
            new_time = self._current_time.copy()

        # 检查并触发定时回调
        self._check_callbacks(old_time, new_time)

        logger.debug(f"时间推进: {old_time.to_string()} -> {new_time.to_string()}")
        return new_time

    def add_callback(self,
                     trigger_time: GameTime,
                     callback: Callable[[], Any],
                     callback_id: str = None) -> str:
        """
        添加定时回调

        Args:
            trigger_time: 触发时间
            callback: 回调函数
            callback_id: 回调ID（可选）

        Returns:
            回调ID
        """
        callback_id = callback_id or str(uuid.uuid4())[:8]

        with self._lock:
            self._callbacks[callback_id] = {
                "trigger_time": trigger_time,
                "callback": callback,
                "executed": False
            }

        return callback_id

    def remove_callback(self, callback_id: str):
        """移除定时回调"""
        with self._lock:
            if callback_id in self._callbacks:
                del self._callbacks[callback_id]

    def _check_callbacks(self, old_time: GameTime, new_time: GameTime):
        """检查并触发到期的回调"""
        with self._lock:
            callbacks_copy = dict(self._callbacks)

        for callback_id, info in callbacks_copy.items():
            if info["executed"]:
                continue

            trigger_time = info["trigger_time"]

            # 检查触发时间是否在old_time和new_time之间
            if old_time < trigger_time <= new_time:
                try:
                    info["callback"]()
                    with self._lock:
                        if callback_id in self._callbacks:
                            self._callbacks[callback_id]["executed"] = True
                except Exception as e:
                    logger.error(f"回调执行失败 [{callback_id}]: {e}")

    def reset(self, new_time: GameTime = None):
        """重置时钟"""
        with self._lock:
            self._current_time = new_time or GameTime()
            self._callbacks.clear()


class EventScheduler:
    """
    事件调度器
    管理和调度游戏事件
    """

    def __init__(self, clock: SimulationClock):
        """
        初始化事件调度器

        Args:
            clock: 模拟时钟实例
        """
        self._clock = clock
        self._scheduled_events: Dict[str, ScheduledEvent] = {}
        self._event_history: List[ScheduledEvent] = []
        self._lock = threading.RLock()
        self._max_history = 1000

    def schedule_event(self,
                       event_type: str,
                       content: str,
                       trigger_time: GameTime,
                       target_agents: List[str] = None,
                       metadata: Dict[str, Any] = None,
                       event_id: str = None) -> str:
        """
        安排事件

        Args:
            event_type: 事件类型
            content: 事件内容
            trigger_time: 触发时间
            target_agents: 目标Agent列表（空表示广播）
            metadata: 事件元数据
            event_id: 事件ID（可选）

        Returns:
            事件ID
        """
        event = ScheduledEvent(
            event_id=event_id or str(uuid.uuid4())[:8],
            trigger_time=trigger_time,
            event_type=event_type,
            content=content,
            target_agents=target_agents or [],
            metadata=metadata or {}
        )

        with self._lock:
            self._scheduled_events[event.event_id] = event

        logger.info(f"事件已安排: [{event.event_id}] {event_type} @ {trigger_time.to_string()}")
        return event.event_id

    def cancel_event(self, event_id: str) -> bool:
        """取消事件"""
        with self._lock:
            if event_id in self._scheduled_events:
                del self._scheduled_events[event_id]
                return True
        return False

    async def process_scheduled_events(self) -> List[ScheduledEvent]:
        """
        处理到期的事件

        Returns:
            已触发的事件列表
        """
        current_time = self._clock.current_time
        triggered_events = []

        with self._lock:
            for event_id, event in list(self._scheduled_events.items()):
                if event.executed:
                    continue

                if event.trigger_time <= current_time:
                    event.executed = True
                    triggered_events.append(event)

                    # 添加到历史
                    self._event_history.append(event)
                    if len(self._event_history) > self._max_history:
                        self._event_history.pop(0)

        if triggered_events:
            logger.info(f"触发了 {len(triggered_events)} 个调度事件")

        return triggered_events

    def get_pending_events(self) -> List[ScheduledEvent]:
        """获取待处理的事件"""
        with self._lock:
            return [e for e in self._scheduled_events.values() if not e.executed]

    def get_event_history(self, limit: int = 50) -> List[ScheduledEvent]:
        """获取事件历史"""
        with self._lock:
            return self._event_history[-limit:]


class NPCAgent:
    """
    单个NPC的异步Agent包装器
    将NPC行为系统包装为可并行执行的Agent
    """

    def __init__(self,
                 npc_system: Any,
                 agent_id: str = None,
                 message_bus: NPCMessageBus = None):
        """
        初始化NPC Agent

        Args:
            npc_system: NPC行为系统实例
            agent_id: Agent唯一标识（默认使用NPC名称）
            message_bus: 消息总线实例
        """
        self._npc_system = npc_system
        self._agent_id = agent_id or getattr(npc_system, 'npc_name', str(uuid.uuid4())[:8])
        self._message_bus = message_bus

        self._state = AgentState.IDLE
        self._state_lock = threading.RLock()

        # 消息队列
        self._message_queue: asyncio.Queue = None
        self._pending_messages: List[Message] = []

        # 统计信息
        self._stats = {
            "ticks_processed": 0,
            "messages_received": 0,
            "errors": 0,
            "last_tick_time": None
        }

        # 暂停事件
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始为非暂停状态

        logger.info(f"NPC Agent 已创建: {self._agent_id}")

    @property
    def agent_id(self) -> str:
        """获取Agent ID"""
        return self._agent_id

    @property
    def state(self) -> AgentState:
        """获取Agent状态"""
        with self._state_lock:
            return self._state

    @property
    def npc_system(self) -> Any:
        """获取底层NPC系统"""
        return self._npc_system

    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()

    def _set_state(self, new_state: AgentState):
        """设置Agent状态"""
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            logger.debug(f"Agent [{self._agent_id}] 状态变更: {old_state.value} -> {new_state.value}")

    async def run(self, clock: SimulationClock, tick_interval: float = 1.0):
        """
        主运行循环

        Args:
            clock: 模拟时钟
            tick_interval: tick间隔（秒）
        """
        self._set_state(AgentState.RUNNING)
        self._message_queue = asyncio.Queue()

        logger.info(f"Agent [{self._agent_id}] 开始运行")

        try:
            while self._state == AgentState.RUNNING:
                # 检查暂停状态
                await self._pause_event.wait()

                if self._state != AgentState.RUNNING:
                    break

                # 处理一个tick
                game_time = clock.current_time
                await self.process_tick(game_time)

                # 等待下一个tick
                await asyncio.sleep(tick_interval)

        except asyncio.CancelledError:
            logger.info(f"Agent [{self._agent_id}] 被取消")
        except Exception as e:
            logger.error(f"Agent [{self._agent_id}] 运行错误: {e}")
            self._set_state(AgentState.ERROR)
            self._stats["errors"] += 1
            raise
        finally:
            if self._state != AgentState.ERROR:
                self._set_state(AgentState.STOPPED)
            logger.info(f"Agent [{self._agent_id}] 已停止")

    async def process_tick(self, game_time: GameTime) -> Dict[str, Any]:
        """
        处理一个时间单位

        Args:
            game_time: 当前游戏时间

        Returns:
            处理结果
        """
        result = {
            "agent_id": self._agent_id,
            "game_time": game_time.to_string(),
            "messages_processed": 0,
            "actions": []
        }

        try:
            # 处理待处理的消息
            messages_processed = await self._process_pending_messages()
            result["messages_processed"] = messages_processed

            # 让NPC系统进行自主决策
            if hasattr(self._npc_system, 'autonomous_tick'):
                actions = await self._npc_system.autonomous_tick(game_time)
                result["actions"] = actions or []

            self._stats["ticks_processed"] += 1
            self._stats["last_tick_time"] = datetime.now()

        except Exception as e:
            logger.error(f"Agent [{self._agent_id}] tick处理错误: {e}")
            self._stats["errors"] += 1
            result["error"] = str(e)

        return result

    async def _process_pending_messages(self) -> int:
        """处理待处理的消息"""
        processed = 0

        # 处理队列中的消息
        while not self._message_queue.empty():
            try:
                message = self._message_queue.get_nowait()
                await self._handle_message(message)
                processed += 1
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Agent [{self._agent_id}] 消息处理错误: {e}")

        return processed

    async def _handle_message(self, message: Message):
        """处理单个消息"""
        if hasattr(self._npc_system, 'handle_message'):
            await self._npc_system.handle_message(message)
        elif hasattr(self._npc_system, 'process_event'):
            event_data = {
                "type": message.message_type.value,
                "source": message.sender_id,
                "content": message.content,
                "metadata": message.metadata
            }
            await self._npc_system.process_event(event_data)

    async def receive_message(self, message: Message):
        """
        接收消息

        Args:
            message: 消息对象
        """
        if self._message_queue:
            await self._message_queue.put(message)
        else:
            self._pending_messages.append(message)

        self._stats["messages_received"] += 1
        logger.debug(f"Agent [{self._agent_id}] 收到消息: {message.message_type.value}")

    def pause(self):
        """暂停Agent"""
        self._pause_event.clear()
        self._set_state(AgentState.PAUSED)
        logger.info(f"Agent [{self._agent_id}] 已暂停")

    def resume(self):
        """恢复Agent"""
        self._pause_event.set()
        self._set_state(AgentState.RUNNING)
        logger.info(f"Agent [{self._agent_id}] 已恢复")

    def stop(self):
        """停止Agent"""
        self._set_state(AgentState.STOPPED)
        self._pause_event.set()  # 确保不会卡在暂停状态

    def get_state_snapshot(self) -> Dict[str, Any]:
        """获取Agent状态快照"""
        snapshot = {
            "agent_id": self._agent_id,
            "state": self._state.value,
            "stats": self._stats.copy()
        }

        # 添加NPC系统状态
        if hasattr(self._npc_system, 'current_location'):
            snapshot["location"] = self._npc_system.current_location
        if hasattr(self._npc_system, 'current_activity'):
            activity = self._npc_system.current_activity
            if hasattr(activity, 'value'):
                snapshot["activity"] = activity.value
            else:
                snapshot["activity"] = str(activity)
        if hasattr(self._npc_system, 'current_emotion'):
            emotion = self._npc_system.current_emotion
            if hasattr(emotion, 'value'):
                snapshot["emotion"] = emotion.value
            else:
                snapshot["emotion"] = str(emotion)

        return snapshot


class WorldSimulator(BaseNPCRegistry):
    """
    世界模拟器主类

    继承自 BaseNPCRegistry，实现统一的NPC注册接口。
    协调多个NPC Agent的并行执行。
    """

    def __init__(self,
                 initial_time: GameTime = None,
                 message_bus: NPCMessageBus = None):
        """
        初始化世界模拟器

        Args:
            initial_time: 初始游戏时间
            message_bus: 消息总线（可选，不提供则创建新的）
        """
        # 模拟时钟
        self._clock = SimulationClock(initial_time)

        # 事件调度器
        self._event_scheduler = EventScheduler(self._clock)

        # 消息总线
        self._message_bus = message_bus or NPCMessageBus(async_mode=False)

        # 注册的NPC Agents
        self._agents: Dict[str, NPCAgent] = {}
        self._agent_tasks: Dict[str, asyncio.Task] = {}

        # NPC元数据（用于接口兼容）
        self._npc_metadata: Dict[str, Dict[str, Any]] = {}

        # 运行状态
        self._running = False
        self._paused = False
        self._lock = threading.RLock()

        # 事件回调
        self._event_callbacks: List[Callable[[ScheduledEvent], Any]] = []

        # 统计信息
        self._stats = {
            "simulation_started": None,
            "simulation_stopped": None,
            "total_ticks": 0,
            "events_processed": 0
        }

        logger.info("世界模拟器已初始化")

    @property
    def clock(self) -> SimulationClock:
        """获取模拟时钟"""
        return self._clock

    @property
    def event_scheduler(self) -> EventScheduler:
        """获取事件调度器"""
        return self._event_scheduler

    @property
    def message_bus(self) -> NPCMessageBus:
        """获取消息总线"""
        return self._message_bus

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running

    @property
    def is_paused(self) -> bool:
        """是否已暂停"""
        return self._paused

    # ========================================================================
    # 接口标准方法实现 (NPCRegistryInterface)
    # ========================================================================

    def register_npc(
        self,
        npc_id: str,
        name: str = None,
        npc_type: str = "普通",
        initial_position: Optional[Position] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        注册NPC (实现 NPCRegistryInterface)

        Args:
            npc_id: NPC唯一标识
            name: NPC名称
            npc_type: NPC类型
            initial_position: 初始位置
            metadata: 额外元数据

        Returns:
            bool: 是否注册成功
        """
        with self._lock:
            if npc_id in self._agents:
                return False  # 已存在

            # 存储元数据
            self._npc_metadata[npc_id] = {
                "npc_id": npc_id,
                "name": name or npc_id,
                "npc_type": npc_type,
                "position": initial_position or Position(),
                "metadata": metadata or {},
                "registered_at": datetime.now()
            }

            logger.info(f"NPC已注册(接口): {npc_id}")
            return True

    def register_npc_agent(self, npc_system: Any, agent_id: str = None) -> 'NPCAgent':
        """
        注册NPC Agent到模拟器 (原有方法)

        Args:
            npc_system: NPC行为系统实例
            agent_id: Agent ID（可选）

        Returns:
            创建的NPCAgent实例
        """
        agent = NPCAgent(
            npc_system=npc_system,
            agent_id=agent_id,
            message_bus=self._message_bus
        )

        with self._lock:
            if agent.agent_id in self._agents:
                raise ValueError(f"Agent ID已存在: {agent.agent_id}")
            self._agents[agent.agent_id] = agent

            # 同步到接口元数据
            npc_name = getattr(npc_system, 'npc_name', agent.agent_id)
            self._npc_metadata[agent.agent_id] = {
                "npc_id": agent.agent_id,
                "name": npc_name,
                "npc_type": "Agent",
                "position": Position(),
                "metadata": {},
                "registered_at": datetime.now()
            }

        logger.info(f"NPC Agent已注册: {agent.agent_id}")
        return agent

    def unregister_npc(self, npc_id: str) -> bool:
        """
        取消注册NPC (实现 NPCRegistryInterface)

        Args:
            npc_id: NPC唯一标识

        Returns:
            bool: 是否注销成功
        """
        with self._lock:
            # 移除Agent (如果存在)
            if npc_id in self._agents:
                agent = self._agents[npc_id]
                agent.stop()

                # 取消任务
                if npc_id in self._agent_tasks:
                    self._agent_tasks[npc_id].cancel()
                    del self._agent_tasks[npc_id]

                del self._agents[npc_id]

            # 移除元数据
            if npc_id in self._npc_metadata:
                del self._npc_metadata[npc_id]
                logger.info(f"NPC已取消注册: {npc_id}")
                return True

        return False

    def get_npc(self, npc_id: str) -> Optional[NPCStateInterface]:
        """
        获取NPC (实现 NPCRegistryInterface)

        Args:
            npc_id: NPC唯一标识

        Returns:
            Optional[NPCStateInterface]: NPC状态接口
        """
        # 优先返回Agent（实现了更多功能）
        agent = self._agents.get(npc_id)
        if agent:
            return agent
        return None

    def get_all_npcs(self) -> List[NPCStateInterface]:
        """
        获取所有NPC (实现 NPCRegistryInterface)

        Returns:
            List[NPCStateInterface]: 所有NPC列表
        """
        with self._lock:
            return list(self._agents.values())

    def count_npcs(self) -> int:
        """
        获取NPC总数 (实现 NPCRegistryInterface)

        Returns:
            int: NPC数量
        """
        with self._lock:
            return len(self._agents)

    # ========================================================================
    # 原有方法 (保持向后兼容)
    # ========================================================================

    def get_agent(self, agent_id: str) -> Optional[NPCAgent]:
        """获取Agent"""
        return self._agents.get(agent_id)

    def get_all_agents(self) -> Dict[str, NPCAgent]:
        """获取所有Agent"""
        with self._lock:
            return dict(self._agents)

    async def run_simulation(self,
                             duration_hours: float = 24.0,
                             time_scale: float = 60.0,
                             tick_interval: float = 1.0) -> Dict[str, Any]:
        """
        运行模拟

        Args:
            duration_hours: 模拟持续时间（游戏小时）
            time_scale: 时间缩放（1秒现实 = N分钟游戏）
            tick_interval: tick间隔（秒）

        Returns:
            模拟结果
        """
        if self._running:
            raise RuntimeError("模拟已在运行中")

        self._running = True
        self._paused = False
        self._clock.time_scale = time_scale
        self._stats["simulation_started"] = datetime.now()

        logger.info(f"开始模拟: 持续 {duration_hours} 游戏小时, 时间缩放 1:{time_scale}")

        result = {
            "success": True,
            "start_time": self._clock.current_time.to_string(),
            "duration_hours": duration_hours,
            "agents": list(self._agents.keys()),
            "events_processed": 0,
            "errors": []
        }

        try:
            # 启动所有Agent任务
            for agent_id, agent in self._agents.items():
                task = asyncio.create_task(
                    agent.run(self._clock, tick_interval),
                    name=f"agent_{agent_id}"
                )
                self._agent_tasks[agent_id] = task

            # 计算结束时间
            start_game_time = self._clock.current_time
            end_minutes = int(duration_hours * 60)

            # 主模拟循环
            minutes_elapsed = 0
            while self._running and minutes_elapsed < end_minutes:
                if self._paused:
                    await asyncio.sleep(0.1)
                    continue

                # 推进时间
                minutes_per_tick = int(time_scale)
                self._clock.advance(minutes_per_tick)
                minutes_elapsed += minutes_per_tick

                # 处理调度事件
                triggered_events = await self._event_scheduler.process_scheduled_events()
                for event in triggered_events:
                    await self._dispatch_event(event)
                    result["events_processed"] += 1

                self._stats["total_ticks"] += 1

                # 等待下一个tick
                await asyncio.sleep(tick_interval)

            result["end_time"] = self._clock.current_time.to_string()

        except asyncio.CancelledError:
            result["success"] = False
            result["errors"].append("模拟被取消")
        except Exception as e:
            result["success"] = False
            result["errors"].append(str(e))
            logger.error(f"模拟错误: {e}")
        finally:
            # 停止所有Agent
            await self._stop_all_agents()
            self._running = False
            self._stats["simulation_stopped"] = datetime.now()
            self._stats["events_processed"] += result["events_processed"]

        logger.info(f"模拟结束: {result}")
        return result

    async def _stop_all_agents(self):
        """停止所有Agent"""
        for agent in self._agents.values():
            agent.stop()

        # 等待所有任务完成
        if self._agent_tasks:
            for task in self._agent_tasks.values():
                task.cancel()

            await asyncio.gather(*self._agent_tasks.values(), return_exceptions=True)
            self._agent_tasks.clear()

    async def _dispatch_event(self, event: ScheduledEvent):
        """分发事件给Agent"""
        message = Message(
            id=event.event_id,
            message_type=MessageType.WORLD_EVENT,
            sender_id="system",
            content=event.content,
            timestamp=datetime.now(),
            priority=MessagePriority.HIGH,
            target_ids=event.target_agents,
            metadata=event.metadata
        )

        # 广播给目标Agent或所有Agent
        if event.target_agents:
            targets = event.target_agents
        else:
            targets = list(self._agents.keys())

        for agent_id in targets:
            agent = self._agents.get(agent_id)
            if agent:
                await agent.receive_message(message)

        # 触发回调
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"事件回调错误: {e}")

    async def broadcast_event(self,
                              event_type: str,
                              content: str,
                              target_agents: List[str] = None,
                              metadata: Dict[str, Any] = None):
        """
        广播事件给所有NPC或指定NPC

        Args:
            event_type: 事件类型
            content: 事件内容
            target_agents: 目标Agent列表（空表示所有）
            metadata: 事件元数据
        """
        message = Message(
            id=str(uuid.uuid4())[:8],
            message_type=MessageType.WORLD_EVENT,
            sender_id="system",
            content=content,
            timestamp=datetime.now(),
            priority=MessagePriority.HIGH,
            target_ids=target_agents or [],
            metadata=metadata or {"event_type": event_type}
        )

        targets = target_agents if target_agents else list(self._agents.keys())

        for agent_id in targets:
            agent = self._agents.get(agent_id)
            if agent:
                await agent.receive_message(message)

        logger.info(f"事件已广播: {event_type} -> {targets}")

    def pause_simulation(self):
        """暂停模拟"""
        self._paused = True
        for agent in self._agents.values():
            agent.pause()
        logger.info("模拟已暂停")

    def resume_simulation(self):
        """恢复模拟"""
        self._paused = False
        for agent in self._agents.values():
            agent.resume()
        logger.info("模拟已恢复")

    def stop_simulation(self):
        """停止模拟"""
        self._running = False
        logger.info("模拟停止请求已发送")

    def pause_agent(self, agent_id: str) -> bool:
        """暂停单个Agent"""
        agent = self._agents.get(agent_id)
        if agent:
            agent.pause()
            return True
        return False

    def resume_agent(self, agent_id: str) -> bool:
        """恢复单个Agent"""
        agent = self._agents.get(agent_id)
        if agent:
            agent.resume()
            return True
        return False

    def get_all_npc_states(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有NPC状态

        Returns:
            NPC状态字典
        """
        states = {}
        for agent_id, agent in self._agents.items():
            states[agent_id] = agent.get_state_snapshot()
        return states

    def get_simulation_stats(self) -> Dict[str, Any]:
        """获取模拟统计信息"""
        stats = self._stats.copy()
        stats["current_time"] = self._clock.current_time.to_string()
        stats["agents_count"] = len(self._agents)
        stats["running"] = self._running
        stats["paused"] = self._paused

        # 汇总Agent统计
        agent_stats = {}
        for agent_id, agent in self._agents.items():
            agent_stats[agent_id] = agent.stats
        stats["agent_stats"] = agent_stats

        return stats

    def add_event_callback(self, callback: Callable[[ScheduledEvent], Any]):
        """添加事件回调"""
        self._event_callbacks.append(callback)

    def remove_event_callback(self, callback: Callable[[ScheduledEvent], Any]):
        """移除事件回调"""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)


# 便捷函数
def create_world_simulator(initial_time: GameTime = None) -> WorldSimulator:
    """
    创建世界模拟器实例

    Args:
        initial_time: 初始游戏时间

    Returns:
        WorldSimulator实例
    """
    return WorldSimulator(initial_time=initial_time)


async def run_simple_simulation(
    npc_systems: List[Any],
    duration_hours: float = 24.0,
    time_scale: float = 60.0
) -> Dict[str, Any]:
    """
    运行简单模拟

    Args:
        npc_systems: NPC系统列表
        duration_hours: 模拟持续时间（游戏小时）
        time_scale: 时间缩放

    Returns:
        模拟结果
    """
    simulator = WorldSimulator()

    # 注册所有NPC
    for npc_system in npc_systems:
        simulator.register_npc(npc_system)

    # 运行模拟
    result = await simulator.run_simulation(
        duration_hours=duration_hours,
        time_scale=time_scale
    )

    return result
