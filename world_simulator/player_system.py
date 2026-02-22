# -*- coding: utf-8 -*-
"""
玩家系统模块
管理玩家角色的创建、属性、行为和状态
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class PlayerAction(Enum):
    """玩家可执行的行为"""
    SOCIALIZE = "社交"      # 与NPC对话
    EAT = "饮食"            # 进食
    WORK = "工作"           # 工作
    REST = "休息"           # 休息
    MOVE = "移动"           # 移动到其他地点


class Gender(Enum):
    """性别"""
    MALE = "男"
    FEMALE = "女"
    OTHER = "其他"


class Profession(Enum):
    """职业预设"""
    TRAVELER = "旅行者"
    MERCHANT = "商人"
    ADVENTURER = "冒险者"
    SCHOLAR = "学者"
    CRAFTSMAN = "工匠"
    FARMER = "农民"
    GUARD = "卫兵"
    BARD = "吟游诗人"
    CUSTOM = "自定义"


class Personality(Enum):
    """性格类型"""
    FRIENDLY = "友善"
    RESERVED = "内向"
    AGGRESSIVE = "好斗"
    CURIOUS = "好奇"
    CAUTIOUS = "谨慎"
    CHEERFUL = "开朗"
    MELANCHOLIC = "忧郁"


@dataclass
class PlayerPreset:
    """玩家预设模板"""
    name: str
    profession: Profession
    age_range: tuple
    background: str
    personality: Personality
    starting_location: str
    skills: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "profession": self.profession.value,
            "age_range": self.age_range,
            "background": self.background,
            "personality": self.personality.value,
            "starting_location": self.starting_location,
            "skills": self.skills
        }


# 预设角色模板
PLAYER_PRESETS = {
    "traveler": PlayerPreset(
        name="旅行者",
        profession=Profession.TRAVELER,
        age_range=(20, 40),
        background="来自远方的旅行者，刚刚抵达艾伦谷寻找新的冒险。",
        personality=Personality.CURIOUS,
        starting_location="镇中心",
        skills={"交涉": 50, "观察": 60, "生存": 40}
    ),
    "merchant": PlayerPreset(
        name="商人",
        profession=Profession.MERCHANT,
        age_range=(25, 55),
        background="精明的商人，来到艾伦谷寻找商机和贸易伙伴。",
        personality=Personality.FRIENDLY,
        starting_location="市场区",
        skills={"交涉": 70, "估价": 80, "算术": 60}
    ),
    "adventurer": PlayerPreset(
        name="冒险者",
        profession=Profession.ADVENTURER,
        age_range=(18, 35),
        background="年轻的冒险者，听闻艾伦谷附近有神秘的遗迹。",
        personality=Personality.AGGRESSIVE,
        starting_location="酒馆",
        skills={"战斗": 60, "生存": 50, "探索": 70}
    ),
    "scholar": PlayerPreset(
        name="学者",
        profession=Profession.SCHOLAR,
        age_range=(30, 60),
        background="来自学院的学者，研究古代历史和民间传说。",
        personality=Personality.CAUTIOUS,
        starting_location="圣光教堂",
        skills={"知识": 80, "研究": 70, "语言": 60}
    ),
    "bard": PlayerPreset(
        name="吟游诗人",
        profession=Profession.BARD,
        age_range=(20, 45),
        background="四处游历的吟游诗人，收集故事和歌谣。",
        personality=Personality.CHEERFUL,
        starting_location="酒馆",
        skills={"表演": 75, "交涉": 65, "音乐": 80}
    )
}


@dataclass
class PlayerNeeds:
    """玩家需求状态"""
    hunger: float = 0.3      # 饥饿度 0-1 (0=饱, 1=极饿)
    fatigue: float = 0.2     # 疲劳度 0-1 (0=精力充沛, 1=精疲力竭)
    social: float = 0.5      # 社交需求 0-1 (0=满足, 1=孤独)

    def update(self, hours_passed: float):
        """根据时间更新需求"""
        self.hunger = min(1.0, self.hunger + hours_passed * 0.05)
        self.fatigue = min(1.0, self.fatigue + hours_passed * 0.03)
        self.social = min(1.0, self.social + hours_passed * 0.02)

    def satisfy_hunger(self, amount: float = 0.5):
        self.hunger = max(0.0, self.hunger - amount)

    def satisfy_fatigue(self, amount: float = 0.5):
        self.fatigue = max(0.0, self.fatigue - amount)

    def satisfy_social(self, amount: float = 0.3):
        self.social = max(0.0, self.social - amount)

    def to_dict(self) -> Dict[str, float]:
        return {
            "hunger": self.hunger,
            "fatigue": self.fatigue,
            "social": self.social
        }

    def get_urgent_need(self) -> Optional[str]:
        """获取最紧急的需求"""
        if self.hunger > 0.8:
            return "hunger"
        if self.fatigue > 0.8:
            return "fatigue"
        if self.social > 0.8:
            return "social"
        return None


@dataclass
class PlayerCharacter:
    """玩家角色"""
    # 基础信息
    name: str
    age: int
    gender: Gender
    profession: Profession

    # 背景设定
    background: str
    birthplace: str
    personality: Personality

    # 外观描述
    appearance: str = ""

    # 状态
    current_location: str = "镇中心"
    needs: PlayerNeeds = field(default_factory=PlayerNeeds)

    # 技能 (0-100)
    skills: Dict[str, int] = field(default_factory=dict)

    # 物品栏
    inventory: List[Dict[str, Any]] = field(default_factory=list)

    # 金钱
    gold: int = 100

    # 与NPC的关系
    relationships: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 玩家记忆/日志
    memories: List[Dict[str, Any]] = field(default_factory=list)

    # 创建时间
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.skills:
            self.skills = {"交涉": 50, "观察": 50, "生存": 50}

    @classmethod
    def from_preset(cls, preset_id: str, name: str, age: int, gender: Gender,
                    birthplace: str = "远方", appearance: str = "") -> 'PlayerCharacter':
        """从预设创建玩家角色"""
        preset = PLAYER_PRESETS.get(preset_id)
        if not preset:
            raise ValueError(f"未知预设: {preset_id}")

        return cls(
            name=name,
            age=age,
            gender=gender,
            profession=preset.profession,
            background=preset.background,
            birthplace=birthplace,
            personality=preset.personality,
            appearance=appearance,
            current_location=preset.starting_location,
            skills=preset.skills.copy()
        )

    @classmethod
    def create_custom(cls, name: str, age: int, gender: Gender,
                      profession: str, background: str, birthplace: str,
                      personality: Personality, appearance: str = "",
                      skills: Dict[str, int] = None) -> 'PlayerCharacter':
        """创建自定义玩家角色"""
        return cls(
            name=name,
            age=age,
            gender=gender,
            profession=Profession.CUSTOM,
            background=background,
            birthplace=birthplace,
            personality=personality,
            appearance=appearance,
            skills=skills or {"交涉": 50, "观察": 50, "生存": 50}
        )

    def move_to(self, location: str) -> bool:
        """移动到指定位置"""
        old_location = self.current_location
        self.current_location = location
        self.add_memory(f"从{old_location}移动到{location}")
        logger.info(f"玩家 {self.name} 从 {old_location} 移动到 {location}")
        return True

    def add_memory(self, content: str, importance: float = 0.5):
        """添加记忆"""
        self.memories.append({
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "importance": importance
        })
        # 保持最近100条记忆
        if len(self.memories) > 100:
            self.memories = self.memories[-100:]

    def update_relationship(self, npc_name: str, affinity_change: float = 0,
                           trust_change: float = 0):
        """更新与NPC的关系"""
        if npc_name not in self.relationships:
            self.relationships[npc_name] = {
                "affinity": 50,  # 好感度 0-100
                "trust": 50,     # 信任度 0-100
                "interactions": 0
            }

        rel = self.relationships[npc_name]
        rel["affinity"] = max(0, min(100, rel["affinity"] + affinity_change))
        rel["trust"] = max(0, min(100, rel["trust"] + trust_change))
        rel["interactions"] += 1

    def get_character_card(self) -> str:
        """获取角色卡描述"""
        return f"""【玩家角色】
