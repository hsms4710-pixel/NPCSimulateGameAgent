"""
NPC 基础类定义

包含 NPCBehaviorSystem 的核心初始化和基础方法：
- __init__: 初始化
- 属性访问方法
- 持久化恢复
- 目标初始化
- 空间系统和消息总线集成
"""

import random
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from backend.deepseek_client import DeepSeekClient
from npc_core.npc_persistence import NPCPersistence, NPCTask
from world_simulator.world_clock import get_world_clock
from core_types import NPCAction, Emotion

from npc_optimization import (
    ContextCompressor,
    BehaviorDecisionTree,
    PromptTemplates,
    MemoryManager,
    RAGMemorySystem,
    FourLevelDecisionMaker,
    MemoryLayerManager,
)
from npc_optimization.react_tools import NPCToolRegistry, ReActAgent
from npc_optimization.spatial_system import get_spatial_system
from npc_optimization.message_bus import get_message_bus, MessageType, MessagePriority
from npc_optimization.unified_tools import UnifiedToolRegistry
from npc_optimization.world_event_manager import WorldEventManager
from npc_optimization.reflection_flow import ReflectionFlowManager

# 全局 WorldEventManager 单例
_global_world_event_manager: Optional[WorldEventManager] = None


def get_world_event_manager() -> WorldEventManager:
    """获取全局 WorldEventManager 单例"""
    global _global_world_event_manager
    if _global_world_event_manager is None:
        _global_world_event_manager = WorldEventManager()
        _global_world_event_manager.start()
    return _global_world_event_manager

from .data_models import Memory, Goal, Relationship
from .environment import EnvironmentPerception, NeedSystem

logger = logging.getLogger(__name__)


