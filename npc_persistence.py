"""
NPC持久化存储系统
使用JSON文件存储NPC的完整状态和事件历史
"""

import json
import os
import time
import gzip
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import threading

@dataclass
class NPCEvent:
    """NPC事件记录"""
    timestamp: str
    event_type: str  # dialogue, world_event, preset_event, status_change
    content: str
    analysis: Dict[str, Any]  # LLM分析结果
    response: str
    state_before: Dict[str, Any]  # 事件前状态
    state_after: Dict[str, Any]   # 事件后状态
    impact_score: int  # 事件影响度 0-100
    resolved: bool = False  # 事件是否已解决

@dataclass
class NPCTask:
    """NPC任务"""
    id: str
    description: str
    task_type: str  # short_term, long_term, event_response
    priority: int   # 0-100
    status: str     # pending, active, completed, failed, paused
    created_at: str
    deadline: Optional[str] = None
    progress: float = 0.0
    related_events: List[str] = None  # 相关事件ID列表

    def __post_init__(self):
        if self.related_events is None:
            self.related_events = []

@dataclass
class NPCState:
    """NPC当前状态"""
    primary_state: str      # rest/activity 主要状态
    current_task_id: Optional[str] = None  # 当前任务ID，而不是对象引用
    emotional_state: str = "calm"
    energy_level: int = 100
    alertness_level: int = 50  # 警觉度 0-100，影响对事件的敏感度
    last_activity_change: str = ""
    consecutive_rest_hours: int = 0  # 连续休息小时数

