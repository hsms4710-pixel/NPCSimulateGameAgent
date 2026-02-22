# -*- coding: utf-8 -*-
"""
任务/剧情系统模块
==================

管理游戏中的任务创建、追踪、完成等功能。

主要组件:
- QuestObjective: 任务目标，定义需要完成的具体条件
- Quest: 任务实体，包含完整的任务信息
- QuestManager: 任务管理器，统一管理所有任务
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from datetime import datetime
import copy

logger = logging.getLogger(__name__)


# =============================================================================
# 枚举定义
# =============================================================================

class ObjectiveType(Enum):
    """任务目标类型"""
    TALK_TO = "talk_to"           # 与NPC对话
    COLLECT = "collect"            # 收集物品
    DELIVER = "deliver"            # 递送物品
    KILL = "kill"                  # 击杀目标
    EXPLORE = "explore"            # 探索地点
    ESCORT = "escort"              # 护送NPC
    INTERACT = "interact"          # 与物体交互
    CRAFT = "craft"                # 制作物品
    PURCHASE = "purchase"          # 购买物品
    REACH_LEVEL = "reach_level"    # 达到等级
    EARN_GOLD = "earn_gold"        # 赚取金币
    CUSTOM = "custom"              # 自定义目标


class QuestStatus(Enum):
    """任务状态"""
    UNAVAILABLE = "unavailable"    # 不可用（未解锁）
    AVAILABLE = "available"        # 可接取
    IN_PROGRESS = "in_progress"    # 进行中
    READY_TO_COMPLETE = "ready_to_complete"  # 可提交
    COMPLETED = "completed"        # 已完成
    FAILED = "failed"              # 已失败
    ABANDONED = "abandoned"        # 已放弃


class QuestType(Enum):
    """任务类型"""
    MAIN = "main"                  # 主线任务
    SIDE = "side"                  # 支线任务
    DAILY = "daily"                # 日常任务
    REPEATABLE = "repeatable"      # 可重复任务
    HIDDEN = "hidden"              # 隐藏任务
    EVENT = "event"                # 事件任务


class QuestDifficulty(Enum):
    """任务难度"""
    TRIVIAL = ("简单", 1)
    EASY = ("普通", 2)
    NORMAL = ("中等", 3)
    HARD = ("困难", 4)
    LEGENDARY = ("传说", 5)

    def __init__(self, display_name: str, level: int):
        self.display_name = display_name
        self.level = level


# =============================================================================
# 任务目标
# =============================================================================

@dataclass
class QuestObjective:
    """
    任务目标

    定义任务中需要完成的具体条件。
    """
    objective_id: str
    objective_type: ObjectiveType
    description: str
    target: str                    # 目标对象（NPC名/物品ID/地点名等）
    quantity: int = 1              # 需要完成的数量
    progress: int = 0              # 当前进度
    is_optional: bool = False      # 是否为可选目标
    is_hidden: bool = False        # 是否为隐藏目标（完成前不显示）
    target_location: Optional[str] = None  # 目标地点（如有）
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        """目标是否完成"""
        return self.progress >= self.quantity

    @property
    def progress_percentage(self) -> float:
        """完成百分比"""
        if self.quantity <= 0:
            return 100.0
        return min(100.0, (self.progress / self.quantity) * 100)

    def update_progress(self, amount: int = 1) -> bool:
        """
        更新进度

        参数:
            amount: 增加的进度

        返回:
            是否刚刚完成（从未完成变为完成）
        """
        was_completed = self.is_completed
        self.progress = min(self.quantity, self.progress + amount)
        return not was_completed and self.is_completed

    def reset_progress(self):
        """重置进度"""
        self.progress = 0

    def get_display_text(self) -> str:
        """获取显示文本"""
        status_icon = "[完成]" if self.is_completed else f"[{self.progress}/{self.quantity}]"
        optional_tag = "(可选)" if self.is_optional else ""
        return f"{status_icon} {self.description} {optional_tag}".strip()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "objective_id": self.objective_id,
            "type": self.objective_type.value,
            "description": self.description,
            "target": self.target,
            "quantity": self.quantity,
            "progress": self.progress,
            "is_optional": self.is_optional,
            "is_hidden": self.is_hidden,
            "is_completed": self.is_completed,
            "progress_percentage": self.progress_percentage,
            "target_location": self.target_location,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestObjective':
        """从字典创建"""
        return cls(
            objective_id=data["objective_id"],
            objective_type=ObjectiveType(data["type"]),
            description=data["description"],
            target=data["target"],
            quantity=data.get("quantity", 1),
            progress=data.get("progress", 0),
            is_optional=data.get("is_optional", False),
            is_hidden=data.get("is_hidden", False),
            target_location=data.get("target_location"),
            metadata=data.get("metadata", {})
        )


# =============================================================================
# 任务奖励
# =============================================================================

@dataclass
class QuestReward:
    """任务奖励"""
    gold: int = 0                              # 金币奖励
    experience: int = 0                         # 经验值奖励
    items: Dict[str, int] = field(default_factory=dict)  # 物品奖励 {item_id: quantity}
    reputation: Dict[str, int] = field(default_factory=dict)  # 声望奖励 {faction: amount}
    skills: Dict[str, int] = field(default_factory=dict)  # 技能点奖励 {skill: points}
    unlocks: List[str] = field(default_factory=list)  # 解锁内容（任务/地点/功能等）
    custom: Dict[str, Any] = field(default_factory=dict)  # 自定义奖励

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "gold": self.gold,
            "experience": self.experience,
            "items": self.items,
            "reputation": self.reputation,
            "skills": self.skills,
            "unlocks": self.unlocks,
            "custom": self.custom
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestReward':
        """从字典创建"""
        return cls(
            gold=data.get("gold", 0),
            experience=data.get("experience", 0),
            items=data.get("items", {}),
            reputation=data.get("reputation", {}),
            skills=data.get("skills", {}),
            unlocks=data.get("unlocks", []),
            custom=data.get("custom", {})
        )

    def get_display_text(self) -> str:
        """获取奖励显示文本"""
        parts = []
        if self.gold > 0:
            parts.append(f"{self.gold} 金币")
        if self.experience > 0:
            parts.append(f"{self.experience} 经验")
        if self.items:
            for item_id, qty in self.items.items():
                parts.append(f"{item_id} x{qty}")
        if self.reputation:
            for faction, amount in self.reputation.items():
                parts.append(f"{faction}声望 +{amount}")
        return ", ".join(parts) if parts else "无"


# =============================================================================
# 任务
# =============================================================================

@dataclass
class Quest:
    """
    任务

    表示游戏中的一个完整任务，包含目标、奖励、状态等信息。
    """
    quest_id: str
    title: str
    description: str
    quest_type: QuestType = QuestType.SIDE
    difficulty: QuestDifficulty = QuestDifficulty.NORMAL

    # 任务发布者
    giver: Optional[str] = None
    giver_location: Optional[str] = None

    # 任务目标
    objectives: List[QuestObjective] = field(default_factory=list)

    # 任务奖励
    rewards: QuestReward = field(default_factory=QuestReward)

    # 前置条件
    prerequisites: List[str] = field(default_factory=list)  # 前置任务ID
    level_requirement: int = 0  # 等级要求
    reputation_requirements: Dict[str, int] = field(default_factory=dict)  # 声望要求

    # 状态
    status: QuestStatus = QuestStatus.AVAILABLE
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 时间限制
    time_limit_hours: Optional[float] = None  # 时间限制（游戏小时）
    expire_at: Optional[datetime] = None

    # 对话和剧情
    accept_dialogue: str = ""      # 接受任务时的对话
    progress_dialogue: str = ""    # 进行中的对话
    complete_dialogue: str = ""    # 完成时的对话
    fail_dialogue: str = ""        # 失败时的对话

    # 可重复性
    is_repeatable: bool = False
    repeat_cooldown_hours: float = 24.0
    times_completed: int = 0
    last_completed_at: Optional[datetime] = None

    # 元数据
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        """任务是否完成"""
        return self.status == QuestStatus.COMPLETED

    @property
    def is_active(self) -> bool:
        """任务是否激活（进行中）"""
        return self.status == QuestStatus.IN_PROGRESS

    @property
    def all_objectives_completed(self) -> bool:
        """所有必要目标是否完成"""
        return all(
            obj.is_completed
            for obj in self.objectives
            if not obj.is_optional
        )

    @property
    def completion_percentage(self) -> float:
        """总完成百分比"""
        if not self.objectives:
            return 0.0
        required = [obj for obj in self.objectives if not obj.is_optional]
        if not required:
            return 100.0
        return sum(obj.progress_percentage for obj in required) / len(required)

    def get_objective(self, objective_id: str) -> Optional[QuestObjective]:
        """获取指定目标"""
        for obj in self.objectives:
            if obj.objective_id == objective_id:
                return obj
        return None

    def get_objectives_by_type(self, obj_type: ObjectiveType) -> List[QuestObjective]:
        """按类型获取目标"""
        return [obj for obj in self.objectives if obj.objective_type == obj_type]

    def check_can_complete(self) -> Tuple[bool, str]:
        """
        检查是否可以完成任务

        返回:
            (是否可完成, 原因说明)
        """
        if self.status not in (QuestStatus.IN_PROGRESS, QuestStatus.READY_TO_COMPLETE):
            return False, "任务未在进行中"

        if not self.all_objectives_completed:
            incomplete = [
                obj.description
                for obj in self.objectives
                if not obj.is_optional and not obj.is_completed
            ]
            return False, f"未完成的目标: {', '.join(incomplete)}"

        return True, "可以完成"

    def get_current_dialogue(self) -> str:
        """获取当前对话"""
        if self.status == QuestStatus.AVAILABLE:
            return self.accept_dialogue
        elif self.status == QuestStatus.IN_PROGRESS:
            return self.progress_dialogue
        elif self.status in (QuestStatus.READY_TO_COMPLETE, QuestStatus.COMPLETED):
            return self.complete_dialogue
        elif self.status == QuestStatus.FAILED:
            return self.fail_dialogue
        return ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "quest_id": self.quest_id,
            "title": self.title,
            "description": self.description,
            "quest_type": self.quest_type.value,
            "difficulty": self.difficulty.display_name,
            "giver": self.giver,
            "giver_location": self.giver_location,
            "objectives": [obj.to_dict() for obj in self.objectives],
            "rewards": self.rewards.to_dict(),
            "prerequisites": self.prerequisites,
            "level_requirement": self.level_requirement,
            "reputation_requirements": self.reputation_requirements,
            "status": self.status.value,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "time_limit_hours": self.time_limit_hours,
            "is_repeatable": self.is_repeatable,
            "times_completed": self.times_completed,
            "completion_percentage": self.completion_percentage,
            "tags": self.tags,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Quest':
        """从字典创建"""
        quest = cls(
            quest_id=data["quest_id"],
            title=data["title"],
            description=data["description"],
            quest_type=QuestType(data.get("quest_type", "side")),
            difficulty=QuestDifficulty[data.get("difficulty", "NORMAL").upper()]
                if isinstance(data.get("difficulty"), str)
                else QuestDifficulty.NORMAL,
            giver=data.get("giver"),
            giver_location=data.get("giver_location"),
            objectives=[QuestObjective.from_dict(obj) for obj in data.get("objectives", [])],
            rewards=QuestReward.from_dict(data.get("rewards", {})),
            prerequisites=data.get("prerequisites", []),
            level_requirement=data.get("level_requirement", 0),
            reputation_requirements=data.get("reputation_requirements", {}),
            status=QuestStatus(data.get("status", "available")),
            time_limit_hours=data.get("time_limit_hours"),
            is_repeatable=data.get("is_repeatable", False),
            times_completed=data.get("times_completed", 0),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {})
        )

        if data.get("accepted_at"):
            quest.accepted_at = datetime.fromisoformat(data["accepted_at"])
        if data.get("completed_at"):
            quest.completed_at = datetime.fromisoformat(data["completed_at"])

        return quest


# =============================================================================
# 任务触发器
# =============================================================================

@dataclass
class QuestTrigger:
    """任务触发器"""
    trigger_id: str
    quest_id: str
    trigger_type: str              # 触发类型: location, npc_talk, item_collect, event等
    trigger_condition: Dict[str, Any]  # 触发条件
    is_one_time: bool = True       # 是否只触发一次
    has_triggered: bool = False

    def check_trigger(self, event_data: Dict[str, Any]) -> bool:
        """
        检查是否满足触发条件

        参数:
            event_data: 事件数据

        返回:
            是否触发
        """
        if self.is_one_time and self.has_triggered:
            return False

        trigger_type = event_data.get("type")
        if trigger_type != self.trigger_type:
            return False

        # 根据触发类型检查条件
        if trigger_type == "location":
            return event_data.get("location") == self.trigger_condition.get("location")

        elif trigger_type == "npc_talk":
            return event_data.get("npc") == self.trigger_condition.get("npc")

        elif trigger_type == "item_collect":
            item_id = self.trigger_condition.get("item_id")
            quantity = self.trigger_condition.get("quantity", 1)
            return (event_data.get("item_id") == item_id and
                    event_data.get("quantity", 0) >= quantity)

        elif trigger_type == "event":
            return event_data.get("event_id") == self.trigger_condition.get("event_id")

        elif trigger_type == "time":
            return event_data.get("hour") == self.trigger_condition.get("hour")

        return False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trigger_id": self.trigger_id,
            "quest_id": self.quest_id,
            "trigger_type": self.trigger_type,
            "trigger_condition": self.trigger_condition,
            "is_one_time": self.is_one_time,
            "has_triggered": self.has_triggered
        }


# =============================================================================
# 任务管理器
# =============================================================================

class QuestManager:
    """
    任务管理器

    统一管理所有任务的创建、接取、进度更新、完成等操作。
    """

    def __init__(self, economy_system=None):
        """
        初始化任务管理器

        参数:
            economy_system: 经济系统（用于发放奖励）
        """
        self.economy_system = economy_system

        # 所有任务定义: {quest_id: Quest}
        self._quests: Dict[str, Quest] = {}

        # 玩家活跃任务: {player_id: Set[quest_id]}
        self._active_quests: Dict[str, Set[str]] = {}

        # 玩家已完成任务: {player_id: Set[quest_id]}
        self._completed_quests: Dict[str, Set[str]] = {}

        # 任务触发器
        self._triggers: List[QuestTrigger] = []

        # 事件回调
        self._on_quest_complete: List[Callable] = []
        self._on_quest_accept: List[Callable] = []
        self._on_objective_complete: List[Callable] = []

        # 初始化默认任务
        self._initialize_default_quests()

        logger.info("任务管理器初始化完成")

    def _ensure_player(self, player: str):
        """确保玩家数据存在"""
        if player not in self._active_quests:
            self._active_quests[player] = set()
        if player not in self._completed_quests:
            self._completed_quests[player] = set()

    def _initialize_default_quests(self):
        """初始化默认任务"""
        # 新手引导任务
        welcome_quest = Quest(
            quest_id="welcome_to_village",
            title="欢迎来到艾伦谷",
            description="与村庄里的居民交流，了解这个地方。",
            quest_type=QuestType.MAIN,
            difficulty=QuestDifficulty.TRIVIAL,
            giver="村长",
            giver_location="镇中心",
            objectives=[
                QuestObjective(
                    objective_id="talk_to_elder",
                    objective_type=ObjectiveType.TALK_TO,
                    description="与村长交谈",
                    target="村长",
                    quantity=1
                ),
                QuestObjective(
                    objective_id="explore_village",
                    objective_type=ObjectiveType.EXPLORE,
                    description="探索村庄的主要区域",
                    target="村庄",
                    quantity=3,
                    metadata={"locations": ["市场区", "酒馆", "铁匠铺"]}
                )
            ],
            rewards=QuestReward(
                gold=50,
                experience=100,
                items={"bread": 5, "water": 3}
            ),
            accept_dialogue="欢迎，旅行者！艾伦谷是个和平的地方。请四处看看，与村民们交流吧。",
            progress_dialogue="你探索得怎么样了？记得去市场区、酒馆和铁匠铺看看。",
            complete_dialogue="太好了！你已经熟悉了我们的村庄。希望你在这里过得愉快！"
        )
        self.create_quest(welcome_quest)

        # 收集任务
        gather_quest = Quest(
            quest_id="gather_herbs",
            title="草药采集",
            description="草药师需要一些草药来制作药剂。",
            quest_type=QuestType.SIDE,
            difficulty=QuestDifficulty.EASY,
            giver="草药师",
            giver_location="市场区",
            objectives=[
                QuestObjective(
                    objective_id="collect_herbs",
                    objective_type=ObjectiveType.COLLECT,
                    description="收集草药",
                    target="herb",
                    quantity=5
                )
            ],
            rewards=QuestReward(
                gold=30,
                experience=50,
                items={"health_potion": 2}
            ),
            prerequisites=[],
            accept_dialogue="我需要一些新鲜的草药来制作药剂。你能帮我收集5份吗？",
            progress_dialogue="草药收集得怎么样了？",
            complete_dialogue="太感谢了！这些草药正是我需要的。给你一些药水作为报答。",
            is_repeatable=True,
            repeat_cooldown_hours=24.0
        )
        self.create_quest(gather_quest)

        # 递送任务
        delivery_quest = Quest(
            quest_id="delivery_to_blacksmith",
            title="铁匠的订单",
            description="帮助商人将铁矿石送到铁匠铺。",
            quest_type=QuestType.SIDE,
            difficulty=QuestDifficulty.EASY,
            giver="商人",
            giver_location="市场区",
            objectives=[
                QuestObjective(
                    objective_id="get_ore",
                    objective_type=ObjectiveType.COLLECT,
                    description="从商人处获取铁矿石",
                    target="iron_ore",
                    quantity=3
                ),
                QuestObjective(
                    objective_id="deliver_ore",
                    objective_type=ObjectiveType.DELIVER,
                    description="将铁矿石送到铁匠铺",
                    target="铁匠",
                    quantity=3,
                    target_location="铁匠铺"
                )
            ],
            rewards=QuestReward(
                gold=40,
                experience=60,
                reputation={"商人行会": 10}
            ),
            prerequisites=["welcome_to_village"],
            accept_dialogue="我有一批铁矿石需要送到铁匠那里，但我走不开。你能帮我送一下吗？",
            progress_dialogue="记得把铁矿石送到铁匠铺哦！",
            complete_dialogue="效率很高！这是你应得的报酬。"
        )
        self.create_quest(delivery_quest)

        # 调查任务
        investigate_quest = Quest(
            quest_id="mysterious_noise",
            title="神秘的声音",
            description="调查酒馆后院传来的奇怪声音。",
            quest_type=QuestType.SIDE,
            difficulty=QuestDifficulty.NORMAL,
            giver="酒馆老板",
            giver_location="酒馆",
            objectives=[
                QuestObjective(
                    objective_id="investigate_backyard",
                    objective_type=ObjectiveType.EXPLORE,
                    description="调查酒馆后院",
                    target="酒馆后院",
                    quantity=1
                ),
                QuestObjective(
                    objective_id="find_source",
                    objective_type=ObjectiveType.INTERACT,
                    description="找到声音的来源",
                    target="神秘木箱",
                    quantity=1,
                    is_hidden=True
                ),
                QuestObjective(
                    objective_id="report_back",
                    objective_type=ObjectiveType.TALK_TO,
                    description="向酒馆老板报告",
                    target="酒馆老板",
                    quantity=1
                )
            ],
            rewards=QuestReward(
                gold=80,
                experience=120,
                items={"ale": 5},
                unlocks=["hidden_cellar"]
            ),
            accept_dialogue="最近后院总是有奇怪的声音，我忙着招呼客人没法去看。你能帮我调查一下吗？",
            progress_dialogue="查到什么了吗？那声音真的让我不安。",
            complete_dialogue="原来是这样！谢谢你帮我解决了这个谜团。来，喝杯酒暖暖身子！"
        )
        self.create_quest(investigate_quest)

    def create_quest(self, quest: Quest) -> bool:
        """
        创建/注册任务

        参数:
            quest: 任务对象

        返回:
            是否成功
        """
        if quest.quest_id in self._quests:
            logger.warning(f"任务已存在，将被覆盖: {quest.quest_id}")

        self._quests[quest.quest_id] = quest
        logger.debug(f"任务注册: {quest.title} ({quest.quest_id})")
        return True

    def create_quest_from_data(self, quest_data: Dict[str, Any]) -> bool:
        """
        从字典数据创建任务

        参数:
            quest_data: 任务数据字典

        返回:
            是否成功
        """
        try:
            quest = Quest.from_dict(quest_data)
            return self.create_quest(quest)
        except Exception as e:
            logger.error(f"创建任务失败: {e}")
            return False

    def get_quest(self, quest_id: str) -> Optional[Quest]:
        """
        获取任务

        参数:
            quest_id: 任务ID

        返回:
            任务对象
        """
        return self._quests.get(quest_id)

    def accept_quest(self, quest_id: str, player: str) -> Tuple[bool, str]:
        """
        接受任务

        参数:
            quest_id: 任务ID
            player: 玩家标识

        返回:
            (是否成功, 消息)
        """
        self._ensure_player(player)
        quest = self._quests.get(quest_id)

        if not quest:
            return False, f"任务不存在: {quest_id}"

        # 检查是否已接受
        if quest_id in self._active_quests[player]:
            return False, "你已经接受了这个任务"

        # 检查是否已完成（非重复任务）
        if quest_id in self._completed_quests[player] and not quest.is_repeatable:
            return False, "你已经完成过这个任务"

        # 检查前置任务
        for prereq in quest.prerequisites:
            if prereq not in self._completed_quests[player]:
                prereq_quest = self._quests.get(prereq)
                prereq_name = prereq_quest.title if prereq_quest else prereq
                return False, f"需要先完成任务: {prereq_name}"

        # 接受任务
        # 创建任务副本（如果是可重复任务）
        if quest.is_repeatable and quest_id in self._completed_quests[player]:
            # 重置进度
            for obj in quest.objectives:
                obj.reset_progress()

        quest.status = QuestStatus.IN_PROGRESS
        quest.accepted_at = datetime.now()
        self._active_quests[player].add(quest_id)

        # 触发回调
        for callback in self._on_quest_accept:
            try:
                callback(player, quest)
            except Exception as e:
                logger.error(f"任务接受回调失败: {e}")

        logger.info(f"任务接受: {player} 接受了 {quest.title}")
        return True, f"已接受任务: {quest.title}"

    def update_quest_progress(self, quest_id: str, objective_id: str,
                              progress: int = 1, player: str = None) -> Tuple[bool, str]:
        """
        更新任务进度

        参数:
            quest_id: 任务ID
            objective_id: 目标ID
            progress: 增加的进度
            player: 玩家标识（可选）

        返回:
            (是否成功, 消息)
        """
        quest = self._quests.get(quest_id)
        if not quest:
            return False, f"任务不存在: {quest_id}"

        if quest.status != QuestStatus.IN_PROGRESS:
            return False, "任务未在进行中"

        objective = quest.get_objective(objective_id)
        if not objective:
            return False, f"目标不存在: {objective_id}"

        just_completed = objective.update_progress(progress)

        # 检查是否所有目标完成
        if quest.all_objectives_completed:
            quest.status = QuestStatus.READY_TO_COMPLETE
            logger.info(f"任务可提交: {quest.title}")

        # 触发目标完成回调
        if just_completed:
            for callback in self._on_objective_complete:
                try:
                    callback(player, quest, objective)
                except Exception as e:
                    logger.error(f"目标完成回调失败: {e}")

        return True, f"进度更新: {objective.description} ({objective.progress}/{objective.quantity})"

    def complete_quest(self, quest_id: str, player: str) -> Tuple[bool, str, Optional[QuestReward]]:
        """
        完成任务

        参数:
            quest_id: 任务ID
            player: 玩家标识

        返回:
            (是否成功, 消息, 奖励)
        """
        self._ensure_player(player)
        quest = self._quests.get(quest_id)

        if not quest:
            return False, f"任务不存在: {quest_id}", None

        if quest_id not in self._active_quests[player]:
            return False, "你没有接受这个任务", None

        can_complete, reason = quest.check_can_complete()
        if not can_complete:
            return False, reason, None

        # 完成任务
        quest.status = QuestStatus.COMPLETED
        quest.completed_at = datetime.now()
        quest.times_completed += 1
        quest.last_completed_at = datetime.now()

        self._active_quests[player].remove(quest_id)
        self._completed_quests[player].add(quest_id)

        # 发放奖励
        rewards = quest.rewards
        self._grant_rewards(player, rewards)

        # 触发回调
        for callback in self._on_quest_complete:
            try:
                callback(player, quest, rewards)
            except Exception as e:
                logger.error(f"任务完成回调失败: {e}")

        logger.info(f"任务完成: {player} 完成了 {quest.title}")
        return True, f"恭喜完成任务: {quest.title}!", rewards

    def _grant_rewards(self, player: str, rewards: QuestReward):
        """发放奖励"""
        if self.economy_system and rewards.gold > 0:
            self.economy_system.currency_manager.add_funds(
                player, rewards.gold,
                reason="任务奖励"
            )

        if self.economy_system and rewards.items:
            for item_id, quantity in rewards.items.items():
                self.economy_system.inventory_manager.add_item(
                    player, item_id, quantity
                )

        # 其他奖励（经验、声望等）需要根据具体系统实现
        logger.debug(f"奖励发放: {player} 获得 {rewards.get_display_text()}")

    def abandon_quest(self, quest_id: str, player: str) -> Tuple[bool, str]:
        """
        放弃任务

        参数:
            quest_id: 任务ID
            player: 玩家标识

        返回:
            (是否成功, 消息)
        """
        self._ensure_player(player)
        quest = self._quests.get(quest_id)

        if not quest:
            return False, f"任务不存在: {quest_id}"

        if quest_id not in self._active_quests[player]:
            return False, "你没有接受这个任务"

        # 重置任务
        quest.status = QuestStatus.ABANDONED
        for obj in quest.objectives:
            obj.reset_progress()

        self._active_quests[player].remove(quest_id)

        logger.info(f"任务放弃: {player} 放弃了 {quest.title}")
        return True, f"已放弃任务: {quest.title}"

    def fail_quest(self, quest_id: str, player: str, reason: str = "") -> Tuple[bool, str]:
        """
        任务失败

        参数:
            quest_id: 任务ID
            player: 玩家标识
            reason: 失败原因

        返回:
            (是否成功, 消息)
        """
        self._ensure_player(player)
        quest = self._quests.get(quest_id)

        if not quest:
            return False, f"任务不存在: {quest_id}"

        if quest_id not in self._active_quests[player]:
            return False, "你没有接受这个任务"

        quest.status = QuestStatus.FAILED
        self._active_quests[player].remove(quest_id)

        logger.info(f"任务失败: {player} 的任务 {quest.title} 失败了, 原因: {reason}")
        return True, f"任务失败: {quest.title}。{reason}"

    def check_quest_triggers(self, event: Dict[str, Any], player: str) -> List[str]:
        """
        检查事件是否触发任务

        参数:
            event: 事件数据
            player: 玩家标识

        返回:
            触发的任务ID列表
        """
        triggered = []

        for trigger in self._triggers:
            if trigger.check_trigger(event):
                quest_id = trigger.quest_id
                quest = self._quests.get(quest_id)

                if quest and quest.status == QuestStatus.AVAILABLE:
                    # 自动接受触发的任务或标记为可接受
                    trigger.has_triggered = True
                    triggered.append(quest_id)
                    logger.info(f"任务触发: {quest.title} (触发器: {trigger.trigger_id})")

        return triggered

    def get_available_quests(self, player: str,
                             location: Optional[str] = None) -> List[Quest]:
        """
        获取可接取的任务

        参数:
            player: 玩家标识
            location: 当前位置（可选，用于筛选）

        返回:
            可接取的任务列表
        """
        self._ensure_player(player)
        available = []

        for quest in self._quests.values():
            # 跳过已接受的
            if quest.quest_id in self._active_quests[player]:
                continue

            # 跳过已完成的非重复任务
            if quest.quest_id in self._completed_quests[player] and not quest.is_repeatable:
                continue

            # 检查前置任务
            prereq_met = all(
                prereq in self._completed_quests[player]
                for prereq in quest.prerequisites
            )
            if not prereq_met:
                continue

            # 位置筛选
            if location and quest.giver_location:
                if quest.giver_location != location:
                    continue

            available.append(quest)

        return available

    def get_active_quests(self, player: str) -> List[Quest]:
        """
        获取玩家进行中的任务

        参数:
            player: 玩家标识

        返回:
            进行中的任务列表
        """
        self._ensure_player(player)
        return [
            self._quests[qid]
            for qid in self._active_quests[player]
            if qid in self._quests
        ]

    def get_completed_quests(self, player: str) -> List[Quest]:
        """
        获取玩家已完成的任务

        参数:
            player: 玩家标识

        返回:
            已完成的任务列表
        """
        self._ensure_player(player)
        return [
            self._quests[qid]
            for qid in self._completed_quests[player]
            if qid in self._quests
        ]

    def get_quests_by_giver(self, giver: str) -> List[Quest]:
        """
        按发布者获取任务

        参数:
            giver: NPC名称

        返回:
            该NPC发布的任务列表
        """
        return [q for q in self._quests.values() if q.giver == giver]

    def get_quests_by_type(self, quest_type: QuestType) -> List[Quest]:
        """
        按类型获取任务

        参数:
            quest_type: 任务类型

        返回:
            该类型的任务列表
        """
        return [q for q in self._quests.values() if q.quest_type == quest_type]

    def register_trigger(self, trigger: QuestTrigger):
        """
        注册任务触发器

        参数:
            trigger: 触发器对象
        """
        self._triggers.append(trigger)
        logger.debug(f"触发器注册: {trigger.trigger_id} -> {trigger.quest_id}")

    def on_quest_complete(self, callback: Callable):
        """注册任务完成回调"""
        self._on_quest_complete.append(callback)

    def on_quest_accept(self, callback: Callable):
        """注册任务接受回调"""
        self._on_quest_accept.append(callback)

    def on_objective_complete(self, callback: Callable):
        """注册目标完成回调"""
        self._on_objective_complete.append(callback)

    def get_quest_summary(self, player: str) -> Dict[str, Any]:
        """
        获取玩家任务概览

        参数:
            player: 玩家标识

        返回:
            任务概览信息
        """
        self._ensure_player(player)
        active = self.get_active_quests(player)
        completed = self.get_completed_quests(player)

        return {
            "active_count": len(active),
            "completed_count": len(completed),
            "active_quests": [
                {
                    "quest_id": q.quest_id,
                    "title": q.title,
                    "completion": q.completion_percentage,
                    "difficulty": q.difficulty.display_name
                }
                for q in active
            ],
            "recent_completed": [
                {
                    "quest_id": q.quest_id,
                    "title": q.title,
                    "completed_at": q.completed_at.isoformat() if q.completed_at else None
                }
                for q in sorted(completed, key=lambda x: x.completed_at or datetime.min, reverse=True)[:5]
            ]
        }

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "quests": {qid: q.to_dict() for qid, q in self._quests.items()},
            "triggers": [t.to_dict() for t in self._triggers]
        }


# =============================================================================
# 预定义任务模板
# =============================================================================

QUEST_TEMPLATES = {
    "fetch_quest": {
        "quest_type": QuestType.SIDE,
        "difficulty": QuestDifficulty.EASY,
        "objective_template": {
            "type": ObjectiveType.COLLECT,
            "quantity": 5
        }
    },
    "delivery_quest": {
        "quest_type": QuestType.SIDE,
        "difficulty": QuestDifficulty.EASY,
        "objective_template": {
            "type": ObjectiveType.DELIVER,
            "quantity": 1
        }
    },
    "talk_quest": {
        "quest_type": QuestType.MAIN,
        "difficulty": QuestDifficulty.TRIVIAL,
        "objective_template": {
            "type": ObjectiveType.TALK_TO,
            "quantity": 1
        }
    },
    "explore_quest": {
        "quest_type": QuestType.SIDE,
        "difficulty": QuestDifficulty.NORMAL,
        "objective_template": {
            "type": ObjectiveType.EXPLORE,
            "quantity": 3
        }
    }
}
