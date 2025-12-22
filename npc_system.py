import json
import time
import random
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, field
from deepseek_client import DeepSeekClient
from world_lore import NPC_TEMPLATES, ENVIRONMENTAL_EVENTS

logger = logging.getLogger(__name__)
from npc_persistence import NPCPersistence, NPCEvent, NPCTask
from world_clock import get_world_clock
from constants import NPCAction, ReasoningMode, Emotion  # 从统一的常量文件导入
from npc_optimization import (
    ContextCompressor,
    BehaviorDecisionTree,
    PromptTemplates,
    MemoryManager,
    RAGMemorySystem,
    FourLevelDecisionMaker
)
from npc_optimization.react_tools import NPCToolRegistry, ReActAgent

class Memory:
    """记忆数据类"""
    content: str
    emotional_impact: int  # -10 到 +10
    importance: int  # 1-10
    timestamp: datetime
    tags: List[str] = field(default_factory=list)
    related_npcs: List[str] = field(default_factory=list)

@dataclass
class Goal:
    """目标数据类"""
    description: str
    priority: int  # 1-10
    deadline: Optional[datetime] = None
    progress: float = 0.0  # 0.0-1.0
    sub_goals: List[str] = field(default_factory=list)
    status: str = "active"  # active, completed, failed, paused

@dataclass
class Relationship:
    """人际关系数据类"""
    npc_name: str
    affection: int  # -100 到 +100
    trust: int  # 0-100
    interactions_count: int = 0
    last_interaction: Optional[datetime] = None
    relationship_type: str = "acquaintance"  # friend, family, enemy, etc.

@dataclass
class NeedState:
    """需求状态数据类"""
    hunger: float = 0.0  # 饥饿程度 0-1
    fatigue: float = 0.0  # 疲劳程度 0-1
    social: float = 0.0  # 社交需求 0-1
    security: float = 0.0  # 安全需求 0-1
    achievement: float = 0.0  # 成就需求 0-1
    last_updated: datetime = field(default_factory=datetime.now)

class EnvironmentPerception:
    """环境感知系统"""

    def __init__(self, world_clock):
        self.world_clock = world_clock
        self.current_weather = "clear"
        self.current_location = "home"
        self.nearby_entities = []
        self.last_updated = datetime.now()

    def update_perception(self):
        """更新环境感知"""
        self.current_weather = self._get_current_weather()
        self.nearby_entities = self._scan_nearby_entities()
        self.last_updated = datetime.now()

    def _get_current_weather(self) -> str:
        """获取当前天气（简化版）"""
        # 基于月份和随机性生成天气
        month = self.world_clock.current_time.month
        hour = self.world_clock.current_time.hour

        # 冬季天气
        if month in [12, 1, 2]:
            weather_options = ["snow", "clear", "cloudy", "storm"]
            weights = [0.3, 0.3, 0.3, 0.1]
        # 春季天气
        elif month in [3, 4, 5]:
            weather_options = ["rain", "clear", "cloudy", "storm"]
            weights = [0.2, 0.4, 0.3, 0.1]
        # 夏季天气
        elif month in [6, 7, 8]:
            weather_options = ["clear", "rain", "storm", "cloudy"]
            weights = [0.5, 0.2, 0.1, 0.2]
        # 秋季天气
        else:
            weather_options = ["clear", "rain", "cloudy", "fog"]
            weights = [0.4, 0.2, 0.3, 0.1]

        # 夜间调整
        if hour < 6 or hour > 22:
            weights = [w * 0.7 for w in weights]  # 夜间天气更稳定

        return random.choices(weather_options, weights=weights)[0]

    def _scan_nearby_entities(self) -> List[Dict[str, Any]]:
        """扫描附近实体（简化版）"""
        # 这里可以扩展为更复杂的实体检测逻辑
        # 目前返回一些示例实体
        entities = []

        # 基于时间添加一些实体
        hour = self.world_clock.current_time.hour
        if 6 <= hour <= 9:  # 早晨
            entities.append({"type": "person", "name": "村民", "distance": 10})
        elif 18 <= hour <= 22:  # 晚上
            entities.append({"type": "person", "name": "守卫", "distance": 20})

        # 随机添加一些环境实体
        if random.random() < 0.1:  # 10%概率
            entities.append({"type": "animal", "name": "野兔", "distance": random.randint(5, 50)})

        return entities

    def assess_safety(self) -> float:
        """评估当前环境安全性 0-1"""
        safety_score = 1.0

        # 天气影响
        if self.current_weather in ['storm', 'heavy_rain', 'snow']:
            safety_score *= 0.7

        # 时间影响
        hour = self.world_clock.current_time.hour
        if 0 <= hour <= 5:
            safety_score *= 0.8  # 深夜不太安全

        # 附近实体影响
        for entity in self.nearby_entities:
            if entity.get('type') == 'threat':
                safety_score *= 0.5

        return max(0.0, min(1.0, safety_score))

class NeedSystem:
    """需求管理系统"""

    def __init__(self):
        self.needs = NeedState()

    def update_needs(self, time_passed_minutes: float, current_activity: NPCAction):
        """根据时间和活动更新需求"""
        # 时间流逝导致的需求增加
        base_rate = time_passed_minutes / 60.0  # 转换为小时

        # 基础需求增长
        self.needs.hunger = min(1.0, self.needs.hunger + base_rate * 0.15)  # 每小时增加15%
        self.needs.fatigue = min(1.0, self.needs.fatigue + base_rate * 0.12)  # 每小时增加12%
        self.needs.social = min(1.0, self.needs.social + base_rate * 0.08)  # 每小时增加8%
        self.needs.security = min(1.0, self.needs.security + base_rate * 0.05)  # 每小时增加5%

        # 活动对需求的影响
        if current_activity == NPCAction.EAT:
            self.needs.hunger = max(0.0, self.needs.hunger - base_rate * 0.8)  # 吃饭减少饥饿
        elif current_activity == NPCAction.SLEEP:
            self.needs.fatigue = max(0.0, self.needs.fatigue - base_rate * 0.6)  # 睡觉减少疲劳
            self.needs.hunger = min(1.0, self.needs.hunger + base_rate * 0.05)  # 睡觉时会饿
        elif current_activity == NPCAction.SOCIALIZE:
            self.needs.social = max(0.0, self.needs.social - base_rate * 0.4)  # 社交减少社交需求
        elif current_activity == NPCAction.WORK:
            self.needs.fatigue = min(1.0, self.needs.fatigue + base_rate * 0.2)  # 工作增加疲劳
            self.needs.achievement = max(0.0, self.needs.achievement - base_rate * 0.1)  # 工作满足成就需求
        elif current_activity == NPCAction.REST:
            self.needs.fatigue = max(0.0, self.needs.fatigue - base_rate * 0.3)  # 休息减少疲劳

        self.needs.last_updated = datetime.now()

    def get_most_urgent_need(self) -> tuple[str, float]:
        """获取最紧急的需求"""
        need_levels = {
            'hunger': self.needs.hunger,
            'fatigue': self.needs.fatigue,
            'social': self.needs.social,
            'security': self.needs.security,
            'achievement': self.needs.achievement
        }
        return max(need_levels.items(), key=lambda x: x[1])

    def get_need_satisfaction_level(self) -> float:
        """获取整体需求满足度 0-1"""
        total_needs = (self.needs.hunger + self.needs.fatigue +
                      self.needs.social + self.needs.security + self.needs.achievement)
        return 1.0 - (total_needs / 5.0)  # 平均值取反