class NPCPersistence:
    """NPC持久化管理器"""

    def __init__(self, npc_name: str, storage_dir: str = "npc_storage"):
        self.npc_name = npc_name
        self.storage_dir = storage_dir
        self.file_path = os.path.join(storage_dir, f"{npc_name}.json.gz")
        self.lock = threading.Lock()

        # 确保存储目录存在
        os.makedirs(storage_dir, exist_ok=True)

        # 初始化数据结构
        self.current_state = NPCState(primary_state="rest")
        self.tasks: Dict[str, NPCTask] = {}
        self.event_history: List[NPCEvent] = []
        self.thinking_variables: Dict[str, Any] = {}

        # 加载现有数据
        self._load_data()

    def _load_data(self):
        """加载NPC数据"""
        try:
            if os.path.exists(self.file_path):
                with gzip.open(self.file_path, 'rt', encoding='utf-8') as f:
                    data = json.load(f)

                # 恢复状态
                if 'current_state' in data:
                    state_data = data['current_state']
                    self.current_state = NPCState(**state_data)

                # 恢复任务
                if 'tasks' in data:
                    for task_id, task_data in data['tasks'].items():
                        self.tasks[task_id] = NPCTask(**task_data)

                # 恢复事件历史（限制数量）
                if 'event_history' in data:
                    # 只加载最近100个事件
                    recent_events = data['event_history'][-100:]
                    self.event_history = [NPCEvent(**event) for event in recent_events]

                # 恢复思考变量
                if 'thinking_variables' in data:
                    self.thinking_variables = data['thinking_variables']

                print(f"Loaded existing NPC {self.npc_name} data")

            else:
                # 文件不存在，初始化默认状态
                print(f"Creating new NPC {self.npc_name} data")
                self._initialize_default_state()

        except Exception as e:
            print(f"Failed to load NPC {self.npc_name} data: {e}")
            # 初始化默认状态
            self._initialize_default_state()

    def _initialize_default_state(self):
        """初始化默认状态"""
        self.current_state = NPCState(primary_state="rest")
        self.tasks = {}
        self.event_history = []
        self.thinking_variables = {
            "personality_traits": ["坚韧", "耐心", "固执", "智慧", "沉默寡言"],
            "work_ethics": "注重作息规律，每天6点准时开门",
            "event_sensitivity": 60,  # 对事件的敏感度 0-100
            "risk_tolerance": 30,    # 风险承受度 0-100
            "social_responsibility": 80,  # 社会责任感
        }

        # 注意：这里不直接创建任务
        # 任务应该由NPCBehaviorSystem通过_initialize_goals_from_config方法创建
        # 这样可以确保配置文件中的所有目标都被正确加载

        # 保存初始状态（不包含任务，任务由NPC系统管理）
        self._save_data()

    def _save_data(self):
        """保存NPC数据"""
        try:
            with self.lock:
                data = {
                    'npc_name': self.npc_name,
                    'last_save': datetime.now().isoformat(),
                    'current_state': asdict(self.current_state),
                    'tasks': {task_id: asdict(task) for task_id, task in self.tasks.items()},
                    'event_history': [asdict(event) for event in self.event_history[-200:]],  # 保存最近200个事件
                    'thinking_variables': self.thinking_variables
                }

                # 压缩保存
                with gzip.open(self.file_path, 'wt', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"保存NPC {self.npc_name} 数据失败: {e}")

    def create_task(self, description: str, task_type: str, priority: int,
                   deadline: Optional[str] = None) -> str:
        """创建新任务"""
        task_id = f"{self.npc_name}_{int(time.time())}_{len(self.tasks)}"
        task = NPCTask(
            id=task_id,
            description=description,
            task_type=task_type,
            priority=priority,
            status="pending",
            created_at=datetime.now().isoformat(),
            deadline=deadline
        )

        self.tasks[task_id] = task
        self._save_data()
        return task_id

    def update_task(self, task_id: str, **updates):
        """更新任务"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            self._save_data()

    def set_current_task(self, task: NPCTask):
        """设置当前任务"""
        # 如果有旧的当前任务，标记为暂停
        if self.current_state.current_task_id:
            old_task = self.tasks.get(self.current_state.current_task_id)
            if old_task:
                old_task.status = "paused"

        # 设置新任务
        self.current_state.current_task_id = task.id
        task.status = "active"
        self.current_state.last_activity_change = datetime.now().isoformat()

        self._save_data()

    def clear_current_task(self):
        """清除当前任务"""
        if self.current_state.current_task_id:
            old_task = self.tasks.get(self.current_state.current_task_id)
            if old_task:
                old_task.status = "paused"
            self.current_state.current_task_id = None
            self._save_data()

    def clear_all_event_tasks(self):
        """清除所有事件响应任务（用于重置）"""
        tasks_to_remove = []
        for task_id, task in self.tasks.items():
            if task.task_type == "event_response" and task.status != "completed":
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
        
        if self.current_state.current_task_id in tasks_to_remove:
            self.current_state.current_task_id = None
        
        self._save_data()

    @property
    def current_task(self) -> Optional[NPCTask]:
        """获取当前任务对象"""
        if self.current_state.current_task_id:
            return self.tasks.get(self.current_state.current_task_id)
        return None

    def record_event(self, event: NPCEvent):
        """记录事件"""
        self.event_history.append(event)

        # 限制事件历史长度（内存管理）
        if len(self.event_history) > 500:
            # 压缩旧事件：只保留重要信息
            self._compress_old_events()

        self._save_data()

    def _compress_old_events(self):
        """压缩旧事件以节省存储空间"""
        # 保留最近100个完整事件
        recent_events = self.event_history[-100:]

        # 压缩更早的事件：只保留关键信息
        compressed_events = []
        for event in self.event_history[:-100]:
            compressed = NPCEvent(
                timestamp=event.timestamp,
                event_type=event.event_type,
                content=f"[压缩] {event.content[:50]}..." if len(event.content) > 50 else event.content,
                analysis={},  # 清空详细分析
                response=event.response[:30] + "..." if len(event.response) > 30 else event.response,
                state_before={},
                state_after={},
                impact_score=event.impact_score,
                resolved=event.resolved
            )
            compressed_events.append(compressed)

        self.event_history = compressed_events + recent_events

    def analyze_event_impact(self, event_content: str, event_type: str) -> Dict[str, Any]:
        """
        分析事件影响
        返回事件的影响分析结果
        """
        # 获取当前状态的敏感度
        sensitivity = self.thinking_variables.get('event_sensitivity', 50)
        risk_tolerance = self.thinking_variables.get('risk_tolerance', 50)

        # 基础影响计算
        base_impact = self._calculate_base_impact(event_content, event_type)

        # 状态影响修正
        state_modifier = self._calculate_state_modifier()

        # 时间影响修正
        time_modifier = self._calculate_time_modifier()

        # 最终影响度
        final_impact = min(100, max(0, base_impact + state_modifier + time_modifier))

        # 判断是否需要状态转换
        should_change_state = final_impact > sensitivity

        return {
            'impact_score': final_impact,
            'should_change_state': should_change_state,
            'base_impact': base_impact,
            'state_modifier': state_modifier,
            'time_modifier': time_modifier,
            'sensitivity_threshold': sensitivity,
            'risk_tolerance': risk_tolerance
        }

    def _calculate_base_impact(self, event_content: str, event_type: str) -> int:
        """计算基础事件影响"""
        impact_keywords = {
            'threat': ['小偷', '盗贼', '强盗', '入侵', '攻击', '怪物', '野兽', '危险', '火灾', '爆炸'],
            'social': ['拜访', '来访', '客人', '访客', '送信', '求助', '帮助'],
            'personal': ['生病', '受伤', '家庭', '亲人', '朋友', '爱情'],
            'economic': ['钱', '金币', '生意', '交易', '合同', '订单'],
            'environmental': ['天气', '雨', '雪', '风暴', '地震', '洪水']
        }

        impact = 0
        content_lower = event_content.lower()

        for category, keywords in impact_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in content_lower)
            if matches > 0:
                if category == 'threat':
                    impact += matches * 30  # 威胁事件影响大
                elif category == 'social':
                    impact += matches * 15  # 社交事件中等影响
                else:
                    impact += matches * 10  # 其他事件小影响

        # 事件类型影响
        type_multipliers = {
            'world_event': 1.2,
            'preset_event': 1.0,
            'dialogue': 0.8
        }

        impact *= type_multipliers.get(event_type, 1.0)

        return min(100, int(impact))

    def _calculate_state_modifier(self) -> int:
        """计算当前状态的影响修正"""
        modifier = 0

        # 主要状态影响
        if self.current_state.primary_state == "rest":
            modifier -= 20  # 休息状态对事件反应迟钝
        elif self.current_state.primary_state == "activity":
            modifier += 10  # 活动状态更警觉

        # 警觉度影响
        alertness = self.current_state.alertness_level
        modifier += (alertness - 50) * 0.5  # 警觉度偏离50的影响

        # 连续休息时间影响
        rest_hours = self.current_state.consecutive_rest_hours
        if rest_hours > 8:
            modifier -= 15  # 睡太久会更迟钝
        elif rest_hours > 4:
            modifier -= 5   # 睡了段时间后开始清醒

        # 情感状态影响
        emotion_modifiers = {
            "angry": 10,    # 愤怒时更敏感
            "fearful": 15,  # 害怕时高度敏感
            "happy": -5,    # 高兴时不太敏感
            "sad": -10,     # 悲伤时迟钝
            "calm": 0       # 平静正常
        }
        modifier += emotion_modifiers.get(self.current_state.emotional_state, 0)

        return int(modifier)

    def _calculate_time_modifier(self) -> int:
        """计算时间的影响修正"""
        current_hour = datetime.now().hour
        modifier = 0

        # 深夜时间更迟钝
        if 0 <= current_hour <= 5:
            modifier -= 25
        elif 6 <= current_hour <= 8:
            modifier -= 10  # 早上开始清醒
        elif 9 <= current_hour <= 17:
            modifier += 5   # 白天正常
        elif 18 <= current_hour <= 22:
            modifier += 10  # 晚上更警觉
        elif 23 <= current_hour <= 23:
            modifier -= 15  # 深夜开始疲惫

        return modifier

    def should_respond_to_event(self, impact_analysis: Dict[str, Any]) -> bool:
        """判断是否应该对事件做出响应"""
        impact_score = impact_analysis['impact_score']
        sensitivity = impact_analysis['sensitivity_threshold']

        # 基础判断
        if impact_score > sensitivity:
            return True

        # 特殊情况：即使影响不高，也可能响应
        # 例如：威胁事件总是有机会被注意到
        if 'threat' in impact_analysis.get('event_category', ''):
            return impact_score > (sensitivity * 0.7)

        return False

    def get_unresolved_events(self) -> List[NPCEvent]:
        """获取未解决的事件"""
        return [event for event in self.event_history if not event.resolved]

    def resolve_event(self, event_timestamp: str):
        """标记事件为已解决"""
        for event in self.event_history:
            if event.timestamp == event_timestamp:
                event.resolved = True
                break
        self._save_data()

    def get_recent_memories(self, days: int = 7) -> List[NPCEvent]:
        """获取最近的记忆（事件）"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return [event for event in self.event_history
                if datetime.fromisoformat(event.timestamp) > cutoff_date]

    def update_thinking_variables(self, **updates):
        """更新思考变量"""
        self.thinking_variables.update(updates)
        self._save_data()

    def get_full_state_summary(self) -> Dict[str, Any]:
        """获取完整状态摘要"""
        state_dict = asdict(self.current_state)
        # 添加current_task对象以保持向后兼容性
        state_dict['current_task'] = asdict(self.current_task) if self.current_task else None

        return {
            'npc_name': self.npc_name,
            'current_state': state_dict,
            'active_tasks': [asdict(task) for task in self.tasks.values() if task.status == 'active'],
            'unresolved_events': len(self.get_unresolved_events()),
            'recent_events': len(self.get_recent_memories(1)),  # 最近24小时
            'thinking_variables': self.thinking_variables
        }