姓名: {self.name}
年龄: {self.age}岁
性别: {self.gender.value}
职业: {self.profession.value}
性格: {self.personality.value}
出生地: {self.birthplace}
背景: {self.background}
外观: {self.appearance or '普通'}
当前位置: {self.current_location}
金钱: {self.gold} 金币
"""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "age": self.age,
            "gender": self.gender.value,
            "profession": self.profession.value,
            "background": self.background,
            "birthplace": self.birthplace,
            "personality": self.personality.value,
            "appearance": self.appearance,
            "current_location": self.current_location,
            "needs": self.needs.to_dict(),
            "skills": self.skills,
            "inventory": self.inventory,
            "gold": self.gold,
            "relationships": self.relationships,
            "memories": self.memories[-10:],  # 只返回最近10条
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerCharacter':
        """从字典创建"""
        needs = PlayerNeeds(**data.get("needs", {}))
        player = cls(
            name=data["name"],
            age=data["age"],
            gender=Gender(data["gender"]),
            profession=Profession(data["profession"]) if data["profession"] != "自定义" else Profession.CUSTOM,
            background=data["background"],
            birthplace=data["birthplace"],
            personality=Personality(data["personality"]),
            appearance=data.get("appearance", ""),
            current_location=data.get("current_location", "镇中心"),
            needs=needs,
            skills=data.get("skills", {}),
            inventory=data.get("inventory", []),
            gold=data.get("gold", 100),
            relationships=data.get("relationships", {}),
            memories=data.get("memories", [])
        )
        return player


def get_available_presets() -> Dict[str, Dict[str, Any]]:
    """获取所有可用预设"""
    return {k: v.to_dict() for k, v in PLAYER_PRESETS.items()}