class NPCBehaviorSystem:
    """NPC复杂行为系统 - 基于持久化的事件驱动架构"""

    def __init__(self, npc_config: Dict[str, Any], deepseek_client: DeepSeekClient):
        self.config = npc_config
        self.llm_client = deepseek_client
        self.npc_name = npc_config['name']

        # 时间和位置
        self.world_clock = get_world_clock()
        self.current_location = self.config.get("default_location", "住宅")

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
        
        # 初始化四级决策系统（新的核心决策引擎）
        self.decision_maker = FourLevelDecisionMaker(
            npc_config=npc_config,
            llm_client=deepseek_client,
            tool_registry=self.tool_registry
        )
        
        # 初始化RAG记忆系统（从现有记忆加载）
        self._initialize_rag_memory()
        
        # 从world_lore导入世界观（如果可用）
        try:
            from world_lore import WORLD_LORE
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
        self.energy_level = 100
        self.current_activity = NPCAction.SLEEP
        self.activity_start_time = datetime.now()

        # 同步primary_state
        self.persistence.current_state.primary_state = self.current_activity.value

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
        """自主行为主循环"""
        evaluation_interval = 30  # 每30秒评估一次

        while not self.autonomous_stop_event.is_set():
            try:
                # 更新环境感知
                self.environment_perception.update_perception()

                # 更新需求状态
                time_passed = evaluation_interval / 60.0  # 转换为分钟
                self.need_system.update_needs(time_passed, self.current_activity)

                # 实时状态评估
                self._assess_current_state()

                # 优先检查：如果有活跃的事件响应任务，但当前活动不合适，立即切换
                current_task = self.persistence.current_task
                if current_task and current_task.task_type == "event_response" and current_task.status == "active":
                    # 检查当前活动是否适合处理这个任务
                    appropriate_activity = self._analyze_task_and_select_activity(current_task)
                    if appropriate_activity != self.current_activity:
                        # 立即切换到合适的活动
                        self._change_activity(appropriate_activity)
                
                # 使用行为决策树判断是否需要改变活动（优化：减少LLM调用）
                current_hour = self.world_clock.current_time.hour
                needs_dict = {
                    "hunger": self.need_system.needs.hunger,
                    "fatigue": self.need_system.needs.fatigue,
                    "social": self.need_system.needs.social
                }
                
                current_task_dict = None
                if current_task:
                    current_task_dict = {
                        "priority": current_task.priority,
                        "description": current_task.description
                    }
                
                # 先尝试规则决策（日常行为，从人物卡读取）
                routine_action = self.behavior_tree.decide_routine_behavior(
                    current_hour=current_hour,
                    energy_level=self.energy_level,
                    needs=needs_dict,
                    current_task=current_task_dict
                )
                
                if routine_action and routine_action != self.current_activity:
                    # 规则决策成功，切换活动（不需要LLM）
                    self._change_activity(routine_action)
                elif self._should_change_activity():
                    # 规则决策失败，使用LLM决策（复杂情况）
                    new_activity = self._select_new_activity()
                    if new_activity != self.current_activity:
                        self._change_activity(new_activity)

                # 执行当前活动（这会更新任务进度）
                self._execute_current_activity()
                
                # 通知GUI更新（如果设置了回调）
                if self.gui_update_callback:
                    try:
                        self.gui_update_callback()
                    except Exception as e:
                        print(f"GUI更新回调失败: {e}")

                # 定期输出状态摘要（每3次评估一次）
                if hasattr(self, '_evaluation_count'):
                    self._evaluation_count += 1
                else:
                    self._evaluation_count = 1

                # 定期状态检查（可选的调试功能）
                pass

            except Exception as e:
                # 记录错误但不中断循环
                import traceback
                print(f"自主行为循环错误: {e}")
                traceback.print_exc()

            # 等待下一次评估
            self.autonomous_stop_event.wait(evaluation_interval)
    
    def _cleanup_memories(self):
        """定期清理记忆"""
        try:
            # 将记忆转换为字典格式
            memories_dict = [
                {
                    "id": f"mem_{i}",
                    "content": m.content,
                    "importance": m.importance,
                    "tags": m.tags if hasattr(m, 'tags') else [],
                    "timestamp": m.timestamp.isoformat() if isinstance(m.timestamp, datetime) else str(m.timestamp)
                }
                for i, m in enumerate(self.memories)
            ]
            
            # 将事件转换为字典格式
            events_dict = [
                {
                    "id": f"evt_{i}",
                    "event_type": e.event_type,
                    "content": e.content,
                    "impact_score": e.impact_score,
                    "timestamp": e.timestamp
                }
                for i, e in enumerate(self.persistence.event_history)
            ]
            
            # 执行清理
            cleanup_result = self.memory_manager.cleanup_memories(memories_dict, events_dict)
            
            # 更新记忆列表
            self.memories = [Memory(**m) for m in cleanup_result["kept"]]
            
            # 创建情景（如果有归档的事件）
            if cleanup_result["archived"]:
                episodes = self.memory_manager.create_episodes_from_events(
                    cleanup_result["archived"],
                    time_window_hours=24
                )
                # 可以将情景存储到持久化系统
            
            print(f"[记忆清理] 保留{len(cleanup_result['kept'])}个，压缩{len(cleanup_result['compressed'])}个，归档{len(cleanup_result['archived'])}个，删除{len(cleanup_result['deleted'])}个")
            
        except Exception as e:
            print(f"记忆清理失败: {e}")

    def _assess_current_state(self):
        """评估当前状态"""
        # 检查需求紧急程度
        urgent_need, need_level = self.need_system.get_most_urgent_need()

        # 检查环境安全性
        safety_level = self.environment_perception.assess_safety()

        # 检查当前活动是否仍然合适
        activity_appropriateness = self._evaluate_activity_appropriateness()

        # 记录状态评估结果
        self.decision_history.append({
            'timestamp': datetime.now(),
            'type': 'state_assessment',
            'urgent_need': urgent_need,
            'need_level': need_level,
            'safety_level': safety_level,
            'current_activity': self.current_activity.value,
            'activity_appropriateness': activity_appropriateness
        })

        # 保持决策历史在合理长度
        if len(self.decision_history) > 50:
            self.decision_history = self.decision_history[-50:]


    def _change_activity(self, new_activity: NPCAction):
        """改变当前活动"""
        old_activity = self.current_activity
        self.current_activity = new_activity
        self.activity_start_time = datetime.now()

        # 更新持久化状态
        self.persistence.current_state.primary_state = new_activity.value

        # 记录活动变化
        self.decision_history.append({
            'timestamp': datetime.now(),
            'type': 'activity_change',
            'old_activity': old_activity.value,
            'new_activity': new_activity.value,
            'reason': 'autonomous_decision'
        })

    def _execute_current_activity(self):
        """执行当前活动"""
        activity_duration = (datetime.now() - self.activity_start_time).total_seconds() / 60  # 分钟

        # 如果有当前任务，使用LLM决策更新任务进度
        if self.persistence.current_task and self.persistence.current_task.status == "active":
            # 计算时间差（自主行为循环每30秒执行一次，约0.008小时）
            time_diff = 0.008  # 约30秒
            self._update_task_progress(time_diff)

        # 基于活动类型更新状态
        if self.current_activity == NPCAction.WORK:
            # 工作会消耗能量，积累疲劳
            self.energy_level = max(0, self.energy_level - 0.5)
            self.need_system.needs.fatigue = min(1.0, self.need_system.needs.fatigue + 0.01)
        elif self.current_activity == NPCAction.REST:
            # 休息恢复能量
            self.energy_level = min(100, self.energy_level + 1.0)
            self.need_system.needs.fatigue = max(0.0, self.need_system.needs.fatigue - 0.02)
        elif self.current_activity == NPCAction.SLEEP:
            # 睡觉大幅恢复
            self.energy_level = min(100, self.energy_level + 2.0)
            self.need_system.needs.fatigue = max(0.0, self.need_system.needs.fatigue - 0.05)
        elif self.current_activity == NPCAction.EAT:
            # 吃饭恢复饥饿
            self.need_system.needs.hunger = max(0.0, self.need_system.needs.hunger - 0.1)
        elif self.current_activity == NPCAction.SOCIALIZE:
            # 社交满足社交需求
            self.need_system.needs.social = max(0.0, self.need_system.needs.social - 0.05)
        elif self.current_activity == NPCAction.OBSERVE:
            # 普通的观察活动，轻微消耗能量
            if not (self.persistence.current_task and self.persistence.current_task.status == "active"):
                self.energy_level = max(0, self.energy_level - 0.1)
        elif self.current_activity == NPCAction.HELP_OTHERS:
            # 普通的帮助活动，消耗一定能量但满足社交需求
            if not (self.persistence.current_task and self.persistence.current_task.status == "active"):
                self.energy_level = max(0, self.energy_level - 0.2)
                self.need_system.needs.social = max(0.0, self.need_system.needs.social - 0.03)

    def _evaluate_activity_appropriateness(self) -> float:
        """评估当前活动的合适程度 0-1"""
        appropriateness = 1.0

        # 基于时间评估
        current_hour = self.world_clock.current_time.hour
        if self.current_activity == NPCAction.SLEEP:
            if not (22 <= current_hour or current_hour <= 6):
                appropriateness *= 0.3  # 白天睡觉不合适
        elif self.current_activity == NPCAction.WORK:
            if not (9 <= current_hour <= 18):
                appropriateness *= 0.5  # 非工作时间工作

        # 基于需求评估
        urgent_need, need_level = self.need_system.get_most_urgent_need()
        if need_level > 0.7:
            # 如果有紧急需求，当前活动可能不合适
            appropriateness *= 0.7

        return appropriateness

    def _is_time_for_routine_change(self, current_hour: int) -> bool:
        """检查是否到了常规活动转换时间"""
        # 定义常规活动转换时间点
        routine_changes = [
            (6, "wake_up"),
            (9, "start_work"),
            (12, "lunch"),
            (18, "end_work"),
            (20, "dinner"),
            (22, "bedtime")
        ]

        for hour, routine in routine_changes:
            if current_hour == hour:
                return True

        return False
        for goal in self.short_term_goals + self.long_term_goals:
            # 根据描述找到对应的任务ID
            for task_id, task in self.persistence.tasks.items():
                if task.description == goal.description and task.task_type in ["short_term", "long_term"]:
                    self._task_id_to_goal[task_id] = goal
                    break

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

        # 如果持久化中没有目标（第一次创建），从配置中初始化
        # 初始化或恢复任务
        if not self.persistence.tasks:
            self._initialize_goals_from_config()

        # 恢复情感状态
        emotion_map = {
            "calm": Emotion.CALM,
            "angry": Emotion.ANGRY,
            "fearful": Emotion.WORRIED,
            "happy": Emotion.HAPPY,
            "sad": Emotion.SAD
        }
        self.current_emotion = emotion_map.get(
            self.persistence.current_state.emotional_state, Emotion.CALM
        )

        # 恢复能量水平
        self.energy_level = self.persistence.current_state.energy_level

        # 恢复当前活动（兼容旧的Activity枚举）
        primary_state = self.persistence.current_state.primary_state
        if primary_state == "rest":
            self.current_activity = NPCAction.SLEEP
        elif primary_state == "activity":
            # 根据当前任务确定具体活动
            current_task = self.persistence.current_task
            if current_task:
                task_desc = current_task.description.lower()
                if "睡觉" in task_desc or "休息" in task_desc:
                    self.current_activity = NPCAction.SLEEP
                elif "工作" in task_desc:
                    self.current_activity = NPCAction.WORK
                elif "观察" in task_desc or "调查" in task_desc:
                    self.current_activity = NPCAction.OBSERVE
                else:
                    self.current_activity = NPCAction.REST
            else:
                self.current_activity = NPCAction.REST

        # 设置活动开始时间
        self.activity_start_time = datetime.now()

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

    def process_event(self, event_content: str, event_type: str,
                     max_reasoning_steps: Optional[int] = None) -> Dict[str, Any]:
        """
        处理事件的统一入口 - 使用四级决策系统
        
        决策流程：
        L1: 生物钟硬判决 (0 tokens) - 是否遵循日程
        L2: 快速重要性过滤 (50 tokens) - 是否忽视这个事件
        L3: 战略规划 (200 tokens) - 制定行动计划
        L4: 深度推理 (500+ tokens) - 复杂情况下的树搜索推理

        Args:
            event_content: 事件内容
            event_type: 事件类型
            max_reasoning_steps: 最大推理步数（仅用于L4）
        """
        # 0. 预处理：构建当前状态快照
        current_state = self._build_current_state_snapshot()
        
        # 1. 评估事件冲击力（0-100）
        impact_score = self._evaluate_event_impact(event_content, event_type)
        
        # 2. 构建事件对象
        event = {
            "content": event_content,
            "type": event_type,
            "impact_score": impact_score,
            "timestamp": datetime.now().isoformat()
        }
        
        # 3. 使用四级决策系统做出决策
        decision_result = self.decision_maker.make_decision(
            event=event,
            current_state=current_state,
            latest_impact_score=impact_score
        )
        
        # 4. 执行决策的行动
        response_data = self._execute_decision(decision_result, event, current_state)
        
        # 5. 记录决策过程和结果
        self._record_decision_and_event(event, decision_result, response_data)
        
        return response_data

    def _build_current_state_snapshot(self) -> Dict[str, Any]:
        """构建当前NPC状态快照，供决策系统使用"""
        current_hour = self.world_clock.current_time.hour
        
        return {
            "current_action": self.current_activity,
            "current_hour": current_hour,
            "energy_level": self.energy_level,
            "hunger_level": self.hunger_level,
            "fatigue_level": self.fatigue_level,
            "current_emotion": self.current_emotion.value,
            "location": self.current_location,
            "current_task": self.persistence.current_task.description if self.persistence.current_task else None,
            "time_string": self.world_clock.current_time.strftime("%H:%M"),
            "relationships": self._get_relevant_relationships(event_content=""),
            "recent_memory": self._get_recent_memory_context()
        }

    def _evaluate_event_impact(self, event_content: str, event_type: str) -> int:
        """
        评估事件冲击力 (0-100)
        
        冲击力决定事件是否能打断当前活动（与ACTIVITY_INERTIA比较）
        """
        # 基础分值（基于事件类型）
        base_scores = {
            "dialogue": 20,        # 对话
            "world_event": 40,     # 世界事件
            "preset_event": 50,    # 预设事件
            "status_change": 30,   # 状态变化
            "social": 35,          # 社交
            "danger": 80,          # 危险事件
            "emergency": 100       # 紧急事件
        }
        
        impact = base_scores.get(event_type, 30)
        
        # 根据内容关键词调整冲击力
        keywords_high_impact = ["死亡", "受伤", "失火", "救助", "紧急", "危险", "攻击"]
        keywords_low_impact = ["问好", "闲聊", "观察", "想"]
        
        content_lower = event_content.lower()
        for keyword in keywords_high_impact:
            if keyword in content_lower:
                impact = min(100, impact + 20)
        
        for keyword in keywords_low_impact:
            if keyword in content_lower:
                impact = max(0, impact - 10)
        
        return impact

    def _execute_decision(self, decision_result: Dict[str, Any], 
                         event: Dict[str, Any], 
                         current_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行决策系统的输出
        
        如果推荐改变活动，则：
        1. 更新当前活动
        2. 生成合适的响应文本
        3. 创建/更新任务（如需要）
        """
        recommended_action = decision_result.get("action")
        decision_level = decision_result.get("decision_level")
        reasoning = decision_result.get("reasoning", "")
        confidence = decision_result.get("confidence", 0.5)
        
        response_data = {
            "decision_level": decision_level.value if hasattr(decision_level, 'value') else str(decision_level),
            "recommended_action": recommended_action.value if hasattr(recommended_action, 'value') else str(recommended_action),
            "reasoning": reasoning,
            "confidence": confidence,
            "response_text": "",
            "state_changed": False,
            "new_task_created": False
        }
        
        # 如果推荐的行动与当前行动不同，则改变活动
        if recommended_action != current_state.get("current_action"):
            try:
                self._change_activity(recommended_action)
                response_data["state_changed"] = True
            except Exception as e:
                logger.warning(f"改变活动失败: {e}")
        
        # 生成自然语言响应
        response_text = self._generate_response_for_event(
            event, 
            recommended_action, 
            decision_level,
            reasoning
        )
        response_data["response_text"] = response_text
        
        # 如果是高优先级事件（影响度>70）且L3/L4决策，可能需要创建任务
        if event.get("impact_score", 0) > 70 and decision_level.value >= 3:
            task_created = self._potentially_create_task_for_event(event, reasoning)
            response_data["new_task_created"] = task_created
        
        return response_data

    def _generate_response_for_event(self, event: Dict[str, Any], 
                                     action: NPCAction,
                                     decision_level,
                                     reasoning: str) -> str:
        """
        根据事件和决策生成NPC的自然语言响应
        
        这里可以用轻量级的规则或简单的LLM调用，避免过度消耗Token
        """
        action_responses = {
            NPCAction.SLEEP: "我现在很累，需要休息一下...",
            NPCAction.EAT: "我有点饿了，得去吃点东西。",
            NPCAction.WORK: "我得继续我的工作。",
            NPCAction.REST: "我需要休息一会儿。",
            NPCAction.SOCIALIZE: "让我们聊一聊吧。",
            NPCAction.OBSERVE: "让我看看发生了什么。",
            NPCAction.THINK: "这需要我好好思考一下...",
            NPCAction.PRAY: "我要去祈祷。",
            NPCAction.LEARN: "这很有趣，我想了解更多。",
            NPCAction.CREATE: "我想创造点什么。",
            NPCAction.HELP_OTHERS: "我应该去帮忙。",
            NPCAction.TRAVEL: "我需要移动到其他地方。"
        }
        
        # 根据事件类型添加特定的回应
        event_type_responses = {
            "dialogue": f"（听到了）{event.get('content', '')}",
            "world_event": "（注意到周围发生了什么变化）",
            "danger": "（立即警觉起来！）",
            "emergency": "（这是紧急情况！）"
        }
        
        base_response = event_type_responses.get(
            event.get("type", ""),
            action_responses.get(action, "我在处理这个情况。")
        )
        
        return base_response

    def _potentially_create_task_for_event(self, event: Dict[str, Any], reasoning: str) -> bool:
        """
        在必要时为事件创建任务
        
        返回：是否成功创建了任务
        """
        # 仅为特定类型的高影响事件创建任务
        should_create = event.get("type") in ["world_event", "preset_event", "emergency"]
        
        if should_create:
            try:
                task_id = self.persistence.create_task(
                    description=f"处理事件: {event['content'][:50]}",
                    task_type="event_response",
                    priority=min(100, event.get("impact_score", 50) + 20)
                )
                
                # 如果这是紧急任务，立即设为当前任务
                if event.get("impact_score", 0) > 80:
                    task = self.persistence.tasks.get(task_id)
                    if task:
                        self.persistence.set_current_task(task)
                
                return True
            except Exception as e:
                logger.warning(f"创建事件任务失败: {e}")
        
        return False

    def _record_decision_and_event(self, event: Dict[str, Any], 
                                   decision_result: Dict[str, Any],
                                   response_data: Dict[str, Any]):
        """
        记录事件和决策过程到持久化存储
        """
        try:
            # 记录到决策历史
            self.decision_history.append({
                'timestamp': datetime.now(),
                'type': 'event_processing',
                'event': event,
                'decision_level': decision_result.get('decision_level'),
                'recommended_action': decision_result.get('action'),
                'confidence': decision_result.get('confidence'),
                'response': response_data.get('response_text')
            })
            
            # 限制历史长度
            if len(self.decision_history) > 100:
                self.decision_history = self.decision_history[-100:]
            
            # 保存到持久化存储（可选）
            # self.persistence.record_event(event, decision_result)
            
        except Exception as e:
            logger.warning(f"记录决策和事件失败: {e}")

    def _get_relevant_relationships(self, event_content: str) -> List[str]:
        """
        获取与事件相关的关系信息
        
        返回：相关NPC名称列表
        """
        try:
            if hasattr(self, 'relationships') and isinstance(self.relationships, dict):
                # 简单实现：返回关系得分最高的几个NPC
                sorted_rels = sorted(
                    self.relationships.items(),
                    key=lambda x: abs(x[1].affection),
                    reverse=True
                )
                return [npc_name for npc_name, _ in sorted_rels[:3]]
            return []
        except Exception as e:
            logger.warning(f"获取相关关系失败: {e}")
            return []

    def _get_recent_memory_context(self) -> str:
        """
        获取最近的记忆上下文
        
        返回：最近事件的简要总结
        """
        try:
            if hasattr(self, 'memories') and self.memories:
                # 获取最近3条记忆
                recent = self.memories[-3:] if len(self.memories) > 3 else self.memories
                context_parts = []
                for mem in recent:
                    if hasattr(mem, 'content'):
                        context_parts.append(mem.content[:50])
                return " | ".join(context_parts)
            return "（暂无最近记忆）"
        except Exception as e:
            logger.warning(f"获取记忆上下文失败: {e}")
            return "（记忆访问失败）"

    def _generate_event_response(self, event_content: str, event_type: str,
                                impact_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成事件响应和状态变化"""
        # 使用LLM分析应该如何响应
        prompt = f"""
你是一个{self.config['name']}，{self.config['profession']}。
当前状态：{self.persistence.current_state.primary_state}
当前任务：{self.persistence.current_task.description if self.persistence.current_task else '无'}
情感状态：{self.persistence.current_state.emotional_state}
警觉度：{self.persistence.current_state.alertness_level}

事件：{event_content}
事件影响度：{impact_analysis['impact_score']}
是否应该改变状态：{impact_analysis['should_change_state']}

请分析：
1. 应该如何回应这个事件
2. 是否需要改变主要状态（rest/activity）
3. 是否需要创建新任务来处理这个事件
4. 对情感状态的影响

请用JSON格式回复：
{{
    "response": "你的回应内容",
    "reasoning": "回应的理由",
    "state_change": "rest/activity/none",
    "emotion_change": "calm/angry/fearful/happy/sad/none",
    "create_task": true/false,
    "task_description": "如果需要创建任务，这里填写任务描述",
    "task_priority": 1-100
}}
"""

        try:
            llm_response = self.llm_client.generate_response(prompt)
            result = json.loads(llm_response)

            # 应用状态变化
            state_changed = self._apply_state_changes(result)

            return {
                'response_text': result.get('response', ''),
                'reasoning': result.get('reasoning', ''),
                'state_changed': state_changed,
                'new_task_created': result.get('create_task', False),
                'task_description': result.get('task_description', ''),
                'task_priority': result.get('task_priority', 50)
            }

        except Exception as e:
            # 如果LLM分析失败，使用默认响应
            return {
                'response_text': "（看起来有些困惑）这是怎么回事？",
                'reasoning': f"LLM分析失败: {e}",
                'state_changed': False,
                'new_task_created': False
            }

    def _apply_state_changes(self, llm_result: Dict[str, Any]) -> bool:
        """应用LLM建议的状态变化"""
        state_changed = False

        # 状态变化
        state_change = llm_result.get('state_change', 'none')
        if state_change != 'none' and state_change != self.persistence.current_state.primary_state:
            old_state = self.persistence.current_state.primary_state
            self.persistence.current_state.primary_state = state_change
            self.persistence.current_state.last_activity_change = datetime.now().isoformat()
            state_changed = True

            # 根据新状态调整当前活动
            if state_change == "rest":
                self.current_activity = NPCAction.REST
            elif state_change == "activity":
                # 活动状态下，根据当前任务确定具体活动
                current_task = self.persistence.current_task
                if current_task:
                    task_desc = current_task.description.lower()
                    if "睡觉" in task_desc:
                        self.current_activity = NPCAction.SLEEP
                    elif "观察" in task_desc or "调查" in task_desc:
                        self.current_activity = NPCAction.OBSERVE
                    elif "工作" in task_desc:
                        self.current_activity = NPCAction.WORK
                    else:
                        self.current_activity = NPCAction.REST
                else:
                    self.current_activity = NPCAction.REST

        # 情感变化
        emotion_change = llm_result.get('emotion_change', 'none')
        if emotion_change != 'none':
            self.persistence.current_state.emotional_state = emotion_change
            emotion_map = {
                "calm": Emotion.CALM,
                "angry": Emotion.ANGRY,
                "fearful": Emotion.WORRIED,
                "happy": Emotion.HAPPY,
                "sad": Emotion.SAD
            }
            self.current_emotion = emotion_map.get(emotion_change, Emotion.CALM)

        # 创建新任务
        if llm_result.get('create_task', False):
            task_desc = llm_result.get('task_description', '')
            if task_desc:
                task_id = self.persistence.create_task(
                    description=task_desc,
                    task_type="event_response",
                    priority=llm_result.get('task_priority', 50)
                )

                # 如果这是高优先级任务，设置为当前任务并立即切换活动
                task_priority = llm_result.get('task_priority', 50)
                if task_priority > 70:
                    task = self.persistence.tasks[task_id]
                    self.persistence.set_current_task(task)
                    # 立即切换到合适的活动来处理任务
                    appropriate_activity = self._analyze_task_and_select_activity(task)
                    if appropriate_activity != self.current_activity:
                        self._change_activity(appropriate_activity)
                        # 立即执行一次新活动
                        self._execute_current_activity()

        return state_changed

    def _record_event(self, event_content: str, event_type: str,
                     impact_analysis: Dict[str, Any], response_data: Dict[str, Any]):
        """记录事件到持久化存储"""
        # 获取事件前后的状态
        state_before = {
            'primary_state': self.persistence.current_state.primary_state,
            'current_task': self.persistence.current_task.description if self.persistence.current_task else None,
            'emotional_state': self.persistence.current_state.emotional_state,
            'energy_level': self.persistence.current_state.energy_level
        }

        # 创建事件记录
        event = NPCEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            content=event_content,
            analysis=impact_analysis,
            response=response_data.get('response_text', ''),
            state_before=state_before,
            state_after={
                'primary_state': self.persistence.current_state.primary_state,
                'current_task': self.persistence.current_task.description if self.persistence.current_task else None,
                'emotional_state': self.persistence.current_state.emotional_state,
                'energy_level': self.persistence.current_state.energy_level
            },
            impact_score=impact_analysis.get('impact_score', 0)
        )

        # 记录事件
        self.persistence.record_event(event)

        # 同步goals变化到持久化系统
        self.sync_goals_to_persistence()


    def _adjust_activity_for_time(self, current_time: datetime):
        """根据当前时间自动调整活动状态"""
        hour = current_time.hour
        weekday = current_time.weekday()  # 0-6, 0是周一

        # 获取NPC的职业信息
        profession = self.config.get("profession", "")
        work_hours = self.config.get("work_hours", "")

        # 解析工作时间（简单实现）
        is_workday = weekday < 5  # 周一到周五工作

        # 根据时间段和职业判断应该的活动

        if 22 <= hour or hour < 6:  # 晚上10点到早上6点
            # 睡觉时间
            if self.current_activity != NPCAction.SLEEP:
                self.current_activity = NPCAction.SLEEP
                self.persistence.current_state.primary_state = "rest"
                self.activity_start_time = current_time

        elif 6 <= hour < 9:  # 早上6-9点
            # 起床准备时间
            if profession in ["铁匠", "商人", "牧师", "农民"]:
                if self.current_activity != NPCAction.WORK:
                    self.current_activity = NPCAction.WORK  # 准备工作
                    self.persistence.current_state.primary_state = "activity"
                    self.activity_start_time = current_time

        elif 9 <= hour < 18:  # 白天工作时间 9-18点
            if is_workday and profession in ["铁匠", "商人", "牧师", "农民"]:
                if self.current_activity != NPCAction.WORK:
                    self.current_activity = NPCAction.WORK
                    self.persistence.current_state.primary_state = "activity"
                    self.activity_start_time = current_time
            else:
                # 非工作日或非工作职业
                if self.current_activity != NPCAction.REST:
                    self.current_activity = NPCAction.REST
                    self.persistence.current_state.primary_state = "rest"
                    self.activity_start_time = current_time

        elif 18 <= hour < 22:  # 晚上18-22点
            # 下班后的社交时间
            if profession == "铁匠":
                if self.current_activity != NPCAction.SOCIALIZE:
                    self.current_activity = NPCAction.SOCIALIZE  # 去酒馆
                    self.persistence.current_state.primary_state = "activity"
                    self.activity_start_time = current_time
            else:
                if self.current_activity != NPCAction.REST:
                    self.current_activity = NPCAction.REST
                    self.persistence.current_state.primary_state = "rest"
                    self.activity_start_time = current_time