class NPCBehaviorSystemBase:
    """NPC复杂行为系统 - 基础类"""

    def __init__(self, npc_config: Dict[str, Any], deepseek_client: DeepSeekClient):
        self.config = npc_config
        self.llm_client = deepseek_client
        self.npc_name = npc_config['name']

        # 时间和位置
        self.world_clock = get_world_clock()
        self.current_location = self.config.get("default_location", "住宅")

        # 集成空间系统
        self.spatial_system = get_spatial_system()
        self._register_to_spatial_system()

        # 集成 WorldEventManager（坐标广播系统）
        self.world_event_manager = get_world_event_manager()

        # 待处理事件队列 - 支持延迟事件响应
        self.pending_events: List[Dict[str, Any]] = []
        # 移动目标 - 当前NPC要移动到的位置
        self.movement_destination: Optional[str] = None

        # 集成消息总线 - 用于NPC间通信
        self.message_bus = get_message_bus()
        self._subscribe_to_messages()

        # 持久化存储
        self.persistence = NPCPersistence(self.npc_name)

        # 新增：自主性系统
        self.need_system = NeedSystem()
        self.environment_perception = EnvironmentPerception(self.world_clock)

        # 优化模块：上下文压缩、行为决策树、记忆管理、ReAct工具、RAG记忆
        self.context_compressor = ContextCompressor(max_tokens=1000)
        self.behavior_tree = BehaviorDecisionTree(npc_config)
        self.prompt_templates = PromptTemplates()
        self.memory_manager = MemoryManager(llm_client=deepseek_client)
        self.rag_memory = RAGMemorySystem()
        self.tool_registry = NPCToolRegistry(self)
        self.react_agent = ReActAgent(deepseek_client, self.tool_registry)

        # 初始化三层记忆管理器（热/温/冷记忆）
        self.memory_layer_manager = MemoryLayerManager(self.npc_name)
        self.memory_layer_manager.start()  # 启动后台归档线程

        # 初始化统一工具注册表（供ReAct模式使用）
        self.unified_tool_registry = UnifiedToolRegistry(npc_system=self)

        # 初始化四级决策系统（新的核心决策引擎）
        # 将 behavior_tree 传入 L1，使其从人物卡读取作息规则
        self.decision_maker = FourLevelDecisionMaker(
            npc_config=npc_config,
            llm_client=deepseek_client,
            tool_registry=self.tool_registry,
            unified_tool_registry=self.unified_tool_registry,
            behavior_tree=self.behavior_tree
        )

        # 初始化RAG记忆系统（从现有记忆加载）
        self._initialize_rag_memory()

        # 从world_lore导入世界观（如果可用）
        try:
            from world_simulator.world_lore import WORLD_LORE
            self.prompt_templates.world_lore = WORLD_LORE
        except ImportError:
            pass

        # 自主行为循环控制 - 默认启用
        self.autonomous_mode = False  # 初始为False，在初始化完成后启动
        self.autonomous_thread = None
        self.autonomous_stop_event = threading.Event()

        # GUI更新回调（由GUI设置）
        self.gui_update_callback = None

        # 从持久化数据恢复状态
        self._restore_from_persistence()

        # 初始化RAG记忆系统（在恢复记忆后）
        self._initialize_rag_memory()

        # 决策历史（短期内存）
        self.decision_history: List[Dict[str, Any]] = []

        # 初始化反思系统（在恢复状态后启动，确保 memory_layer_manager 已就绪）
        self.reflection_manager = ReflectionFlowManager(
            llm_client=deepseek_client,
            memory_layer_manager=self.memory_layer_manager,
            npc_profile=npc_config
        )
        self.reflection_manager.start()

        # 自动启动自主行为
        try:
            self._start_autonomous_immediately()
        except Exception as e:
            print(f"警告: NPC {self.npc_name} 自主行为启动失败: {e}")
            self.autonomous_mode = False

    def _initialize_rag_memory(self):
        """初始化RAG记忆系统（从现有记忆加载）"""
        try:
            # 从现有记忆加载到RAG系统
            if hasattr(self, 'memories') and self.memories:
                for i, memory in enumerate(self.memories):
                    memory_id = f"mem_{i}_{hash(memory.content)}"
                    self.rag_memory.add_memory(
                        memory_id=memory_id,
                        content=memory.content,
                        importance=memory.importance,
                        tags=memory.tags if hasattr(memory, 'tags') else [],
                        timestamp=memory.timestamp if isinstance(memory.timestamp, datetime) else datetime.now()
                    )
        except Exception as e:
            print(f"RAG记忆初始化失败: {e}")

    def _register_to_spatial_system(self):
        """将NPC注册到空间系统"""
        # 根据职业确定初始位置
        profession_locations = {
            "铁匠": "铁匠铺",
            "酒馆老板": "酒馆",
            "牧师": "圣光教堂",
            "农民": "农田",
            "商人": "杂货店",
        }

        profession = self.config.get("profession", "")
        initial_location = profession_locations.get(profession, "中心广场")

        # 注册到空间系统
        self.spatial_system.register_npc(self.npc_name, initial_location)
        self.current_location = initial_location

    def move_to(self, destination: str) -> bool:
        """
        命令NPC移动到指定位置，同步更新三套位置系统

        Args:
            destination: 目标位置名称

        Returns:
            是否成功开始移动
        """
        if self.spatial_system.move_npc(self.npc_name, destination):
            old_location = self.current_location
            self.current_location = destination
            self.movement_destination = destination
            self._change_activity(NPCAction.TRAVEL)

            # 同步更新消息总线的位置（区域名称）
            self.message_bus.update_npc_location(self.npc_name, zone=destination)

            # 同步更新 WorldEventManager 的坐标位置
            # 使用区域名称的哈希值作为简化坐标（实际项目可从地图数据读取）
            coord_x = float(hash(destination) % 1000)
            coord_y = float((hash(destination) >> 10) % 1000)
            self.world_event_manager.update_npc_position(self.npc_name, (coord_x, coord_y))

            logger.info(f"NPC {self.npc_name} 从 {old_location} 移动到 {destination}")
            return True
        return False

    def _subscribe_to_messages(self):
        """订阅消息总线上的相关消息"""
        # 订阅世界事件、区域事件和NPC通信
        self.message_bus.subscribe(
            subscriber_id=self.npc_name,
            message_types=[
                MessageType.WORLD_EVENT,
                MessageType.ZONE_EVENT,
                MessageType.NPC_SPEECH,
                MessageType.GOSSIP
            ],
            callback=self._on_message_received,
            filter_zone=self.current_location
        )

    def _on_message_received(self, message):
        """处理收到的消息"""
        # 忽略自己发送的消息
        if message.sender_id == self.npc_name:
            return

        # 检查是否在同一区域
        if message.zone and message.zone != self.current_location:
            return

        logger.info(f"NPC {self.npc_name} 收到消息: [{message.message_type.value}] from {message.sender_id}")

        # 将消息转化为事件并添加到待处理队列
        self.add_pending_event(
            event_content=message.content,
            event_type=f"message_{message.message_type.value}",
            delay_hours=0.0,  # 立即处理
            event_location=message.zone or self.current_location
        )

    def broadcast_to_nearby(self, message_content: str, message_type: MessageType = MessageType.NPC_SPEECH,
                           priority: MessagePriority = MessagePriority.NORMAL):
        """
        向附近的NPC广播消息

        Args:
            message_content: 消息内容
            message_type: 消息类型
            priority: 消息优先级
        """
        self.message_bus.publish_event(
            sender_id=self.npc_name,
            message_type=message_type,
            content=f"{self.npc_name}: {message_content}",
            zone=self.current_location,
            priority=priority,
            metadata={
                "npc_name": self.npc_name,
                "location": self.current_location,
                "action": self.current_activity.value if self.current_activity else "unknown"
            }
        )
        logger.info(f"NPC {self.npc_name} 广播消息: {message_content[:50]}...")

    def notify_others_about_event(self, event: Dict[str, Any]):
        """
        通知其他NPC关于某个事件

        Args:
            event: 事件信息
        """
        event_content = event.get("content", "")
        event_location = event.get("location", self.current_location)

        # 根据事件严重程度决定消息优先级
        impact_score = event.get("impact_score", 0)
        if impact_score > 80:
            priority = MessagePriority.URGENT
        elif impact_score > 60:
            priority = MessagePriority.HIGH
        else:
            priority = MessagePriority.NORMAL

        # 构建通知消息
        notification = f"注意！{event_location}发生了：{event_content}"

        self.broadcast_to_nearby(
            message_content=notification,
            message_type=MessageType.GOSSIP,
            priority=priority
        )

    def add_pending_event(self, event_content: str, event_type: str,
                          delay_hours: float = 0.0, event_location: str = None):
        """
        添加待处理事件到队列

        Args:
            event_content: 事件内容
            event_type: 事件类型
            delay_hours: 延迟处理时间（小时）
            event_location: 事件发生位置
        """
        process_time = self.world_clock.current_time + timedelta(hours=delay_hours)

        self.pending_events.append({
            "content": event_content,
            "type": event_type,
            "created_at": datetime.now(),
            "process_at": process_time,
            "location": event_location or self.current_location,
            "processed": False
        })

    def _restore_from_persistence(self):
        """从持久化存储恢复NPC状态"""
        # 持久化系统已经在初始化时加载了数据
        # 这里我们需要将持久化数据转换为运行时状态

        # 初始化目标列表（确保总是存在）
        self.short_term_goals: List[Goal] = []
        self.long_term_goals: List[Goal] = []
        self.memories: List[Memory] = []
        self.knowledge_base: Dict[str, Any] = {}
        self.relationships: Dict[str, Relationship] = {}

        # 初始化其他属性，确保总是存在
        self.current_emotion = Emotion.CALM
        self.energy = 1.0  # 使用新的能量字段 (0.0-1.0)
        self.current_activity = NPCAction.SLEEP
        self.activity_start_time = datetime.now()

        # 同步当前活动到持久化状态
        self.persistence.current_state.current_activity = self.current_activity.value
        self.persistence.current_state.is_sleeping = (self.current_activity == NPCAction.SLEEP)

        # 从持久化任务中恢复目标
        for task in self.persistence.tasks.values():
            # 转换deadline字符串为datetime对象
            deadline = None
            if task.deadline and isinstance(task.deadline, str):
                try:
                    deadline = datetime.fromisoformat(task.deadline)
                except ValueError:
                    deadline = None

            if task.task_type == "short_term":
                goal = Goal(
                    description=task.description,
                    priority=task.priority,
                    progress=task.progress,
                    deadline=deadline
                )
                goal.status = task.status
                self.short_term_goals.append(goal)
            elif task.task_type == "long_term":
                goal = Goal(
                    description=task.description,
                    priority=task.priority,
                    progress=task.progress,
                    deadline=deadline
                )
                goal.status = task.status
                self.long_term_goals.append(goal)

        # 如果持久化中没有目标（第一次创建），从配置中初始化
        if not self.persistence.tasks:
            self._initialize_goals_from_config()

        # 创建一个任务ID到goals对象的映射，用于同步更新
        self._task_id_to_goal = {}

    def start_autonomous_behavior(self):
        """启动自主行为循环"""
        if self.autonomous_mode:
            return  # 已经在运行

        self.autonomous_mode = True
        self.autonomous_stop_event.clear()
        self.autonomous_thread = threading.Thread(target=self._autonomous_behavior_loop)
        self.autonomous_thread.daemon = True
        self.autonomous_thread.start()

    def _get_activity_value(self) -> str:
        """安全地获取当前活动的字符串值"""
        if self.current_activity is None:
            return "空闲"
        if isinstance(self.current_activity, str):
            return self.current_activity
        if hasattr(self.current_activity, 'value'):
            return self.current_activity.value
        return str(self.current_activity)

    def _start_autonomous_immediately(self):
        """立即启动自主行为（用于初始化）"""
        self.autonomous_mode = True
        self.autonomous_stop_event.clear()
        self.autonomous_thread = threading.Thread(target=self._autonomous_behavior_loop)
        self.autonomous_thread.daemon = True
        self.autonomous_thread.start()

    def stop_autonomous_behavior(self):
        """停止自主行为循环"""
        self.autonomous_mode = False
        if self.autonomous_stop_event:
            self.autonomous_stop_event.set()
        if self.autonomous_thread and self.autonomous_thread.is_alive():
            self.autonomous_thread.join(timeout=5)

    def _autonomous_behavior_loop(self):
        """自主行为主循环 - 由子类实现"""
        raise NotImplementedError("子类必须实现 _autonomous_behavior_loop 方法")

    def _change_activity(self, new_activity: NPCAction):
        """改变当前活动"""
        old_activity = self.current_activity
        self.current_activity = new_activity
        self.activity_start_time = datetime.now()

        # 安全获取活动值
        def get_value(activity):
            if activity is None:
                return "空闲"
            if isinstance(activity, str):
                return activity
            if hasattr(activity, 'value'):
                return activity.value
            return str(activity)

        # 更新持久化状态 - 使用新字段
        activity_value = get_value(new_activity)
        self.persistence.current_state.current_activity = activity_value
        self.persistence.current_state.is_sleeping = (activity_value in ["睡觉", "rest", "休息"])

        # 记录活动变化
        self.decision_history.append({
            'timestamp': datetime.now(),
            'type': 'activity_change',
            'old_activity': get_value(old_activity),
            'new_activity': get_value(new_activity),
            'reason': 'autonomous_decision'
        })

    def sync_goals_to_persistence(self):
        """将goals的变化同步到持久化系统"""
        for task_id, goal in self._task_id_to_goal.items():
            if task_id in self.persistence.tasks:
                task = self.persistence.tasks[task_id]
                # 同步状态变化
                if hasattr(goal, 'status') and goal.status != task.status:
                    self.persistence.update_task(task_id, status=goal.status)
                if hasattr(goal, 'progress') and goal.progress != task.progress:
                    self.persistence.update_task(task_id, progress=goal.progress)

    def _initialize_goals_from_config(self):
        """从配置文件初始化目标（仅在第一次创建时调用）"""
        if "goals" not in self.config:
            return

        # 短期目标
        for goal_text in self.config["goals"].get("short_term", []):
            goal = Goal(
                description=goal_text,
                priority=random.randint(3, 8),
                progress=random.uniform(0, 0.3)
            )
            self.short_term_goals.append(goal)

            # 同时添加到持久化系统
            self.persistence.create_task(
                description=goal_text,
                task_type="short_term",
                priority=goal.priority
            )

        # 长期目标
        for goal_text in self.config["goals"].get("long_term", []):
            goal = Goal(
                description=goal_text,
                priority=random.randint(5, 10),
                deadline=self.world_clock.current_time + timedelta(days=random.randint(30, 365)),
                progress=random.uniform(0, 0.1)
            )
            self.long_term_goals.append(goal)

            # 同时添加到持久化系统
            self.persistence.create_task(
                description=goal_text,
                task_type="long_term",
                priority=goal.priority,
                deadline=goal.deadline.isoformat() if goal.deadline else None
            )