# 替换原有 _update_task_progress 方法
def _update_task_progress(self, time_diff_hours: float):
    """
    更新任务进度 - 修复版
    策略：日常使用纯数学计算，仅在20%节点进行轻量级LLM校验
    """
    task = self.persistence.current_task
    if not task or task.status != "active":
        return

    # 1. 首次预估设置（仅执行一次）
    if not hasattr(task, 'estimated_total_hours') or task.estimated_total_hours is None:
        # 给定一个基于优先级的默认初值，避免首次阻塞
        base_hours = 2.0 if task.priority > 80 else 4.0
        task.estimated_total_hours = base_hours
        # 异步请求LLM精细预估（可选）

    # 2. 纯数学步进 (30秒循环即 +0.008小时)
    old_progress = task.progress
    progress_increment = time_diff_hours / task.estimated_total_hours
    task.progress = min(1.0, task.progress + progress_increment)
    
    # 3. 动态校验点：每达到20%进度时进行一次轻量级逻辑检查
    milestone_met = (int(old_progress * 5) != int(task.progress * 5))
    if milestone_met and task.progress < 1.0:
        # 此处可根据需要决定是否调用 _llm_recheck_task_progress
        pass

    # 4. 只有在进度发生 1% 以上的变化时才保存，减少I/O
    if task.progress - old_progress > 0.01 or task.progress >= 1.0:
        self.persistence._save_data()

    if task.progress >= 1.0:
        task.status = "completed"
        self._handle_task_completion(task)

       
'''    def _update_task_progress(self, time_diff: float):
        """
        更新任务进度 - 优化版本（基于时间流逝而非每次LLM调用）
        策略：在创建任务时由LLM预估总时长，日常更新基于比例，只在突发事件时重新评估
        """
        task = self.persistence.current_task
        if not task or task.status != "active":
            return

        # 如果任务未设置预估时长，首次调用LLM获取预估值
        if not hasattr(task, 'estimated_total_hours') or task.estimated_total_hours is None:
            task.estimated_total_hours = self._llm_estimate_task_duration(task)
            self.persistence._save_data()

        # 基于时间流逝计算进度增量（而非LLM每次决策）
        if task.estimated_total_hours > 0:
            progress_increment = time_diff / task.estimated_total_hours
        else:
            progress_increment = 0.05  # 默认进度增量

        # 只在进度有明显变化或达到阈值时更新
        old_progress = task.progress
        task.progress = min(1.0, task.progress + progress_increment)
        
        # 每达到 20% 的进度或任务完成时，重新用 LLM 评估（动态调整）
        should_recheck = (int(old_progress * 5) != int(task.progress * 5)) or task.progress >= 1.0
        
        if should_recheck and task.progress < 1.0:
            # 重新评估：任务是否应该加速或减速完成
            dynamic_adjustment = self._llm_recheck_task_progress(task, time_diff)
            if dynamic_adjustment != 0:
                task.progress += dynamic_adjustment
                print(f"[LLM动态调整] 任务: {task.description[:30]}... 调整: {dynamic_adjustment*100:.1f}%")

        task.progress = min(1.0, task.progress)  # 确保不超过 100%
        self.persistence._save_data()

        if task.progress - old_progress > 0.01:
            print(f"[任务进度] {task.description[:30]}... {old_progress*100:.1f}% -> {task.progress*100:.1f}%")

        # 如果任务完成
        if task.progress >= 1.0:
            task.status = "completed"
            self.persistence.current_state.current_task_id = None
            self.persistence._save_data()
            self.sync_goals_to_persistence()
            print(f"[任务完成] {task.description}")

            # 检查是否有后续影响
            self._handle_task_completion(task)
'''


    def _llm_estimate_task_duration(self, task) -> float:
        """
        使用LLM预估任务的总时长（仅在创建任务时调用一次）
        
        Args:
            task: 任务对象
            
        Returns:
            预估小时数
        """
        try:
            prompt = f"""
你是一个 NPC 行为预测专家。请预估以下任务的完成时长（单位：小时）：

任务: {task.description}
优先级: {task.priority}
任务类型: {task.task_type}
NPC 工作: {self.config['profession']}
NPC 名字: {self.config['name']}

只返回一个数字（小时数），不要其他说明。
如果是短期任务（如制作物品），通常 0.5-4 小时。
如果是中期目标（如学习技能），通常 4-24 小时。
如果是长期目标，通常 24+ 小时。

预估时长（小时）："""
            
            response = self.deepseek_client.chat(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=50
            )
            
            try:
                # 提取数字
                duration_str = response['choices'][0]['message']['content'].strip()
                estimated_hours = float(''.join(filter(lambda x: x.isdigit() or x == '.', duration_str)))
                return max(0.5, min(720, estimated_hours))  # 限制在 0.5-720 小时
            except:
                return 4.0  # 默认 4 小时
                
        except Exception as e:
            print(f"LLM 预估任务时长失败: {e}")
            return 4.0  # 默认降级为 4 小时

    def _llm_recheck_task_progress(self, task, time_diff: float) -> float:
        """
        动态重新评估任务进度（仅在每 20% 进度时调用）
        检查任务是否应该加速或减速完成
        
        Args:
            task: 任务对象
            time_diff: 时间差（小时）
            
        Returns:
            进度调整增量 (-0.2 to 0.2)
        """
        try:
            # 简化的 prompt，只检查是否需要加速或减速
            prompt = f"""
任务进度检查：{task.description}
当前进度：{task.progress*100:.0f}%
预估总时长：{task.estimated_total_hours:.1f} 小时
当前情感状态：{self.current_emotion.value}
当前能量：{self.energy_level*100:.0f}%

请判断任务是否需要加速（+）、正常（0）或减速（-）？
只返回一个符号：+ 或 0 或 - （加速、正常或减速）"""
            
            response = self.deepseek_client.chat(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=10
            )
            
            decision = response['choices'][0]['message']['content'].strip()[0]  # 取第一个字符
            
            if decision == '+':
                return 0.1  # 加速 10% 进度
            elif decision == '-':
                return -0.05  # 减速 5% 进度
            else:
                return 0  # 正常，无调整
                
        except Exception as e:
            print(f"[LLM 动态评估失败] {e}，保持正常进度")
            return 0  # 失败时不调整

    def _handle_task_completion(self, completed_task: NPCTask):
        """处理任务完成的影响 - 使用LLM智能决策后续任务"""
        # 使用LLM判断是否需要创建后续任务，以及任务的优先级和截止时间
        try:
            prompt = f"""
任务已完成：{completed_task.description}

请分析：
1. 是否需要创建后续任务？
2. 如果需要，任务应该是什么？优先级是多少？需要多长时间完成？
3. 后续任务是否应该立即执行，还是可以插入到日常规划中？

请用JSON格式回复：
{{
    "create_followup": true/false,
    "task_description": "后续任务描述（如果需要）",
    "priority": 1-100,
    "estimated_hours": 0.5-4.0,
    "should_immediate": true/false,
    "reasoning": "你的推理"
}}

注意：
- 简单任务（如检查、报告）应该在0.5-1小时内完成
- 后续任务不一定需要立即执行，可以安排到合适的时间
- 考虑任务的紧急程度和重要性
"""
            
            response = self.llm_client.generate_response(prompt, max_tokens=300)
            import json
            import re
            
            json_match = re.search(r'\{[^{}]*"create_followup"[^{}]*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                if result.get('create_followup', False):
                    task_desc = result.get('task_description', '')
                    priority = result.get('priority', 60)
                    estimated_hours = result.get('estimated_hours', 1.0)
                    should_immediate = result.get('should_immediate', False)
                    
                    if task_desc:
                        # 创建后续任务
                        deadline = None
                        if not should_immediate:
                            # 不立即执行，安排在当天合适时间
                            current_hour = self.world_clock.current_time.hour
                            # 如果现在是工作时间，安排在下午；如果是晚上，安排在明天
                            if 9 <= current_hour < 18:
                                deadline_hour = min(17, current_hour + 2)  # 2小时后或17点
                            else:
                                deadline_hour = 14  # 明天下午2点
                            deadline = (self.world_clock.current_time + timedelta(days=0 if 9 <= current_hour < 18 else 1)).replace(hour=deadline_hour, minute=0)
                        
                        follow_up_task = self.persistence.create_task(
                            description=task_desc,
                            task_type="event_followup",
                            priority=priority,
                            deadline=deadline.isoformat() if deadline else None
                        )
                        
                        # 只有高优先级或需要立即执行的任务才设置为当前任务
                        if should_immediate or priority >= 80:
                            task_obj = self.persistence.tasks[follow_up_task]
                            self.persistence.set_current_task(task_obj)
                        # 否则作为待办任务，由Agent自主规划
                        
                        reasoning = result.get('reasoning', '')
                        if reasoning:
                            print(f"[后续任务] {reasoning}")
        except Exception as e:
            print(f"后续任务决策失败: {e}")
        
        # 保存状态
        self.persistence._save_data()

    def _set_initial_activity(self):
        """根据当前时间和职业设置初始活动"""
        current_hour = self.world_clock.current_time.hour
        profession = self.config.get("profession", "")

        # 基于时间和职业设置初始活动
        if 22 <= current_hour or current_hour < 6:
            # 深夜：睡觉
            self.current_activity = NPCAction.SLEEP
        elif 6 <= current_hour < 8:
            # 早上：起床准备
            self.current_activity = NPCAction.REST
        elif 8 <= current_hour < 18:
            # 白天工作时间
            if profession in ["铁匠", "blacksmith"]:
                # 铁匠在工作时间内工作
                work_hours = self.config.get("work_hours", "早上6点-晚上7点")
                if "6" in work_hours and current_hour >= 8:
                    self.current_activity = NPCAction.WORK
                else:
                    self.current_activity = NPCAction.REST
            elif profession in ["酒馆老板", "innkeeper"]:
                # 酒馆老板在营业时间工作
                work_hours = self.config.get("work_hours", "早上8点到深夜12点")
                if current_hour >= 8:
                    self.current_activity = NPCAction.WORK
                else:
                    self.current_activity = NPCAction.REST
            elif profession in ["牧师", "priest"]:
                # 牧师在工作时间内工作
                work_hours = self.config.get("work_hours", "早上8点-下午4点")
                if 8 <= current_hour < 16:
                    self.current_activity = NPCAction.WORK
                else:
                    self.current_activity = NPCAction.REST
            else:
                # 其他职业默认工作
                self.current_activity = NPCAction.WORK
        elif 18 <= current_hour < 22:
            # 晚上：社交或休息
            if profession in ["酒馆老板", "innkeeper"]:
                self.current_activity = NPCAction.WORK  # 晚班
            else:
                self.current_activity = NPCAction.SOCIALIZE
        else:
            # 默认睡觉
            self.current_activity = NPCAction.SLEEP

        # 设置活动开始时间为当前时间
        self.activity_start_time = self.world_clock.current_time

    def _initialize_from_config(self):
        """从配置初始化NPC状态"""
        # 初始化情感状态
        base_mood = self.config["emotional_state"]["base_mood"]
        if base_mood == "cheerful":
            self.current_emotion = Emotion.HAPPY
        elif base_mood == "calm":
            self.current_emotion = Emotion.CALM
        elif base_mood == "serious":
            self.current_emotion = Emotion.CONTENT

        # 初始化记忆
        for memory_text in self.config.get("memories", []):
            memory = Memory(
                content=memory_text,
                emotional_impact=random.randint(-5, 5),
                importance=random.randint(1, 10),
                timestamp=self.world_clock.current_time - timedelta(days=random.randint(1, 365))
            )
            self.memories.append(memory)

        # 初始化知识库
        self.knowledge_base = {
            "skills": self.config.get("skills", {}),
            "world_knowledge": {
                "town_layout": "小镇由中央广场、铁匠铺、酒馆、教堂等区域组成",
                "daily_routine": self.config.get("daily_schedule", {}),
                "important_people": list(self.config.get("relationships", {}).keys())
            }
        }

    def _initialize_goals(self):
        """初始化目标系统"""
        # 短期目标
        for goal_text in self.config["goals"]["short_term"]:
            goal = Goal(
                description=goal_text,
                priority=random.randint(3, 8),
                progress=random.uniform(0, 0.3)
            )
            self.short_term_goals.append(goal)

        # 长期目标
        for goal_text in self.config["goals"]["long_term"]:
            goal = Goal(
                description=goal_text,
                priority=random.randint(5, 10),
                deadline=self.world_clock.current_time + timedelta(days=random.randint(30, 365)),
                progress=random.uniform(0, 0.1)
            )
            self.long_term_goals.append(goal)

    def _initialize_relationships(self):
        """初始化人际关系"""
        for rel_key, rel_info in self.config.get("relationships", {}).items():
            relationship = Relationship(
                npc_name=rel_key,
                affection=random.randint(-20, 80),
                trust=random.randint(20, 90),
                relationship_type=rel_info.get("relationship", "acquaintance")
            )
            self.relationships[rel_key] = relationship

    def update_time(self, new_time: datetime):
        """更新时间并处理时间相关的状态变化"""
        time_diff = (new_time - self.world_clock.current_time).total_seconds() / 3600  # 小时差

        # 根据新时间调整活动状态
        self._adjust_activity_for_time(new_time)

        # 更新能量水平（基于活动和时间）
        if self.current_activity:
            energy_cost = self._get_activity_energy_cost(self.current_activity)
            self.energy_level = max(0, self.energy_level - energy_cost * time_diff)

        # 自然能量恢复（睡觉时更快）
        if self.current_activity == NPCAction.SLEEP:
            recovery_rate = 20  # 每小时恢复20点能量
        else:
            recovery_rate = 5

        self.energy_level = min(100, self.energy_level + recovery_rate * time_diff)

        # 使用LLM决策更新任务进度
        self._update_task_progress(time_diff)

        # 检查是否需要切换活动（额外的随机切换）
        if self._should_change_activity():
            self._select_new_activity()

    def _get_activity_energy_cost(self, activity: NPCAction) -> float:
        """获取活动能量消耗"""
        costs = {
            NPCAction.WORK: 15,
            NPCAction.SOCIALIZE: 8,
            NPCAction.TRAVEL: 12,
            NPCAction.THINK: 5,
            NPCAction.REST: 3,
            NPCAction.SLEEP: -10,  # 睡觉恢复能量
        }
        return costs.get(activity, 5)

    def _should_change_activity(self) -> bool:
        """判断是否应该切换活动"""
        # 检查需求紧急性
        urgent_need, need_level = self.need_system.get_most_urgent_need()

        # 如果有非常紧急的需求
        if need_level > 0.8:
            return True

        # 检查当前活动是否超时
        if self.activity_start_time:
            activity_duration = (self.world_clock.current_time - self.activity_start_time).total_seconds() / 3600
            max_duration = self._get_max_activity_duration(self.current_activity)
            if activity_duration > max_duration:
                return True

        # 检查能量水平
        if self.energy_level < 20 and self.current_activity != NPCAction.SLEEP:
            return True

        # 检查是否有紧急任务需要处理
        current_task = self.persistence.current_task
        if current_task and current_task.task_type == "event_response" and current_task.status == "active":
            # 检查任务优先级和时间
            priority = current_task.priority
            current_hour = self.world_clock.current_time.hour
            is_sleep_time = current_hour >= 22 or current_hour <= 6

            # 高优先级任务总是需要处理
            if priority >= 90:
                return True
            # 中等优先级任务在非睡觉时间处理
            elif priority >= 70 and not is_sleep_time:
                return True

        # 检查时间周期
        current_hour = self.world_clock.current_time.hour
        if current_hour >= 22 and self.current_activity != NPCAction.SLEEP:
            return True

        return False

    def _get_max_activity_duration(self, activity: NPCAction) -> float:
        """获取活动最大持续时间（小时）"""
        durations = {
            NPCAction.WORK: 4,
            NPCAction.SOCIALIZE: 2,
            NPCAction.REST: 1,
            NPCAction.EAT: 0.5,
            NPCAction.SLEEP: 8,
            NPCAction.TRAVEL: 1,
        }
        return durations.get(activity, 2)

    def _select_new_activity(self) -> NPCAction:
        """选择新活动"""
        # 检查当前时间是否应该睡觉
        current_hour = self.world_clock.current_time.hour
        is_sleep_time = current_hour >= 22 or current_hour <= 6

        # 优先检查是否有活跃的事件响应任务
        current_task = self.persistence.current_task
        if current_task and current_task.task_type == "event_response" and current_task.status == "active":
            # 如果是睡觉时间，只有重要事件才会中断睡眠
            if is_sleep_time:
                task_priority = current_task.priority
                # 重要事件（优先级>85）可以在睡觉时间处理，但会影响睡眠质量
                if task_priority > 85:
                    selected_activity = self._analyze_task_and_select_activity(current_task)
                    return selected_activity
                # 其他事件等到早上再处理
                else:
                    return NPCAction.SLEEP
            else:
                # 白天正常处理任务
                selected_activity = self._analyze_task_and_select_activity(current_task)
                return selected_activity

        # 如果没有活跃任务，则基于常规逻辑选择

        # 基于时间选择活动
        if 6 <= current_hour < 8:
            # 早上：起床、早餐
            possible_actions = [NPCAction.EAT, NPCAction.REST]
        elif 8 <= current_hour < 18:
            # 白天：工作时间
            if self.config["profession"] in ["blacksmith", "farmer", "merchant"]:
                possible_actions = [NPCAction.WORK, NPCAction.SOCIALIZE]
            else:
                possible_actions = [NPCAction.WORK, NPCAction.HELP_OTHERS]
        elif 18 <= current_hour < 22:
            # 晚上：社交、休息
            possible_actions = [NPCAction.SOCIALIZE, NPCAction.EAT, NPCAction.REST]
        else:
            # 深夜：睡觉
            possible_actions = [NPCAction.SLEEP]

        # 考虑能量水平
        if self.energy_level < 30:
            possible_actions = [NPCAction.REST, NPCAction.SLEEP]

        # 基于性格偏好调整
        personality = self.config["personality"]
        if "社交" in str(personality.get("traits", [])):
            if NPCAction.SOCIALIZE not in possible_actions:
                possible_actions.append(NPCAction.SOCIALIZE)

        # 随机选择，但考虑权重
        weights = [1] * len(possible_actions)

        # 工作时间更可能工作
        if NPCAction.WORK in possible_actions and 9 <= current_hour <= 17:
            work_index = possible_actions.index(NPCAction.WORK)
            weights[work_index] = 3

        # 疲惫时更可能休息
        if self.energy_level < 50 and NPCAction.REST in possible_actions:
            rest_index = possible_actions.index(NPCAction.REST)
            weights[rest_index] = 2

        selected_action = random.choices(possible_actions, weights=weights)[0]

        self.current_activity = selected_action
        self.activity_start_time = self.world_clock.current_time

        return selected_action

    def make_decision(self, available_actions: List[str], situation: str = "日常决策") -> Dict[str, Any]:
        """使用新的 ReActAgent 系统做出智能决策"""
        # 构建NPC上下文
        npc_context = self._build_npc_context()

        # 使用 ReActAgent 进行决策（简化实现）
        selected_action = available_actions[0] if available_actions else "休息"
        decision = {
            "action": selected_action,
            "reasoning": f"在'{situation}'情况下选择: {selected_action}",
            "confidence": 0.7
        }

        # 记录决策历史
        self.decision_history.append({
            "timestamp": self.world_clock.current_time,
            "situation": situation,
            "decision": decision,
            "available_actions": available_actions
        })

        # 执行工具调用（如果有）
        if decision.get('tool_calls'):
            for tool_call in decision['tool_calls']:
                self._execute_tool_call(tool_call)

        # 更新情感状态
        self._update_emotion_from_decision(decision)

        return decision

    def _build_npc_context(self) -> Dict[str, Any]:
        """构建NPC上下文字典"""
        # 获取最近记忆
        recent_memories = []
        if hasattr(self, 'memories') and self.memories:
            # 转换记忆到新的格式
            sorted_memories = sorted(self.memories, key=lambda x: x.timestamp, reverse=True)[:5]
            for memory in sorted_memories:
                recent_memories.append({
                    "content": memory.content,
                    "importance": memory.importance,
                    "emotional_impact": memory.emotional_impact,
                    "timestamp": memory.timestamp.isoformat(),
                    "tags": memory.tags if hasattr(memory, 'tags') else []
                })

        # 构建时间上下文
        time_context = {
            "season": self._get_season(),
            "time_of_day": self._get_time_of_day(),
            "day_of_week": self.world_clock.current_time.strftime("%A"),
            "weather": "正常",  # 可以扩展
            "hour": self.world_clock.current_time.hour
        }

        # 当前任务
        current_task = None
        if self.persistence.current_task:
            current_task = {
                "description": self.persistence.current_task.description,
                "progress": self.persistence.current_task.progress,
                "id": self.persistence.current_task.id
            }

        return {
            "name": self.config["name"],
            "race": self.config["race"],
            "profession": self.config["profession"],
            "personality": self.config["personality"]["traits"],
            "background": self.config["background"],
            "current_activity": self.current_activity.value if self.current_activity else "空闲",
            "current_emotion": self.current_emotion.value,
            "current_needs": {
                "hunger": getattr(self, 'hunger_level', 0.5),
                "fatigue": getattr(self, 'fatigue_level', 0.5),
                "social": getattr(self, 'social_need', 0.5),
                "achievement": getattr(self, 'achievement_need', 0.5)
            },
            "current_task": current_task,
            "recent_memories": recent_memories,
            "time_context": time_context
        }

    def _execute_tool_call(self, tool_call: Dict[str, Any]):
        """执行工具调用"""
        tool_name = tool_call.get('tool')
        args = tool_call.get('args', {})

        try:
            # 使用新版 NPCToolRegistry 执行工具
            result = self.tool_registry.execute_tool(tool_name, **args)
            if not result['success']:
                print(f"工具执行失败: {tool_name} - {result.get('error', '未知错误')}")
        except Exception as e:
            print(f"工具调用异常: {tool_name} - {e}")

    def _get_season(self) -> str:
        """获取当前季节"""
        month = self.world_clock.current_time.month
        if month in [12, 1, 2]:
            return "冬季"
        elif month in [3, 4, 5]:
            return "春季"
        elif month in [6, 7, 8]:
            return "夏季"
        else:
            return "秋季"

    def _get_time_of_day(self) -> str:
        """获取当前时间段"""
        hour = self.world_clock.current_time.hour
        if 5 <= hour < 12:
            return "上午"
        elif 12 <= hour < 18:
            return "下午"
        elif 18 <= hour < 22:
            return "晚上"
        else:
            return "深夜"

        # 更新目标进度
        self._update_goals_from_decision(decision)

        return decision

    def _update_emotion_from_decision(self, decision: Dict[str, Any]):
        """根据决策更新情感状态"""
        emotion_str = decision.get("emotion", "").lower()

        emotion_map = {
            "高兴": Emotion.HAPPY,
            "平静": Emotion.CALM,
            "担心": Emotion.WORRIED,
            "悲伤": Emotion.SAD,
            "愤怒": Emotion.ANGRY,
            "兴奋": Emotion.EXCITED,
            "疲惫": Emotion.EXHAUSTED,
            "满足": Emotion.CONTENT
        }

        if emotion_str in emotion_map:
            self.current_emotion = emotion_map[emotion_str]

    def _update_goals_from_decision(self, decision: Dict[str, Any]):
        """根据决策更新目标进度"""
        action = decision.get("action", "")
        reasoning = decision.get("reasoning", "")

        for goal in self.short_term_goals + self.long_term_goals:
            if goal.status == "active":
                # 检查是否与目标相关
                if any(keyword in reasoning for keyword in goal.description.split()):
                    goal.progress = min(1.0, goal.progress + 0.1)
                    if goal.progress >= 1.0:
                        goal.status = "completed"

    def add_memory(self, content: str, emotional_impact: int = 0, importance: int = 5, tags: List[str] = None):
        """添加新记忆（同时添加到RAG系统）"""
        memory = Memory(
            content=content,
            emotional_impact=emotional_impact,
            importance=importance,
            timestamp=self.world_clock.current_time,
            tags=tags or []
        )
        self.memories.append(memory)
        
        # 同时添加到RAG记忆系统
        try:
            memory_id = f"mem_{len(self.memories)}_{hash(content)}"
            self.rag_memory.add_memory(
                memory_id=memory_id,
                content=content,
                importance=importance,
                tags=tags or [],
                timestamp=memory.timestamp
            )
        except Exception as e:
            print(f"添加RAG记忆失败: {e}")

        # 限制记忆数量
        if len(self.memories) > 50:
            # 删除最不重要的记忆
            self.memories.sort(key=lambda x: x.importance)
            self.memories = self.memories[10:]

    def get_relationship_status(self, npc_name: str) -> Relationship:
        """获取与特定NPC的关系状态"""
        return self.relationships.get(npc_name, Relationship(npc_name, 0, 50))

    def interact_with_other(self, other_npc_name: str, interaction_type: str):
        """与其他NPC互动"""
        if other_npc_name not in self.relationships:
            self.relationships[other_npc_name] = Relationship(
                npc_name=other_npc_name,
                affection=0,
                trust=50
            )

        relationship = self.relationships[other_npc_name]
        relationship.interactions_count += 1
        relationship.last_interaction = self.world_clock.current_time

        # 根据互动类型调整关系
        if interaction_type == "help":
            relationship.affection = min(100, relationship.affection + 5)
            relationship.trust = min(100, relationship.trust + 3)
        elif interaction_type == "conflict":
            relationship.affection = max(-100, relationship.affection - 10)
            relationship.trust = max(0, relationship.trust - 5)

    def respond_to_world_event(self, event_description: str) -> Dict[str, Any]:
        """对世界事件做出响应"""
        response = self.llm_client.generate_world_event_response(
            self.config,
            event_description
        )

        # 分析事件类型并调整行为
        event_type = self._analyze_event_type(event_description)
        self._adjust_behavior_for_event(event_type, event_description)

        # 添加到记忆
        self.add_memory(
            f"世界事件：{event_description}，我的反应：{response['thoughts']}",
            emotional_impact=response.get('emotional_impact_score', 0),
            importance=7,
            tags=["world_event", "reaction", event_type]
        )

        return response

    def _analyze_event_type(self, event_description: str) -> str:
        """分析事件类型"""
        desc_lower = event_description.lower()

        # 威胁性事件
        if any(word in desc_lower for word in ["小偷", "盗贼", "强盗", "入侵", "攻击", "怪物", "野兽"]):
            return "threat"

        # 自然灾害
        if any(word in desc_lower for word in ["火灾", "地震", "洪水", "风暴"]):
            return "disaster"

        # 社会事件
        if any(word in desc_lower for word in ["拜访", "来访", "客人", "访客", "送信"]):
            return "social"

        # 其他事件
        return "general"

    def _adjust_behavior_for_event(self, event_type: str, event_description: str):
        """根据事件类型调整行为"""
        if event_type == "threat":
            # 面对威胁时，改变当前活动为防御或调查
            self.current_activity = NPCAction.OBSERVE  # 改为观察/调查
            self.energy_level = min(100, self.energy_level + 20)  # 肾上腺素提升
            self.current_emotion = Emotion.ANGRY if "小偷" in event_description else Emotion.WORRIED

        elif event_type == "disaster":
            # 面对灾害时，改变为求助或逃跑
            self.current_activity = NPCAction.HELP_OTHERS
            self.current_emotion = Emotion.WORRIED

        elif event_type == "social":
            # 面对社交事件时，改变为社交
            self.current_activity = NPCAction.SOCIALIZE
            self.current_emotion = Emotion.HAPPY

        # 重置活动开始时间
        self.activity_start_time = self.world_clock.current_time

    def get_status_summary(self) -> Dict[str, Any]:
        """获取NPC状态摘要"""
        current_task_data = None
        if self.persistence.current_task:
            task = self.persistence.current_task
            current_task_data = {
                'id': task.id,
                'description': task.description,
                'task_type': task.task_type,
                'priority': task.priority,
                'status': task.status,
                'progress': task.progress
            }

        return {
            "name": self.config["name"],
            "profession": self.config["profession"],
            "current_emotion": self.current_emotion.value,
            "energy_level": self.energy_level,
            "current_activity": self.current_activity.value if self.current_activity else "无",
            "current_state": {
                "primary_state": self.persistence.current_state.primary_state,
                "current_task": current_task_data,
                "current_task_id": self.persistence.current_state.current_task_id
            },
            "location": self.current_location,
            "time": self.world_clock.current_time.strftime("%H:%M"),
            "active_goals": len([g for g in self.short_term_goals + self.long_term_goals if g.status == "active"]),
            "recent_memories": len([m for m in self.memories if (self.world_clock.current_time - m.timestamp).days < 7])
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "config": self.config,
            "current_emotion": self.current_emotion.value,
            "energy_level": self.energy_level,
            "current_time": self.world_clock.current_time.isoformat(),
            "current_location": self.current_location,
            "current_activity": self.current_activity.value if self.current_activity else None,
            "memories": [m.__dict__ for m in self.memories],
            "goals": {
                "short_term": [g.__dict__ for g in self.short_term_goals],
                "long_term": [g.__dict__ for g in self.long_term_goals]
            },
            "relationships": {k: v.__dict__ for k, v in self.relationships.items()},
            "decision_history": self.decision_history[-10:]  # 只保存最近10个决策
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], deepseek_client: DeepSeekClient) -> 'NPCBehaviorSystem':
        """从字典反序列化"""
        npc = cls(data["config"], deepseek_client)

        npc.current_emotion = Emotion(data.get("current_emotion", "平静"))
        npc.energy_level = data.get("energy_level", 100)
        npc.current_time = datetime.fromisoformat(data["current_time"])
        npc.current_location = data.get("current_location", "住宅")
        npc.current_activity = NPCAction(data["current_activity"]) if data.get("current_activity") else None

        # 恢复记忆
        npc.memories = [Memory(**m) for m in data.get("memories", [])]

        # 恢复目标
        goals_data = data.get("goals", {})
        npc.short_term_goals = [Goal(**g) for g in goals_data.get("short_term", [])]
        npc.long_term_goals = [Goal(**g) for g in goals_data.get("long_term", [])]

        # 恢复关系
        npc.relationships = {k: Relationship(**v) for k, v in data.get("relationships", {}).items()}

        npc.decision_history = data.get("decision_history", [])

        return npc

    def _analyze_task_and_select_activity(self, task) -> NPCAction:
        """
        智能分析任务内容并选择合适的应对活动

        Args:
            task: 要分析的任务

        Returns:
            合适的NPC活动
        """
        description = task.description.lower()

        # 基于任务优先级和内容的智能分析
        priority = task.priority

        # 高优先级任务（>80）通常需要立即关注
        if priority > 80:
            # 分析任务内容的语义特征
            activity = self._classify_task_by_content(description)
            return activity

        # 中等优先级任务（>=50）根据具体内容决定
        elif priority >= 50:
            activity = self._classify_task_by_content(description)
            return activity

        # 低优先级任务（<50）通常只需要观察
        else:
            return NPCAction.OBSERVE

    def _classify_task_by_content(self, description: str) -> NPCAction:
        """
        基于任务内容分类选择活动

        Args:
            description: 任务描述（小写）

        Returns:
            合适的活动类型
        """
        # 威胁和安全相关任务
        threat_keywords = [
            '小偷', '偷窃', '盗贼', '入侵', '闯入', '威胁', '危险', '攻击',
            'theft', 'steal', 'intruder', 'threat', 'danger', 'attack',
            'robber', 'burglar', 'intrusion'
        ]
        if any(keyword in description for keyword in threat_keywords):
            return NPCAction.OBSERVE  # 警戒观察

        # 帮助和救援相关任务
        help_keywords = [
            '帮助', '救援', '救人', '援助', '协助', '支持',
            'help', 'rescue', 'aid', 'assist', 'support',
            'save', 'protect', 'defend'
        ]
        if any(keyword in description for keyword in help_keywords):
            return NPCAction.HELP_OTHERS

        # 社交和沟通相关任务
        social_keywords = [
            '谈话', '聊天', '会面', '交流', '沟通', '拜访',
            'talk', 'chat', 'meet', 'communicate', 'visit',
            'conversation', 'discussion'
        ]
        if any(keyword in description for keyword in social_keywords):
            return NPCAction.SOCIALIZE

        # 调查和探索相关任务
        investigation_keywords = [
            '调查', '检查', '寻找', '搜索', '探索', '查看',
            'investigate', 'check', 'find', 'search', 'explore',
            'examine', 'inspect'
        ]
        if any(keyword in description for keyword in investigation_keywords):
            return NPCAction.OBSERVE

        # 工作和劳动相关任务
        work_keywords = [
            '工作', '劳动', '修理', '制作', '建造', '维护',
            'work', 'labor', 'repair', 'make', 'build', 'maintain',
            'craft', 'create', 'construct'
        ]
        if any(keyword in description for keyword in work_keywords):
            return NPCAction.WORK

        # 学习和研究相关任务
        learn_keywords = [
            '学习', '研究', '阅读', '练习', '训练', '钻研',
            'learn', 'study', 'read', 'practice', 'train',
            'research', 'explore'
        ]
        if any(keyword in description for keyword in learn_keywords):
            return NPCAction.LEARN

        # 医疗和治疗相关任务
        medical_keywords = [
            '治疗', '医疗', '救治', '护理', '康复',
            'treat', 'heal', 'medical', 'care', 'recovery',
            'medicine', 'cure', 'nurse'
        ]
        if any(keyword in description for keyword in medical_keywords):
            return NPCAction.HELP_OTHERS  # 用帮助他人代替医疗活动

        # 祈祷和精神相关任务
        spiritual_keywords = [
            '祈祷', '祷告', '冥想', '礼拜', '仪式',
            'pray', 'prayer', 'meditate', 'worship', 'ritual',
            'spiritual', 'religious'
        ]
        if any(keyword in description for keyword in spiritual_keywords):
            return NPCAction.PRAY

        # 旅行和移动相关任务
        travel_keywords = [
            '旅行', '移动', '前往', '出发', '行走',
            'travel', 'move', 'go', 'journey', 'walk',
            'transport', 'journey'
        ]
        if any(keyword in description for keyword in travel_keywords):
            return NPCAction.TRAVEL

        # 默认情况下，对未知任务保持观察状态
        return NPCAction.OBSERVE
